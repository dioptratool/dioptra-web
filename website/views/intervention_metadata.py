"""The child panels of the intervention Metadata tab.

The draft panels validate what was posted and hand the result back to the parent editor through a
Resolve command; the impact panel lists the analyses a change would affect and resolves the
administrator's choice. Nothing is written here. The parent's draft row arrives in the URL fragment
(``#draft=...``), which the editor script reads once to fill the controls, so no draft travels
in the HTTP request line; a bound (POST) response renders the posted state instead.
"""

import uuid

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _l
from django.views.generic import TemplateView

from ombucore.admin import panel_commands as commands
from ombucore.admin.views import FormView
from ombucore.admin.views.mixins import PanelUIMixin
from website.forms.intervention_metadata import MetadataFieldDraftForm, OptionLabelForm
from website.intervention_metadata import metadata_impact
from website.models import Intervention, InterventionMetadataField, InterventionMetadataOption


class InterventionMetadataDraftView(LoginRequiredMixin, FormView):
    template_name = "panel-form-intervention-metadata.html"
    supertitle = _l("Metadata")
    MODES = {"field": MetadataFieldDraftForm, "option_label": OptionLabelForm}
    TITLES = {"field": _l("Metadata Field"), "option_label": _l("Option Label")}

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.mode = kwargs.get("mode")
        if self.mode not in self.MODES:
            raise Http404(_l("Unknown metadata panel."))
        # Only instance administrators manage definitions: the parent's own permission applies.
        permission = (
            "website.change_intervention" if request.GET.get("intervention") else "website.add_intervention"
        )
        if not request.user.has_perm(permission):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        return self.MODES[self.mode]

    def get_title(self):
        return self.TITLES[self.mode]

    def form_valid(self, form):
        if self.mode == "field":
            payload = {"row": form.normalized_row}
        else:
            payload = {"label": form.cleaned_data["label"]}
        self.panel_commands.append(commands.Resolve(payload))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.urlencode()
        context["mode"] = self.mode
        context["bound"] = self.request.method == "POST"
        context["option_url"] = reverse("intervention-metadata-draft", kwargs={"mode": "option_label"}) + (
            f"?{query}" if query else ""
        )
        # The affected-analyses confirmation; a new intervention has nothing stored to list.
        context["impact_url"] = (
            f"{reverse('intervention-metadata-impact')}?{query}"
            if self.request.GET.get("intervention")
            else ""
        )
        return context


def _uuid_or_404(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise Http404(_l("Unknown metadata key."))


def _int_or_404(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise Http404(_l("Unknown intervention."))


class InterventionMetadataImpactView(LoginRequiredMixin, PanelUIMixin, TemplateView):
    """
    The confirmation shown before a field or option is deleted, or a field's type changed, while
    analyses hold values for it: the affected analyses, tabled with their status. The editor
    script acts on the resolved choice; the change itself is applied by the parent save.

    The query string names the intervention, the field key, the option key (for an option) and the
    action, so the server resolves the impact against what is stored; a draft rename is not shown.
    """

    template_name = "panel-form-intervention-metadata-impact.html"
    ACTIONS = {
        "delete_field": _l("Delete metadata field"),
        "delete_option": _l("Delete option"),
        "change_type": _l("Change field type"),
    }

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.has_perm("website.change_intervention"):
            raise PermissionDenied
        params = request.GET
        self.action = params.get("action")
        if self.action not in self.ACTIONS:
            raise Http404(_l("Unknown metadata action."))
        self.intervention = get_object_or_404(Intervention, pk=_int_or_404(params.get("intervention")))
        self.field = get_object_or_404(
            InterventionMetadataField, intervention=self.intervention, key=_uuid_or_404(params.get("field"))
        )
        self.option = None
        if self.action == "delete_option":
            self.option = get_object_or_404(
                InterventionMetadataOption, field=self.field, key=_uuid_or_404(params.get("option"))
            )
        return super().dispatch(request, *args, **kwargs)

    def get_supertitle(self):
        return self.ACTIONS[self.action]

    def get_title(self):
        return self.field.name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            action=self.action,
            field=self.field,
            option=self.option,
            analyses=metadata_impact(
                self.intervention, self.field.storage_key, self.option.storage_key if self.option else None
            ),
        )
        return context
