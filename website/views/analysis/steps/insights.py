import os
import subprocess
import tempfile
from decimal import Decimal

from babel.numbers import format_currency
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import DetailView

from website.currency import currency_symbol, get_currency_locale
from website.models import (
    AnalysisCostType,
    CostEfficiencyStrategy,
    InsightComparisonData,
)
from website.models import InterventionInstance
from website.models.output_metric import OutputMetric
from website.views.mixins import AnalysisObjectMixin, AnalysisPermissionRequiredMixin, AnalysisStepMixin


class Insights(AnalysisStepMixin, AnalysisObjectMixin, AnalysisPermissionRequiredMixin, DetailView):
    step_name = "insights"
    template_name = "analysis/insights.html"
    permission_required = "website.view_analysis"
    title = ""
    help_text = ""

    def dispatch(self, request, *args, **kwargs):
        if not self.step.calculations_done():
            self.step.calculate_if_possible()
        if not self.has_permission():
            return self.handle_no_permission()
        if not (self.step.dependencies_met and self.step.is_complete):
            return redirect(reverse("analysis", kwargs={"pk": self.analysis.pk}))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["output_metrics_by_intervention"] = {}
        context["cost_efficiency_strategies_by_intervention"] = {}
        context["cost_model_table_paginator"] = {}
        context["cost_model_table_page"] = {}
        context["other_cost_model_table_paginator"] = {}
        context["other_cost_model_table_page"] = {}
        context["cost_total_client_time"] = {}

        context["interventions_by_id"] = {a.id: a for a in self.analysis.interventions.all()}
        each_intervention_instance: InterventionInstance
        for each_intervention_instance in self.analysis.interventioninstance_set.all():
            context["output_metrics_by_intervention"][each_intervention_instance.id] = []
            for output_metric in each_intervention_instance.intervention.output_metric_objects():
                output_costs = self.analysis.output_costs.get(str(each_intervention_instance.id))
                if not output_costs.get(output_metric.id):
                    continue
                output_cost_all = output_costs[output_metric.id]["all"]
                output_cost_direct_only = output_costs[output_metric.id]["direct_only"]

                context["subcomponent_analysis_complete"] = self.step.workflow.get_step(
                    "allocate-subcomponent-costs"
                ).is_complete
                output_cost_in_kind = 0

                serialized_metric = {
                    "output_metric": output_metric,
                    "output_metric_slug": output_metric.get_slug(),
                    "output_cost_all": output_cost_all,
                    "output_cost_direct_only": output_cost_direct_only,
                    "insights_chart_data": self._get_insights_chart_data(
                        output_metric, intervention_instance=each_intervention_instance
                    ),
                }
                if self.analysis.in_kind_contributions:
                    output_cost_in_kind = output_costs[output_metric.id]["in_kind"]
                    serialized_metric.update({"output_cost_in_kind": output_cost_in_kind})

                # Populate data for efficiency bar chart
                bar_chart_data = self._get_bar_chart_data(
                    output_cost_all,
                    output_cost_direct_only,
                    output_cost_in_kind,
                )
                serialized_metric.update(
                    {
                        "efficiency_bar_chart_data": bar_chart_data,
                        "initial_card_label": bar_chart_data["total"]["label"],
                    }
                )

                context["output_metrics_by_intervention"][each_intervention_instance.id].append(
                    serialized_metric
                )

            context["cost_efficiency_strategies_by_intervention"][
                each_intervention_instance.display_name()
            ] = CostEfficiencyStrategy.objects.filter(interventions=each_intervention_instance.intervention)
            context["cost_model_table_paginator"][each_intervention_instance.display_name()] = (
                self._get_cost_model_table_paginator(each_intervention_instance)
            )

            context["cost_model_table_page"][each_intervention_instance.display_name()] = context[
                "cost_model_table_paginator"
            ][each_intervention_instance.display_name()].get_page(self.request.GET.get("page", 1))

            context["other_cost_model_table_paginator"][each_intervention_instance.display_name()] = (
                self._get_other_cost_model_table_paginator(each_intervention_instance)
            )
            context["other_cost_model_table_page"][each_intervention_instance.display_name()] = context[
                "other_cost_model_table_paginator"
            ][each_intervention_instance.display_name()].get_page(self.request.GET.get("page", 1))

            if self.analysis.client_time:
                client_costs = self.analysis.get_cost_total_client_time()
                client_cost_for_intervention_instance = client_costs[each_intervention_instance.id]

                client_time = self.analysis.get_cost_total_client_hours()
                context["cost_total_client_time"][each_intervention_instance.display_name()] = float(
                    round(client_cost_for_intervention_instance, 2)
                )
                context["label_total_client_time"] = _(
                    f"{float(round(client_time, 2)):,.2f} hours of client time"
                )

        context["analysis_full_path"] = self.request.build_absolute_uri(
            reverse("analysis", args=(self.analysis.id,))
        )
        context["cost_breakdown"] = {}
        for each_intervention_instance in self.analysis.interventioninstance_set.all():
            context["cost_breakdown"][each_intervention_instance.id] = self._get_cost_breakdown_data(
                each_intervention_instance
            )
        context["subcomponent_analysis_breakdown"] = self._get_subcomponent_analysis_breakdown_data()
        context["parameters_lookup"] = self._get_formatted_parameter_values()

        if self.analysis.currency_code and self.analysis.currency_code != settings.ISO_CURRENCY_CODE:
            context["data_excluded_footnote"] = (
                "Since the analysis results are not in the default currency, "
                "they are not directly comparable with the comparison data points, "
                "therefore you should convert your results to the default currency "
                "before comparing with these other data points."
            )

        return context

    def _get_formatted_parameter_values(self):
        """
        Here we consolidate the Parameters for all the Output Metrics for each Intervention Instance.

        This originally lived in the template but graduated to here due to the growing complexity of the Output Metrics.

        Specifically this was created to address the scenario where an Intervention has 2 Output
            Metrics that share one or more parameters.

        """
        parameter_lookup = {}
        for each_intervention_instance in self.analysis.interventioninstance_set.all():
            parameter_lookup[each_intervention_instance.id] = {}
            for parameter_id, parameter_value in each_intervention_instance.parameters.items():
                for output_metric in each_intervention_instance.intervention.output_metric_objects():
                    # Filter to only show the parameters with labels in the current output metric
                    if parameter_id not in output_metric.parameters:
                        continue
                    label = output_metric.parameters[parameter_id].label
                    if label in [
                        "Value of Cash Distributed",
                        "Value of Business Grant Amount",
                    ]:
                        formatted_value = f"{currency_symbol(self.analysis)}{parameter_value:,.2f}"
                    else:
                        formatted_value = f"{parameter_value:,.2f}"
                    parameter_lookup[each_intervention_instance.id][label] = formatted_value

        return parameter_lookup

    def _get_insights_chart_data(
        self,
        output_metric: OutputMetric,
        intervention_instance: InterventionInstance,
    ) -> list[dict]:
        comparison_data_points = InsightComparisonData.objects.filter(
            intervention=intervention_instance.intervention
        )
        if len(comparison_data_points) == 0:
            return []
        if not self.analysis.currency_code or self.analysis.currency_code == settings.ISO_CURRENCY_CODE:
            # This program is excluded from comparisons if the currency values don't match to avoid currency
            # conversion confusion
            if output_metric.output_as_currency:
                formatted_total_output = format_currency(
                    output_metric.total_output(**intervention_instance.parameters),
                    settings.ISO_CURRENCY_CODE,
                    locale=get_currency_locale(settings.ISO_CURRENCY_CODE),
                )
            else:
                formatted_total_output = (
                    f"{output_metric.total_output(**intervention_instance.parameters):,.2f}"
                )

            output_cost_all = self.analysis.output_costs[str(intervention_instance.id)][output_metric.id][
                "all"
            ]
            output_cost_direct_only = self.analysis.output_costs[str(intervention_instance.id)][
                output_metric.id
            ]["direct_only"]
            # This program is excluded from comparisons if the currency don't match.
            # This avoids currency conversion confusion.
            data = [
                {
                    "label": _("This Program"),
                    "grants": ", ".join(self.analysis.grants_list()),
                    "description": f"{output_metric.output_unit}: {formatted_total_output}",
                    "tooltip": self.analysis.title,
                    "output_cost_all": output_cost_all or "N/A",
                    "output_cost_direct_only": output_cost_direct_only or "N/A",
                    "raw_output_cost_all": output_cost_all,
                    "raw_output_cost_direct_only": output_cost_direct_only,
                    "highlight": True,
                },
            ]
        else:
            data = []
        for comparison_data_point in comparison_data_points:
            # We are by design using the default settings.ISO_CURRENCY_CODE instead of self.analysis.currency_code
            # to match the formatting on the _efficiency-comparison.html template, which used format_currency without
            # passing in a currency_override value
            if output_metric.output_as_currency:
                formatted_total_output = format_currency(
                    output_metric.total_output(**comparison_data_point.parameters),
                    settings.ISO_CURRENCY_CODE,
                    locale=get_currency_locale(settings.ISO_CURRENCY_CODE),
                )
            else:
                try:
                    formatted_total_output = (
                        f"{output_metric.total_output(**comparison_data_point.parameters):,.2f}"
                    )
                except (ValueError, TypeError):
                    # This is likely an InsightComparisonData that is missing parameters
                    formatted_total_output = "N/A"

            output_cost_all = comparison_data_point.output_costs.get(output_metric.id, {}).get("all", 0)
            if output_cost_all:
                output_cost_all = float(output_cost_all)
            else:
                output_cost_all = 0

            output_cost_direct_only = comparison_data_point.output_costs.get(output_metric.id, {}).get(
                "direct_only", 0
            )
            if output_cost_direct_only:
                output_cost_direct_only = float(output_cost_direct_only)
            else:
                output_cost_direct_only = 0

            data.append(
                {
                    "label": self._make_insights_chart_label(comparison_data_point.country.name),
                    "grants": ", ".join(comparison_data_point.grants_list()),
                    "description": f"{output_metric.output_unit}: {formatted_total_output}",
                    "tooltip": comparison_data_point.name,
                    "output_cost_all": output_cost_all or "N/A",
                    "output_cost_direct_only": output_cost_direct_only or "N/A",
                    "raw_output_cost_all": output_cost_all,
                    "raw_output_cost_direct_only": output_cost_direct_only,
                    "highlight": False,
                }
            )

        # Sort by output_cost_all/raw_output_cost_direct_only
        # If tied, sort by Grant
        data.sort(
            key=lambda x: (
                max(
                    [
                        x["raw_output_cost_all"],
                        x["raw_output_cost_direct_only"],
                    ]
                ),
                x["grants"],
            )
        )
        return data

    def _make_insights_chart_label(self, string):
        if len(string) > 25:
            break_index = self._insights_chart_label_find_break(string)
            if break_index is not None:
                return [
                    string[:break_index],
                    string[break_index:],
                ]
        return string

    def _insights_chart_label_find_break(self, string, start_index=0):
        index_of_space = string.find(" ", start_index)
        if index_of_space < 0:
            return None
        if index_of_space > 20:
            return index_of_space
        return self._insights_chart_label_find_break(string, index_of_space + 1)

    def _get_subcomponent_analysis_breakdown_data(self):
        chart_data = {}
        if self.workflow.get_step("allocate-subcomponent-costs").is_complete:
            chart_data = dict(
                zip(
                    self.analysis.subcomponent_cost_analysis.subcomponent_labels,
                    self.analysis.subcomponent_cost_analysis.cost_line_item_average(
                        exclude_support_costs=False
                    ),
                )
            )

        return {
            "chart_data": chart_data,
        }

    def _get_cost_breakdown_data(self, intervention_instance: InterventionInstance):
        data = []
        query_result = (
            self.analysis.cost_line_items.filter(
                config__allocations__intervention_instance=intervention_instance,
            )
            .values(
                "config__cost_type__name",
                "config__category__name",
                "config__analysis_cost_type",
            )
            .annotate(
                allocated_cost_sum=Coalesce(
                    Sum(F("total_cost") * (F("config__allocations__allocation") / Value(100))),
                    Decimal(0),
                )
            )
        )
        for item in query_result:
            if item["config__analysis_cost_type"] == AnalysisCostType.CLIENT_TIME:
                # Skip Client Time they live on the Other Costs table
                continue
            elif item["config__analysis_cost_type"] == AnalysisCostType.IN_KIND:
                # Skip In-Kind Contributions they live on the Other Costs table
                continue
            elif item["config__analysis_cost_type"] == AnalysisCostType.OTHER_HQ:
                data.append(
                    {
                        "cost_type_name": item["config__cost_type__name"],
                        "category_name": AnalysisCostType.get_pretty_analysis_cost_type(
                            item["config__analysis_cost_type"]
                        ),
                        "amount": item["allocated_cost_sum"],
                    }
                )
            else:
                data.append(
                    {
                        "cost_type_name": item["config__cost_type__name"] or "Support",
                        "category_name": item["config__category__name"] or "Other Supporting Costs",
                        "amount": item["allocated_cost_sum"],
                    }
                )

        # Sort by amount but we aren't done...
        data.sort(key=lambda x: x["amount"], reverse=True)

        total_cost = sum([d["amount"] for d in data])

        for d in data:
            if total_cost > 0:
                d["percent_of_total"] = float((d["amount"] / total_cost) * 100)
                d["percent_of_total_formatted"] = float(format(d["percent_of_total"], ".2f"))
            else:
                d["percent_of_total"] = 0
                d["percent_of_total_formatted"] = 0

        # ICR should never be in the top 5 for this pie chart so we'll remove it and
        #   make sure it ends up in the All Other Costs section
        icr_index = next(
            (index for (index, d) in enumerate(data) if d["category_name"] == "ICR"),
            None,
        )
        if icr_index is not None:
            icr_data = [data.pop(icr_index)]
        else:
            icr_data = []

        # Other Supporting Costs data should be lumped into the All Other Costs section
        other_index = next(
            (index for (index, d) in enumerate(data) if d["category_name"] == "Other Supporting Costs"),
            None,
        )
        if other_index is not None:
            other_supporting_data = [data.pop(other_index)]
        else:
            other_supporting_data = []

        chart_data = []
        for d in data[:5]:
            if d["percent_of_total_formatted"] < 1:
                d["percent_of_total_formatted"] = "< 1"
            elif d["percent_of_total_formatted"] >= 1:
                d["percent_of_total_formatted"] = round(d["percent_of_total_formatted"])

            chart_data.append(
                {
                    "label": f'{d["category_name"]} ({d["cost_type_name"]}) {d["percent_of_total_formatted"]}%',
                    "percent_of_total": float(format(d["percent_of_total"], ".2f")),
                }
            )

        remaining_percent = sum(
            map(
                lambda d: d["percent_of_total"],
                data[5:] + icr_data + other_supporting_data,
            )
        )
        remaining_percent_formatted = float(format(remaining_percent, ".2f"))
        if remaining_percent > 0:
            chart_data.append(
                {
                    "label": f'{"All other costs"} {round(remaining_percent_formatted)}%',
                    "percent_of_total": remaining_percent,
                }
            )

        # Move ICR and Other Supporting Costs back to where they were.
        data += icr_data
        data += other_supporting_data
        data.sort(key=lambda x: x["amount"], reverse=True)

        return {
            "total_cost": total_cost,
            "costs_by_cost_type_category": data,
            "chart_data": chart_data,
        }

    def _get_bar_chart_data(
        self,
        output_cost_all,
        output_cost_direct_only,
        output_cost_in_kind=0,
    ):
        output_cost_total = output_cost_all
        if self.analysis.in_kind_contributions:
            output_cost_total += output_cost_in_kind

        if output_cost_total:
            direct_percent = round((output_cost_direct_only / output_cost_total) * 100, 2)
            in_kind_percent = round((output_cost_in_kind / output_cost_total) * 100, 2)
        else:
            direct_percent = 0.0
            in_kind_percent = 0.0

        # So that the total is always exactly 100, even with rounding errors
        all_percent = round(100 - direct_percent - in_kind_percent, 2)

        currency_override = self.analysis.currency_code or settings.ISO_CURRENCY_CODE

        # Get the individual bar values for each type of cost
        formatted_direct_only = format_currency(
            output_cost_direct_only,
            currency_override,
            locale=get_currency_locale(currency_override),
        )
        formatted_total = format_currency(
            output_cost_all - output_cost_direct_only,
            currency_override,
            locale=get_currency_locale(currency_override),
        )
        if output_cost_in_kind:
            formatted_in_kind = format_currency(
                output_cost_in_kind,
                currency_override,
                locale=get_currency_locale(currency_override),
            )
        else:
            formatted_in_kind = ""
        # Get the aggregate values to be displayed on the Efficiency Card
        # Program, Program + Support + Indirect,  Program + Support + Indirect + In-Kind
        formatted_total_aggregate = format_currency(
            output_cost_all,
            currency_override,
            locale=get_currency_locale(currency_override),
        )
        formatted_in_kind_aggregate = format_currency(
            output_cost_all + output_cost_in_kind,
            currency_override,
            locale=get_currency_locale(currency_override),
        )

        # These key names are referenced within website/static/website/js/insights-charts.js
        # Please do not change them unless you update that file as well

        formatted_data = {
            "direct": {
                "aggregate": formatted_direct_only,
                "value": formatted_direct_only,
                "percent": direct_percent,
                "label": _("Program Costs Only"),
            },
            "total": {
                "aggregate": formatted_total_aggregate,
                "value": formatted_total,
                "percent": all_percent,
                "label": _(
                    f"""
                    Including Program Costs ({formatted_direct_only}), Support Costs and Indirect Costs 
                    ({formatted_total})
                    """
                ),
            },
        }
        # We only include this on interventions when it has a value.
        if formatted_in_kind:
            formatted_data["in_kind"] = {
                "aggregate": formatted_in_kind_aggregate,
                "value": formatted_in_kind,
                "percent": in_kind_percent,
                "label": _(
                    f"""
                                Including Program Costs ({formatted_direct_only}), Support Costs and Indirect Costs 
                                ({formatted_total}), In-Kind Contributions ({formatted_in_kind})
                                """
                ),
            }

        return formatted_data

    def _get_cost_model_table_paginator(self, intervention_instance: InterventionInstance):
        order_by = self.request.GET.get("order_by", None)
        if order_by not in [
            "total_cost",
            "-total_cost",
            "allocated_cost",
            "-allocated_cost",
        ]:
            order_by = "-allocated_cost"

        cost_line_items = (
            self.analysis.cost_line_items.filter(
                config__allocations__intervention_instance=intervention_instance
            )
            .exclude(config__analysis_cost_type__in=[AnalysisCostType.IN_KIND, AnalysisCostType.CLIENT_TIME])
            .annotate(allocated_cost=F("total_cost") * (F("config__allocations__allocation") / Value(100)))
            .order_by(order_by)
            .prefetch_related(
                "config__cost_type",
                "config__category",
                "config__allocations",
                "config__allocations__intervention_instance",
            )
        )

        paginator = Paginator(cost_line_items, self.dioptra_settings.paginate_by)
        return paginator

    def _get_other_cost_model_table_paginator(self, intervention_instance: InterventionInstance):
        ordering = ["config__analysis_cost_type", "budget_line_description"]
        order_by = self.request.GET.get("order_by", None)
        if order_by in [
            "total_cost",
            "-total_cost",
            "coalesced_allocation",
            "-coalesced_allocation",
            "allocated_cost",
            "-allocated_cost",
        ]:
            ordering.insert(0, order_by)

        cost_line_items = (
            self.analysis.cost_line_items.filter(
                config__analysis_cost_type__in=[
                    AnalysisCostType.IN_KIND,
                    AnalysisCostType.CLIENT_TIME,
                ]
            )
            .filter(config__allocations__intervention_instance=intervention_instance)
            .annotate(coalesced_allocation=Coalesce(F("config__allocations__allocation"), Decimal("100.00")))
            .annotate(allocated_cost=F("total_cost") * (F("coalesced_allocation") / Value(100)))
            .order_by(*ordering)
        )

        paginator = Paginator(cost_line_items, self.dioptra_settings.paginate_by)
        return paginator


class InsightsPrint(Insights):
    template_name = "analysis/insights-print.html"

    def get(self, request, *args, **kwargs):
        html_file = self._create_html_file(request)
        cmd = settings.PDF_EXPORT_COMMAND

        fd, pdf_file = tempfile.mkstemp()
        try:
            cmd_options = [
                "--headless",
                f"--print-to-pdf={pdf_file}",
                "--disable-gpu",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=10000",
                "--force-device-scale-factor=1",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                html_file,
            ]

            subprocess.check_call(cmd + cmd_options, timeout=600)

            response = HttpResponse(open(pdf_file, "rb"), content_type="application/pdf")
            response["Content-Disposition"] = 'attachment; filename="insights-report.pdf"'
        finally:
            os.remove(html_file)
            os.remove(pdf_file)
        return response

    def _create_html_file(self, request):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        html = render_to_string(self.template_name, context, request)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        with open(tmp.name, "w") as f:
            f.write(html)
        return tmp.name
