from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _l
from django.views.generic import UpdateView

from website.forms.subcomponent import ConfirmSubcomponentCostAnalysisForm
from website.models import SubcomponentCostAnalysis
from website.views.mixins import AnalysisStepMixin


class ConfirmSubcomponentsCreate(
    PermissionRequiredMixin,
    AnalysisStepMixin,
    UpdateView,
):
    form_class = ConfirmSubcomponentCostAnalysisForm
    help_text = _l("")
    template_name = "subcomponent-cost-analysis/confirm-subcomponents.html"
    permission_required = "website.change_analysis"
    step_name = "confirm-subcomponents"
    title = _l("Confirm sub-component labels")

    def setup_step(self):
        super().setup_step()
        self.step.page_title = "Confirm sub-components"
        SubcomponentCostAnalysis.objects.get_or_create(analysis=self.analysis)
        self.subcomponent_cost_analysis = self.analysis.subcomponent_cost_analysis

    def get_success_url(self):
        return reverse(
            "subcomponent-cost-analysis",
            kwargs={
                "subcomponent_pk": self.analysis.subcomponent_cost_analysis.pk,
                "pk": self.analysis.pk,
            },
        )

    def dispatch(self, request, *args, **kwargs):
        if not self.has_permission():
            return self.handle_no_permission()
        if not self.step.dependencies_met:
            return redirect(
                reverse(
                    "analysis-insights",
                    kwargs={
                        "pk": self.analysis.pk,
                    },
                )
            )
        if not self.step:
            return redirect(
                reverse(
                    "subcomponent-cost-analysis",
                    kwargs={
                        "subcomponent_pk": self.analysis.subcomponent_cost_analysis.pk,
                        "pk": self.analysis.pk,
                    },
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subcomponent_cost_analysis"] = self.subcomponent_cost_analysis
        return context
