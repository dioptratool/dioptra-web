"""The child panels of the intervention Metadata tab.

Both modes validate what was posted and hand the result back to the parent editor through a
Resolve command; nothing is written here. The parent's draft row arrives in the URL fragment
(``#draft=...``), which the editor script reads once to fill the controls, so no draft travels
in the HTTP request line; a bound (POST) response renders the posted state instead.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _l

from ombucore.admin import panel_commands as commands
from ombucore.admin.views import FormView
from website.forms.intervention_metadata import MetadataFieldDraftForm, OptionLabelForm


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
        return context
