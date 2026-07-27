from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _l
from django.views.generic import TemplateView

from ombucore.admin import panel_commands as commands
from ombucore.admin.views import FormView as PanelsFormView
from website.currency import currency_code
from website.forms.analysis import (
    SubcomponentLabelEditForm,
    SubcomponentLabelsDeleteConfirmForm,
    SubcomponentLabelsForm,
)
from website.models import Analysis, InterventionInstance
from website.models.utils import intervention_parameters_display
from website.views.mixins import AnalysisObjectMixin, AnalysisPermissionRequiredMixin, AnalysisStepMixin
from website.workflows import AnalysisWorkflow
from website.workflows.utils import recalculate_analysis


class Interventions(AnalysisPermissionRequiredMixin, AnalysisStepMixin, AnalysisObjectMixin, TemplateView):
    step_name = "interventions"
    title = _l("Interventions")
    help_text = _l("Create the interventions being analyzed and their sub-components.")
    template_name = "analysis/interventions.html"
    permission_required = "website.change_analysis"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        labels_locked = self.workflow.get_step("load-data").is_complete
        context["labels_locked"] = labels_locked
        context["currency"] = currency_code(analysis=self.analysis)
        context["manage_url"] = (
            reverse("ombucore.admin:website_interventioninstance_changelist")
            + f"?analysis={self.analysis.pk}"
        )
        context["intervention_rows"] = [
            self._intervention_row(instance) for instance in self.analysis.interventioninstance_set.all()
        ]
        return context

    def _intervention_row(self, instance: InterventionInstance) -> dict:
        subcomponent_labels = []
        if hasattr(instance, "subcomponent_cost_analysis"):
            subcomponent_labels = instance.subcomponent_cost_analysis.subcomponent_labels or []
        return {
            "instance": instance,
            "params": intervention_parameters_display(instance),
            "subcomponent_labels": subcomponent_labels,
            "subcomponent_labels_url": reverse(
                "analysis-interventions-subcomponent-labels",
                kwargs={"pk": self.analysis.pk, "instance_pk": instance.pk},
            ),
            "subcomponent_delete_url": reverse(
                "analysis-interventions-subcomponent-labels-delete",
                kwargs={"pk": self.analysis.pk, "instance_pk": instance.pk},
            ),
        }


class InterventionInstancePanelMixin:
    """
    Resolves the analysis and intervention instance from URL kwargs for the
    sub-component label panels launched from the Interventions step.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.analysis = get_object_or_404(Analysis, pk=kwargs["pk"])
        self.intervention_instance = get_object_or_404(
            InterventionInstance, pk=kwargs["instance_pk"], analysis=self.analysis
        )
        self.workflow = AnalysisWorkflow(self.analysis)
        self.labels_locked = self.workflow.get_step("load-data").is_complete

    def has_permission(self):
        perms = self.get_permission_required()
        return self.request.user.has_perms(perms, self.analysis)


class InterventionSubcomponentLabels(InterventionInstancePanelMixin, PermissionRequiredMixin, PanelsFormView):
    form_class = SubcomponentLabelsForm
    supertitle = _l("Edit")
    title = _l("Sub-component Labels")
    permission_required = "website.change_analysis"
    template_name = "panel-form-analysis-interventions.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["intervention_instance"] = self.intervention_instance
        kwargs["locked"] = self.labels_locked
        return kwargs

    def form_valid(self, form):
        form.save()
        recalculate_analysis(self.analysis)
        return super().form_valid(form)

    def get_success_commands(self):
        return [commands.Resolve({"operation": "saved"})]


class InterventionSubcomponentLabelsDelete(
    InterventionInstancePanelMixin, PermissionRequiredMixin, PanelsFormView
):
    form_class = SubcomponentLabelsDeleteConfirmForm
    supertitle = _l("Delete")
    title = _l("Sub-Component Analysis")
    permission_required = "website.change_analysis"
    template_name = "panel-form-subcomponent-labels-delete.html"

    def dispatch(self, request, *args, **kwargs):
        # Anonymous users fall through to the login redirect.
        if request.user.is_authenticated and self.labels_locked:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if hasattr(self.intervention_instance, "subcomponent_cost_analysis"):
            subcomponent_analysis = self.intervention_instance.subcomponent_cost_analysis
            subcomponent_analysis.reset_cost_line_items()
            subcomponent_analysis.delete()
            recalculate_analysis(self.analysis)
        return super().form_valid(form)

    def get_success_commands(self):
        return [commands.Resolve({"operation": "deleted"})]


class EditSubcomponentLabel(PermissionRequiredMixin, PanelsFormView):
    form_class = SubcomponentLabelEditForm
    supertitle = _l("Edit")
    title = _l("Sub-component Label")
    permission_required = "website.add_analysis"
    template_name = "panel-form.html"

    def get_initial(self):
        return {"label": self.kwargs.get("label", "")}

    def form_valid(self, form):
        self.new_label = form.cleaned_data["label"]
        return super().form_valid(form)

    def get_success_commands(self):
        return [
            commands.Resolve(
                {
                    "new_label": self.new_label,
                    "label_idx": self.kwargs["label_idx"],
                }
            )
        ]
