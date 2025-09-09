from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic import DetailView

from website.views.mixins import (
    AnalysisPermissionRequiredMixin,
    AnalysisStepMixin,
)


class Categorize(AnalysisPermissionRequiredMixin, AnalysisStepMixin, DetailView):
    """
    Redirects to the first cost_type to confirm categories.
    """

    step_name = "categorize"
    permission_required = "website.change_analysis"
    title = ""
    help_text = _("")

    def get(self, request, *args, **kwargs):
        """
        Return redirect to first CostType to categorize.
        """
        return redirect(self.step.steps[0].get_href())
