from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _l

from website.workflows._steps_base import Step


class Interventions(Step):
    name: str = "interventions"
    nav_title: str = _l("Interventions")

    @cached_property
    def is_complete(self) -> bool:
        if not (self.analysis and getattr(self.analysis, "pk", None)):
            return False
        if not self.analysis.interventioninstance_set.exists():
            return False
        return self.analysis.has_parameters()

    @cached_property
    def dependencies_met(self) -> bool:
        return self.workflow.get_step("define").is_complete

    def get_href(self) -> str | None:
        if getattr(self.analysis, "pk", None):
            return reverse("analysis-interventions", kwargs={"pk": self.analysis.pk})
        return None
