from decimal import Decimal

from babel.numbers import format_currency
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from website.currency import get_currency_locale
from website.models import CostEfficiencyStrategy, InsightComparisonData, Intervention
from website.models.output_metric import OutputMetric


class InterventionInsights(LoginRequiredMixin, DetailView):
    model = Intervention
    template_name = "insights/insight.html"
    context_object_name = "intervention"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["output_metrics"] = []
        for output_metric in self.object.output_metric_objects():
            context["output_metrics"].append(
                {
                    "output_metric": output_metric,
                    "insights_chart_data": self._get_insights_chart_data(output_metric),
                }
            )
        context["cost_efficiency_strategies"] = CostEfficiencyStrategy.objects.filter(
            interventions=self.object
        )
        context["show_cost_efficiency_comparison"] = any(
            [output_metric["insights_chart_data"] for output_metric in context["output_metrics"]]
        )
        return context

    def _get_insights_chart_data(self, output_metric: OutputMetric):
        comparison_data_points = InsightComparisonData.objects.filter(intervention=self.object)
        if len(comparison_data_points) == 0:
            return None

        data = []

        for comparison_data_point in comparison_data_points:
            if output_metric.output_as_currency:
                formatted_total_output = format_currency(
                    output_metric.total_output(**comparison_data_point.parameters),
                    settings.ISO_CURRENCY_CODE,
                    locale=get_currency_locale(settings.ISO_CURRENCY_CODE),
                )
            else:
                value = output_metric.total_output(**comparison_data_point.parameters)
                if value is None:
                    formatted_total_output = "N/A"
                else:
                    formatted_total_output = f"{float(value):,.2f}"

            # TODO This check is done because Insight Comparison Data may be missing certain Output Metric Parameters.
            #  The internal structure of the Output Metric Parameters should be refactored to be more robust.
            if output_metric.id in comparison_data_point.output_costs:
                output_cost_all = comparison_data_point.output_costs[output_metric.id]["all"]
                output_cost_direct_only = comparison_data_point.output_costs[output_metric.id]["direct_only"]
            else:
                output_cost_all = None
                output_cost_direct_only = None

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
                }
            )
        # Sort by output_cost_all/raw_output_cost_direct_only
        # If tied, sort by Grant
        data.sort(
            key=lambda x: (
                max(
                    [
                        Decimal(x["raw_output_cost_all"] or 0) or 0,
                        Decimal(x["raw_output_cost_direct_only"] or 0) or 0,
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
