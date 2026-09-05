from urllib.parse import quote

from django.shortcuts import redirect
from django.utils.translation import gettext as _, gettext_lazy as _l
from django_filters.views import FilterView

from ombucore.admin.views import FilterMixin
from website.filterset import CategorizeCostTypeFilterSet
from website.models import (
    Category,
    CostLineItem,
    CostLineItemConfig,
    CostType,
)
from website.utils import group_by
from website.views.analysis.corrections import correction_urls
from website.views.mixins import (
    AnalysisPermissionRequiredMixin,
    AnalysisStepFiltersetMixin,
    PostActionHandlerMixin,
)


class CategorizeCostType(
    FilterMixin,
    AnalysisPermissionRequiredMixin,
    PostActionHandlerMixin,
    AnalysisStepFiltersetMixin,
    FilterView,
):
    step_name = "categorize"
    title = _l("Review & confirm all cost items in each category")
    help_text = _("")
    template_name = "analysis/categorize-cost_type.html"
    actions = [
        "save_cost_line_item_config",
        "confirm_cost_type_category",
        "confirm_cost_type_category_all",
    ]
    permission_required = "website.change_analysis"
    filterset_class = CategorizeCostTypeFilterSet
    model = CostLineItem

    def setup_step(self):
        super().setup_step()

        self.cost_type_choices = [(cost_type.id, cost_type.name) for cost_type in CostType.objects.all()]
        self.category_choices = [(category.id, category.name) for category in Category.objects.all()]

        self.step = None
        for substep in self.parent_step.steps:
            encoded_request_path = quote(self.request.path)
            if substep.get_href() == encoded_request_path:
                self.step = substep
                break

    def modify_queryset(self, queryset):
        return (
            queryset.filter(
                analysis_id=self.object.id,
            )
            .select_related("config")
            .order_by(
                "grant_code",
                "budget_line_description",
                "site_code",
                "sector_code",
                "account_code",
            )
            # Do NOT prefetch transactions here, we need to load them on-demand or it's very slow.
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cost_line_items = list(self.object_list)
        grouped_cost_line_items = group_by(
            cost_line_items, lambda c: (c.config.cost_type_id, c.config.category_id)
        )
        cost_type_categories = self.analysis.cost_type_categories.filter(
            cost_type=self.step.cost_type
        ).select_related("cost_type", "category")
        sc_cost_line_items = list()
        for sc in cost_type_categories:
            sc_cost_line_items.append(
                (sc, grouped_cost_line_items.get((sc.cost_type_id, sc.category_id), []))
            )
        unconfirmed_count = cost_type_categories.filter(confirmed=False).count()

        context.update(
            {
                "cost_type_categories": cost_type_categories,
                "cost_type_category_items": sc_cost_line_items,
                "unconfirmed_count": unconfirmed_count,
                "cost_type_choices": self.cost_type_choices,
                "category_choices": self.category_choices,
            }
        )
        # Feature 91 edit entry points; ``cost_type`` lets a panel redirect when this table empties.
        context.update(correction_urls(self.analysis, "categorize", cost_type=self.step.cost_type))

        return context

    def get_context_data_old(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cost_type_categories = self.analysis.cost_type_categories.filter(
            cost_type=self.step.cost_type
        ).select_related("cost_type", "category")
        unconfirmed_count = cost_type_categories.filter(confirmed=False).count()
        context.update(
            {
                "cost_type_categories": cost_type_categories,
                "unconfirmed_count": unconfirmed_count,
                "cost_type_choices": self.cost_type_choices,
                "category_choices": self.category_choices,
            }
        )
        if len(self.parent_step.steps) and self.step == self.parent_step.steps[-1]:
            if not all([step.is_complete for step in self.parent_step.steps]):
                context.update(
                    {
                        "next_message": _(
                            "You must finish confirming all cost_types/categories before moving on."
                        ),
                    }
                )
        return context

    def handle_save_cost_line_item_config(self, request, *args, **kwargs):
        config = CostLineItemConfig.objects.get(pk=int(request.POST.get("config_id")))
        cost_type = CostType.objects.get(pk=int(request.POST.get("cost_type_id")))
        category = Category.objects.get(pk=int(request.POST.get("category_id")))

        # Verify config's cost line item is part of this analysis.
        if config.cost_line_item.analysis_id == self.analysis.id:
            previous_cost_type_id = config.cost_type.id
            config.cost_type = cost_type
            config.category = category
            config.save()

            # Add any missing cost_type category objects.
            cost_type_category_ids_added = self.analysis.ensure_cost_type_category_objects()

            # Mark any newly added cost_type category objects as "confirmed".
            self.analysis.cost_type_categories.filter(id__in=cost_type_category_ids_added).update(
                confirmed=True
            )

            self.workflow.invalidate_step("insights")
            self.workflow.calculate_if_possible()

            # If the previous cost_type is no longer used, return a redirect to
            # the newly assigned cost_type.
            if self.analysis.cost_type_categories.filter(cost_type__id=previous_cost_type_id).count() == 0:
                next_step = self.parent_step.get_step_by_cost_type(cost_type)
                if next_step:
                    return redirect(next_step.get_href())
                else:
                    return redirect(self.parent_step.get_href())
            return None

    def handle_confirm_cost_type_category(self, request, *args, **kwargs):
        cost_type_category = self.analysis.cost_type_categories.get(
            pk=int(request.POST.get("cost_type_category_id"))
        )
        cost_type_category.confirmed = True
        cost_type_category.save()
        self.workflow.calculate_if_possible()

    def handle_confirm_cost_type_category_all(self, request, *args, **kwargs):
        cost_type_categories = (
            self.analysis.cost_type_categories.filter(cost_type=self.step.cost_type)
            .select_related("cost_type", "category")
            .all()
        )
        for cost_type_category in cost_type_categories:
            cost_type_category.confirmed = True
            cost_type_category.save()
        self.workflow.calculate_if_possible()
