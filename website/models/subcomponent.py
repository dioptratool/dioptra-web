import json
from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from website.betterdb import bulk_update_dicts
from website.models import CostLineItem, CostLineItemConfig
from website.models.field_types import SubcomponentLabelsType
from website.models.fields import TypedJsonField
from .category import Category
from .cost_type import CostType, Indirect, ProgramCost, Support


class SubcomponentCostAnalysis(models.Model):
    analysis = models.OneToOneField(
        "website.Analysis",
        verbose_name=_("Analysis"),
        on_delete=models.CASCADE,
        related_name="subcomponent_cost_analysis",
    )

    subcomponent_labels = TypedJsonField(
        typed_json=SubcomponentLabelsType,
        default=list,
        blank=True,
        null=True,
    )

    subcomponent_labels_confirmed = models.BooleanField(default=False)
    cloned_from = models.ForeignKey(
        "website.SubcomponentCostAnalysis",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("Subcomponent Cost Analysis")
        verbose_name_plural = _("Subcomponent Cost Analyses")

    def __str__(self):
        return f"Subcomponent Analysis for {self.analysis.title}"

    def save(self, *args, **kwargs):
        if not self.pk and not self.subcomponent_labels:
            all_labels = []
            for intervention in self.analysis.interventions.all():
                all_labels += intervention.subcomponent_labels
            self.subcomponent_labels = all_labels
        super().save(*args, **kwargs)

    def allocated_totals(self):
        subcomponent_allocations = []
        for each_cost_item in self.analysis.cost_line_items.all():
            if not each_cost_item.config.subcomponent_analysis_allocations:
                continue
            if each_cost_item.config.subcomponent_analysis_allocations_skipped:
                continue

            # Get the value of each subcomponent allocation
            subcomponent_allocations.append(
                [
                    Decimal(v) / 100 * each_cost_item.allocated_cost_on_model
                    for v in each_cost_item.config.subcomponent_analysis_allocations.values()
                ]
            )

        # Add up all the subcomponents of the same type
        # This return a list of totals for Each Subcomponent Label
        return [round(float(sum(col)), 4) for col in zip(*subcomponent_allocations)]

    def cost_line_item_average(
        self,
        cost_type: CostType | None = None,
        category: Category | None = None,
        grant: str | None = None,
        exclude_support_costs: bool = True,
    ) -> list[Decimal]:
        """
        This is not the average of the percentages of the Subcomponent analysis but instead the sum of costs
          for each subcomponent as a percentage of the whole subcomponent cost.

          This is a subtle and important distinction.

          There is also hard capped at 100.   Any remainder from rounding/floats/etc is add/subtracted from the last item.
        """
        subcomponent_allocations = []
        total_cost_for_clis_with_subcomponent_value = 0
        each_cost_item: CostLineItem
        for each_cost_item in self.analysis.cost_line_items.cost_type_category_items():
            if not each_cost_item.config.subcomponent_analysis_allocations:
                continue
            if cost_type is not None and each_cost_item.config.cost_type != cost_type:
                continue
            if category is not None and each_cost_item.config.category != category:
                continue
            if grant is not None and each_cost_item.grant_code != grant:
                continue

            if each_cost_item.config.subcomponent_analysis_allocations_skipped:
                continue

            if each_cost_item.config.cost_type and each_cost_item.config.cost_type.type == Indirect.id:
                continue

            if (
                exclude_support_costs
                and each_cost_item.config.cost_type
                and each_cost_item.config.cost_type.type == Support.id
            ):
                continue

            subcomponent_allocations.append(
                [
                    (Decimal(allocation_percentage) / 100) * each_cost_item.allocated_cost_on_model
                    for allocation_percentage in each_cost_item.config.subcomponent_analysis_allocations.values()
                ]
            )
            total_cost_for_clis_with_subcomponent_value += each_cost_item.allocated_cost_on_model

        # Add up all the subcomponents of the same type and then divide them with the total of the Cost Line Items
        # This return a list of Average Percentages for Each Subcomponent Label
        # Percentages are returned as floats from 0-100 for display
        averages = []
        for col in zip(*subcomponent_allocations):
            if sum(col) > 0:
                averages.append(
                    round(
                        Decimal(sum(col) / total_cost_for_clis_with_subcomponent_value) * 100,
                        2,
                    )
                )
            else:
                averages.append(0)

        # This value cannot be over/under 100 so in the case where it might be we remove the extra from the last item
        if averages and sum(averages) != 100:
            averages[-1] += 100 - sum(averages)

        return averages

    def calculate_and_apply_allocations_to_shared_costs_and_skipped_items(self):
        empty_shared_cost_line_items = (
            self.analysis.cost_line_items.exclude(
                config__cost_type__type=ProgramCost().id,
            )
            .filter(
                Q(config__subcomponent_analysis_allocations={})
                | Q(config__subcomponent_analysis_allocations__isnull=True),
            )
            .all()
        )

        skipped_cost_line_items = self.analysis.cost_line_items.filter(
            config__subcomponent_analysis_allocations_skipped=True
        ).all()

        cost_line_item_updates = []
        for cli in empty_shared_cost_line_items.union(skipped_cost_line_items):
            if cli.config.id:
                new_cli_info = {
                    "id": cli.config.id,
                    "subcomponent_analysis_allocations": json.dumps(
                        dict(enumerate(map(str, self.cost_line_item_average())))
                    ),
                    "subcomponent_analysis_allocations_skipped": False,
                }
                cost_line_item_updates.append(new_cli_info)

        bulk_update_dicts(
            model_cls=CostLineItemConfig,
            dicts=cost_line_item_updates,
            pk="id",
            value_template="(%s,CAST(%s AS jsonb),%s)",
        )

    def reset_cost_line_items(self):
        bulk_update_dicts(
            model_cls=CostLineItemConfig,
            dicts=[
                {
                    "id": cli.config.id,
                    "subcomponent_analysis_allocations": [],
                    "subcomponent_analysis_allocations_skipped": False,
                }
                for cli in self.analysis.cost_line_items.all()
                if cli.config.id
            ],
            pk="id",
            value_template="(%s,CAST(%s AS jsonb),%s)",
        )
