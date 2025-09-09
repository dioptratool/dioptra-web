from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _l

from website.workflows._steps_base import Step


class Define(Step):
    """
    Both the Create and Update, Analysis isn't saved yet if it's create.
    """

    name: str = "define"
    nav_title: str = _l("Define Analysis")

    @cached_property
    def is_complete(self) -> bool:
        if hasattr(self.analysis, "pk"):
            if self.analysis.has_parameters():
                return True
        return False

    @cached_property
    def dependencies_met(self) -> bool:
        return True

    def get_href(self) -> str:
        if getattr(self.analysis, "pk", False):
            return reverse("analysis-define-update", kwargs={"pk": self.analysis.pk})
        else:
            return reverse("analysis-define-create")
