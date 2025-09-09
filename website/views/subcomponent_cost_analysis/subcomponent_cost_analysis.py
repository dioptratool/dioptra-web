from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _l
from django.views.generic import DetailView

from ombucore.admin import panel_commands as commands
from ombucore.admin.views.base import FormView
from website.forms.subcomponent import (
    EditSubcomponentCostAnalysisLabelsForm,
    EditSubcomponentLabelForm,
)
from website.models import Analysis, SubcomponentCostAnalysis
from website.workflows import AnalysisWorkflow


class SubcomponentCostAnalysisDetailView(LoginRequiredMixin, DetailView):
    model = Analysis

    def get(self, request, *args, **kwargs):
        self.analysis = self.get_object()
        self.subcomponent_cost_analysis = self.analysis.subcomponent_cost_analysis

        workflow = AnalysisWorkflow(analysis=self.analysis)
        step = workflow.get_last_incomplete_or_last(skip_final=True)

        return redirect(step.get_href())


class EditSubcomponents(PermissionRequiredMixin, FormView):
    permission_required = "website.change_analysis"
    form_class = EditSubcomponentCostAnalysisLabelsForm
    supertitle = _l("Edit")
    title = _l("Sub-component Labels")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.subcomponent_analysis = get_object_or_404(
            SubcomponentCostAnalysis,
            pk=self.kwargs.get("subcomponent_pk"),
        )
        kwargs["instance"] = self.subcomponent_analysis
        return kwargs

    def form_valid(self, form):
        form.save(commit=True)
        workflow = AnalysisWorkflow(analysis=self.subcomponent_analysis.analysis)
        workflow.invalidate_step("confirm-subcomponents")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "subcomponent-cost-analysis-create",
            kwargs={"pk": self.subcomponent_analysis.analysis.pk},
        )

    def get_success_commands(self):
        return [
            commands.CloseCurrentAndRedirectOpener(self.get_success_url()),
        ]


class EditSubcomponentsLimited(EditSubcomponents):
    title = _l("Sub-component Labels")

    def form_valid(self, form):
        # We do not use the EditSubcomponents.form_valid which invalidates the whole
        #  Subcomponent step.  Instead we use the .form_valid() from it's parent class
        form.save(commit=True)
        return FormView.form_valid(self, form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["prevent_add_remove"] = True
        return kwargs


class EditSubcomponentLabel(PermissionRequiredMixin, FormView):
    permission_required = "website.change_analysis"
    form_class = EditSubcomponentLabelForm
    supertitle = _l("Edit")
    title = _l("Sub-component Labels")

    def get(self, request, *args, **kwargs):
        self.initial = kwargs
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.old_label = kwargs.get("label")
        if new_label := request.POST.get("label"):
            kwargs["label"] = new_label
            self.new_label = new_label
        else:
            self.new_label = self.old_label
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        if "data" in kwargs:
            new_label = kwargs["data"]["label"]
            self.initial["label"] = new_label

        kwargs["initial"].update(self.initial)

        return kwargs

    def get_success_commands(self):
        return [
            commands.Resolve({"old_label": self.old_label, "new_label": self.new_label}),
        ]
