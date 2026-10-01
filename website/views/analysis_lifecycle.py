"""Confirm panels for the lifecycle actions: change status, archive, unarchive.

Each is reached from a ``data-panels-trigger`` link. GET shows the question, a CSRF-protected POST
performs the action through the lifecycle service, and a success resolves the panel with the
operation name so the opener can reload itself (``data-panels-reload-on``). A rejection by the
service is rendered as a form error in the same panel; nothing is written in that case.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.html import format_html
from django.utils.translation import gettext as _, gettext_lazy as _l
from django.views.generic.detail import SingleObjectMixin

from ombucore.admin import panel_commands as commands
from ombucore.admin.views import FormView
from website.analysis_lifecycle import AnalysisLifecycleError, change_analysis_status, set_analysis_archived
from website.forms.analysis_lifecycle import AnalysisLifecycleConfirmForm
from website.models import Analysis, AnalysisStatus


class AnalysisLifecycleActionView(LoginRequiredMixin, SingleObjectMixin, FormView):
    queryset = Analysis.objects
    form_class = AnalysisLifecycleConfirmForm
    template_name = "panel-form-analysis-lifecycle.html"
    # Who may open the panel at all; the service re-checks the specific operation when it runs.
    permission_required = None
    # The Resolve payload's operation, matched by the opener's data-panels-reload-on.
    operation = None
    confirm_label = None
    done = False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.object = self.get_object()
        if not request.user.has_perm(self.permission_required, self.object):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def perform(self):
        raise NotImplementedError

    def get_question(self):
        raise NotImplementedError

    def get_explanation(self):
        return None

    def form_valid(self, form):
        try:
            self.object = self.perform()
        except AnalysisLifecycleError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        self.done = True
        return super().form_valid(form)

    def get_success_commands(self):
        return [commands.Resolve({"operation": self.operation})]

    def get_success_message(self, cleaned_data):
        # The title is user content: format it in, never interpolate it into markup.
        return format_html(self.success_message, title=self.object.title)

    def get_title(self):
        return self.object.title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["analysis"] = self.object
        context["done"] = self.done
        context["question"] = self.get_question()
        context["explanation"] = self.get_explanation()
        context["confirm_label"] = self.confirm_label
        context["done_message"] = self.get_success_message({}) if self.done else None
        return context


class AnalysisStatusChangeView(AnalysisLifecycleActionView):
    permission_required = "website.change_analysis_status"
    operation = "status-changed"
    supertitle = _l("Change Status")
    success_message = _l("<strong>{title}</strong> is now {status}.")

    def dispatch(self, request, *args, **kwargs):
        try:
            self.target = AnalysisStatus(kwargs["status"])
        except ValueError:
            raise Http404(_("Unknown analysis status."))
        return super().dispatch(request, *args, **kwargs)

    def perform(self):
        return change_analysis_status(self.object.pk, self.request.user, self.target)

    def get_question(self):
        return _("Mark “%(title)s” as %(status)s?") % {
            "title": self.object.title,
            "status": self.target.label,
        }

    def get_explanation(self):
        if self.target == AnalysisStatus.IN_PROGRESS:
            return _("The analysis can then be edited and marked Complete again later.")
        if self.target == AnalysisStatus.VALIDATED:
            return _("Only administrators can edit a Validated analysis or change its status.")
        return _("Every step of the analysis, including Insights, must be complete.")

    @property
    def confirm_label(self):
        return _("Yes, mark as %(status)s") % {"status": self.target.label}

    def get_success_message(self, cleaned_data):
        return format_html(self.success_message, title=self.object.title, status=self.target.label)


class AnalysisArchiveView(AnalysisLifecycleActionView):
    permission_required = "website.archive_analysis"
    operation = "archived"
    supertitle = _l("Archive")
    confirm_label = _l("Yes, archive")
    success_message = _l("<strong>{title}</strong> was archived.")

    def perform(self):
        return set_analysis_archived(self.object.pk, self.request.user, True)

    def get_question(self):
        return _("Archive “%(title)s”?") % {"title": self.object.title}

    def get_explanation(self):
        return _(
            "An archived analysis is left out of the dashboard unless you filter for archived "
            "analyses. Its status, data and permissions do not change, and it can be unarchived later."
        )


class AnalysisUnarchiveView(AnalysisLifecycleActionView):
    permission_required = "website.unarchive_analysis"
    operation = "unarchived"
    supertitle = _l("Unarchive")
    confirm_label = _l("Yes, unarchive")
    success_message = _l("<strong>{title}</strong> was unarchived.")

    def perform(self):
        return set_analysis_archived(self.object.pk, self.request.user, False)

    def get_question(self):
        return _("Unarchive “%(title)s”?") % {"title": self.object.title}

    def get_explanation(self):
        return _("The analysis is shown on the dashboard again. Its status and data do not change.")
