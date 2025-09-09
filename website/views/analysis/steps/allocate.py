from decimal import Decimal
from urllib.parse import quote

from django.db.models import Q
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic import DetailView
from django_filters.views import FilterView

from ombucore.admin.views import FilterMixin
from website.filterset import AllocateCostTypeGrantSiteFilterSet
from website.models import CostLineItem
from website.models import InterventionInstance
from website.models.cost_type import Indirect, ProgramCost, Support
from website.views.mixins import (
    AllocateMixin,
    AnalysisPermissionRequiredMixin,
    AnalysisStepDetailMixin,
    AnalysisStepFiltersetMixin,
    AnalysisStepMixin,
)


class Allocate(AnalysisPermissionRequiredMixin, AnalysisStepDetailMixin):
    """
    Redirects to the first cost_type/grant to allocate.
    """

    step_name = "allocate"
    permission_required = "website.change_analysis"
    title = ""
    help_text = _("")

    def get(self, request, *args, **kwargs):
        """
        Return redirect to first CostType to categorize.
        """
        if len(self.step.steps):
            return redirect(self.step.steps[0].get_href())
        else:
            return redirect(self.workflow.get_next(self.step).get_href())


class AllocateSupportingCosts(AnalysisPermissionRequiredMixin, AnalysisStepMixin, AllocateMixin, DetailView):
    step_name = "allocate"
    help_text = _(
        'Allocate all Cost Items assigned to "special countries" that '
        "are marked to be included in every analysis"
    )
    template_name = "analysis/allocate-cost_type-grant.html"
    permission_required = "website.change_analysis"
    title = ""

    def setup_step(self):
        super().setup_step()
        self.grant_code = self.kwargs.get("grant")

        supporting_step = next(
            (
                substep
                for substep in self.parent_step.steps
                if substep.name == "allocate-supporting-costs" and substep.grant_code == self.grant_code
            ),
            None,
        )
        if supporting_step:
            self.step = supporting_step
        else:
            self.step = self.parent_step.steps[0]

        self.special_cost_line_items = [
            c for c in self.analysis.special_country_cost_line_items if c.grant_code == self.grant_code
        ]

        self.special_cost_line_items = sorted(
            self.special_cost_line_items, key=lambda cli: cli.budget_line_description
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["cost_line_items_count"] = len(self.special_cost_line_items)
        context["grant"] = self.grant_code
        context["special_cost_line_items"] = self.special_cost_line_items
        context["title"] = _("How much did Other Supporting Costs contribute to each intervention?")

        # Calculator context values
        context["show_special_calculator"] = True
        grant_proportions = self.calc_grant_proportion()
        country_proportions = self.calc_country_proportion()
        suggested_allocation = None
        if grant_proportions and country_proportions:
            suggested_allocation = grant_proportions * country_proportions

        context["grant_proportions"] = f"{grant_proportions:.2%}" if grant_proportions else None
        context["country_proportions"] = f"{country_proportions:.2%}" if country_proportions else None
        context["suggested_allocation"] = suggested_allocation * 100 if suggested_allocation else None
        context["other_suggested_allocation"] = (
            f"{suggested_allocation:.2%}" if suggested_allocation else None
        )

        return context

    def post(self, request, *args, **kwargs):
        data = self._get_cost_line_item_ids_and_allocations_from_post(request)
        data, errors = self._validate_data(data)
        if len(errors):
            context = self.get_context_data(errors=errors)
            self._clear_fields_needing_help(errors)

            # We should attempt to save the items that were not in error
            good_data = {key: data[key] for key in data if key not in errors}
            if good_data:
                self._save_data(good_data)

            return self.render_to_response(context)
        else:
            self._save_data(data)
            self.workflow.invalidate_step("insights")
            self.workflow.calculate_if_possible()
        query = f"?{request.GET.urlencode()}" if request.GET else ""
        return redirect(self.request.path + query)

    def _line_item_ids_needing_help(self, errors):
        error_line_ids = []
        for line_id, error_message in errors.items():
            if error_message == "Not a number":
                error_line_ids.append(line_id)
        return error_line_ids

    def calc_grant_proportion(self):
        total, cost = 0, 0

        for line_item in (
            self.analysis.cost_line_items.cost_type_category_items()
            .filter(
                grant_code=self.grant_code,
            )
            .filter(Q(config__cost_type__type=ProgramCost.id) | Q(config__cost_type__type=Support.id))
        ):
            total += line_item.total_cost

        for line_item in (
            self.analysis.cost_line_items.filter(
                grant_code=self.grant_code,
            )
            .filter(Q(config__cost_type__type=ProgramCost.id) | Q(config__cost_type__type=Support.id))
            .cost_type_category_items()
        ):
            for each_allocation in line_item.config.allocations.all():
                if each_allocation.allocation:
                    allocation_percent = each_allocation.allocation / Decimal(100)
                    cost += line_item.total_cost * allocation_percent

        if not total:
            return None
        return Decimal(cost / total)

    def calc_country_proportion(self):
        standard_cost_lines_cost = sum(
            list(
                self.analysis.cost_line_items.cost_type_category_items()
                .filter(grant_code=self.grant_code)
                .values_list("total_cost", flat=True)
            )
        )
        all_cost_lines_cost = sum(
            list(
                self.analysis.cost_line_items.filter(grant_code=self.grant_code).values_list(
                    "total_cost", flat=True
                )
            )
        )

        # When initially loading data for an Analysis, we aggregate the cost of ALL transactions, even those that are
        # filtered out by now due to a non-matching country.  This total value should always be the highest value among
        # all other cost values in this method
        total_transaction_cost = self.analysis.get_all_transactions_total_cost(self.grant_code)
        if total_transaction_cost is None:
            return None

        total_non_stored_cost = max(total_transaction_cost - all_cost_lines_cost, 0)

        cost_denom = standard_cost_lines_cost + total_non_stored_cost
        if not cost_denom:
            return 0

        return standard_cost_lines_cost / cost_denom

    def _save_data(self, data):
        for cost_line_item_id, allocation in data.items():
            cost_line_item = self.analysis.cost_line_items.get(pk=cost_line_item_id)
            cost_line_item.config.allocation = allocation
            cost_line_item.config.save()


class AllocateCostTypeGrant(
    FilterMixin,
    AnalysisPermissionRequiredMixin,
    AnalysisStepFiltersetMixin,
    AllocateMixin,
    FilterView,
):
    step_name = "allocate"
    template_name = "analysis/allocate-cost_type-grant.html"
    permission_required = "website.change_analysis"
    model = CostLineItem
    filterset_class = AllocateCostTypeGrantSiteFilterSet
    title = ""
    help_text = _("")

    def setup_step(self):
        super().setup_step()
        self.step = None
        for substep in self.parent_step.steps:
            encoded_request_path = quote(self.request.path)
            if substep.get_href() == encoded_request_path:
                self.step = substep
                break

        self.cost_type_category_grants = (
            self.analysis.cost_type_category_grants.filter(
                cost_type_category__cost_type=self.step.cost_type,
                grant=self.step.grant,
            )
            .select_related(
                "cost_type_category",
                "cost_type_category__category",
            )
            .prefetch_related(
                "cost_type_category__analysis__unfiltered_cost_line_items",
                "cost_type_category__analysis__unfiltered_cost_line_items__config__allocations",
            )
            .distinct()
        )

    def modify_queryset(self, queryset):
        return (
            queryset.filter(
                analysis_id=self.object.id,
                config__cost_type=self.step.cost_type,
                grant_code=self.step.grant,
            )
            .select_related("config", "config__cost_type")
            .prefetch_related(
                "transactions",
                "config",
                "config__allocations",
                "config__category",
                "config__allocations__intervention_instance",
            )
            .order_by(
                "grant_code",
                "budget_line_description",
                "site_code",
                "sector_code",
                "account_code",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        cost_line_items_count = 0
        for cost_type_category_grant in self.cost_type_category_grants:
            cost_line_items_count += cost_type_category_grant.get_cost_line_items().count()

        context.update(
            {
                "cost_line_items_count": cost_line_items_count,
                "cost_type_category_grants": self.cost_type_category_grants,
                "title": _("How much did each cost item contribute to intervention being analyzed?"),
            }
        )

        self.filterset.form.fields["site_code"].choices = (
            self.object.site_codes_choices_from_cost_line_items()
        )

        context["suggested_allocation_calculations"] = {}
        if self.step.cost_type.type_obj().shared:
            suggested_allocations = self.analysis.get_suggested_allocations()
            for intervention_instance in self.analysis.interventioninstance_set.all():
                (
                    numerator,
                    denominator,
                    suggested_allocation,
                ) = (
                    suggested_allocations.get(self.step.cost_type.id, {})
                    .get(self.step.grant, {})
                    .get(intervention_instance)
                )

                context["suggested_allocation_calculations"][intervention_instance] = {
                    "suggested_allocation_numerator": numerator,
                    "suggested_allocation_denominator": denominator,
                    "suggested_allocation": suggested_allocation,
                }

                existing_allocation_obj = (
                    self.cost_type_category_grants.first()
                    .get_cost_line_items()
                    .first()
                    .config.allocations.filter(intervention_instance=intervention_instance)
                ).first()
                if (
                    suggested_allocation
                    and existing_allocation_obj
                    and existing_allocation_obj.allocation
                    and f"{suggested_allocation:.2f}" != f"{existing_allocation_obj.allocation:.2f}"
                    and isinstance(self.step.cost_type.type_obj(), Indirect)
                ):
                    context.update(
                        {
                            "next_message": _(
                                "The suggested indirect costs allocation has changed since this step was last completed. "
                                'Click "Save Suggested %" to update this analysis\' calculations with the updated '
                                "suggested percentage."
                            ),
                        }
                    )
        if (
            "next_message" not in context
            and self.step.get_next()
            and not self.step.get_next().dependencies_met
        ):
            context.update(
                {
                    "next_message": _(
                        "You must finish setting the allocation for all cost items before moving on."
                    ),
                }
            )

        return context

    def post(self, request, *args, **kwargs):
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)
        self.object_list = self.modify_queryset(self.filterset.qs)
        data = self._get_cost_line_item_ids_and_allocations_from_post(request)
        data, errors = self._validate_data(data)
        if len(errors):
            context = self.get_context_data(errors=errors)
            self._clear_fields_needing_help(errors)
            line_items_needing_help = self._line_item_objects_needing_help(errors)
            for grant in self.cost_type_category_grants:
                if grant.all_errors():
                    # set context for calculator
                    context["item_totals"] = self.calc_item_totals()
                    context["item_costs"] = self.calc_item_costs()
                    context["all_errors_suggest"] = self.calc_all_errors_suggest()

                for line in line_items_needing_help:
                    if line in grant.get_cost_line_items():
                        grant.show_allocation_calculator = True

            # We should attempt to save the items that were not in error
            good_data = {key: data[key] for key in data if key not in errors}
            if good_data:
                self._save_data(good_data)

            return self.render_to_response(context)
        else:
            self._save_data(data)
            self.workflow.invalidate_step("insights")
            self.workflow.calculate_if_possible()
        query = f"?{request.GET.urlencode()}" if request.GET else ""
        return redirect(self.request.path + query)

    def _line_item_objects_needing_help(self, errors):
        error_lines = []
        for cost_line_item_id, intervention_allocations_error_messages in errors.items():
            for (
                intervention_id,
                error_message,
            ) in intervention_allocations_error_messages.items():
                if intervention_id == "all":
                    c = CostLineItem.objects.get(id=cost_line_item_id)
                    error_lines.append(c)

                if error_message == "Not a number":
                    c = CostLineItem.objects.get(id=cost_line_item_id)
                    error_lines.append(c)
        return error_lines

    def calc_item_totals(self):
        total = 0
        for grant in self.cost_type_category_grants:
            for line_item in grant.get_cost_line_items():
                allocated_total = 0
                for a in line_item.config.allocations.all():
                    if a.allocation is not None:
                        allocated_total += a.allocation

                if allocated_total == 0:
                    total += line_item.total_cost

        return total

    def calc_item_costs(self):
        cost = 0
        for grant in self.cost_type_category_grants:
            for line_item in grant.get_cost_line_items():
                if line_item.config.allocations.count():
                    allocation_percent = 0
                    for a in line_item.config.allocations.all():
                        if a.allocation is not None:
                            allocation_percent += a.allocation

                    allocation_percent *= Decimal(0.01)
                    cost += line_item.total_cost * allocation_percent

        return cost

    def calc_all_errors_suggest(self):
        if self.calc_item_totals() != 0:
            allocation = self.calc_item_costs() / self.calc_item_totals()
            return f"{allocation:.2%}"

    def _save_data(self, data):
        for cost_line_item_id, intervention_allocations in data.items():
            for intervention_instance_id, allocation in intervention_allocations.items():
                cost_line_item: CostLineItem = self.analysis.cost_line_items.get(pk=cost_line_item_id)
                cost_line_item.set_allocation_for_intervention(
                    intervention_instance=InterventionInstance.objects.get(pk=intervention_instance_id),
                    allocation=allocation,
                )
