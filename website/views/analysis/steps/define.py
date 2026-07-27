from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _l
from django.views.generic import CreateView, UpdateView

from website.app_log import loggers as app_loggers
from website.forms.analysis import DefineForm
from website.views.mixins import AnalysisObjectMixin, AnalysisPermissionRequiredMixin, AnalysisStepMixin
from website.workflows import AnalysisWorkflow


class DefineCreate(PermissionRequiredMixin, AnalysisStepMixin, CreateView):
    step_name = "define"
    form_class = DefineForm
    title = _l("Define the details of this analysis")
    help_text = _l("Enter the details of the analysis you wish to create. ")
    template_name = "analysis/define.html"
    permission_required = "website.add_analysis"

    def setup_step(self):
        self.workflow = AnalysisWorkflow(analysis=None)
        self.step = self.workflow.get_step(self.step_name)
        self.parent_step = self.workflow.get_step(self.step_name)

    def get_success_url(self):
        return reverse("analysis-define-update", kwargs={"pk": self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        app_loggers.log_analysis_created(self.object, self.request.user)
        return response


class DefineUpdate(AnalysisStepMixin, AnalysisObjectMixin, AnalysisPermissionRequiredMixin, UpdateView):
    step_name = "define"
    form_class = DefineForm
    title = _l("Define the details of this analysis")
    help_text = _l("Enter the details of the analysis you wish to create.")
    template_name = "analysis/define.html"
    permission_required = "website.change_analysis"

    def get_form_kwargs(self, **kwargs):
        kwargs = super().get_form_kwargs(**kwargs)
        kwargs["data_loaded"] = self.workflow.get_step("load-data").is_complete
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Save the form model.
        self.object = form.save()
        app_loggers.log_analysis_updated(self.object, self.request.user)

        # Re-initialize the workflow so the references to the analysis are correct.
        self.setup_step()

        # Invalidate the insights, try to recalculate.
        self.workflow.invalidate_step("insights")
        self.workflow.calculate_if_possible()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.request.path
