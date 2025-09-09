from __future__ import annotations

from django.urls import reverse
from django.utils.functional import cached_property

from website.workflows._steps_base import MultiStep, SubStep


class AddOtherCostsSubStep(SubStep):
    cost_type: int | None = None  # Implement on Subclass
    parent: MultiStep | None = None

    @cached_property
    def dependencies_met(self) -> bool:
        return self.parent.dependencies_met

    @cached_property
    def is_complete(self) -> bool:
        return self.cost_line_items.exists()

    def get_href(self) -> str:
        return reverse(
            "analysis-add-other-costs-detail",
            kwargs={"pk": self.analysis.pk, "cost_type": int(self.cost_type)},
        )

    def get_define_href(self) -> str:
        return reverse(
            "analysis-define-update",
            kwargs={
                "pk": self.analysis.pk,
            },
        )
