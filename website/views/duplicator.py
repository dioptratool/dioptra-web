from logging import getLogger

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.forms.models import model_to_dict
from django.utils.html import strip_tags
from django.views.generic.detail import SingleObjectMixin

from app_log.logger import log
from ombucore.admin import panel_commands as commands
from ombucore.admin.sites import site
from ombucore.admin.views import FormView
from website.forms.duplicator import (
    DuplicateBudgetUploadAnalysisForm,
    DuplicateTransactionStoreAnalysisForm,
)
from website.models import Analysis
from website.utils.duplicator import clone_analysis
from website.workflows import AnalysisWorkflow

logger = getLogger(__name__)


class DuplicateView(SingleObjectMixin, FormView):
    queryset = Analysis.objects
    title = None
    supertitle = "Duplicate"
    success_message = "<strong>%(title)s</strong> was successfully duplicated."
    log_action = "Duplicated"
    duplicated = False

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object_id = self.object.id
        if "confirmed" in request.GET:
            self.duplicate()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_initial(self):
        if self.object.source == Analysis.DATA_STORE_NAME:
            return {
                "start_date": self.object.start_date,
                "end_date": self.object.end_date,
            }
        return {}

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_form_class(self):
        if self.object.source == Analysis.DATA_STORE_NAME:
            return DuplicateTransactionStoreAnalysisForm
        return DuplicateBudgetUploadAnalysisForm

    def get_template_names(self):
        if self.object.source == Analysis.DATA_STORE_NAME:
            return "panel-form-duplicate-transaction-store-analysis.html"
        return "panel-form-duplicate-budget-upload-analysis.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        obj_dict = model_to_dict(self.object)
        success_message = self.get_success_message(obj_dict)
        values = {}
        if form.cleaned_data.get("change_analysis_date_range") == "change":
            if form.cleaned_data.get("start_date"):
                values["start_date"] = form.cleaned_data.get("start_date")
            if form.cleaned_data.get("end_date"):
                values["end_date"] = form.cleaned_data.get("end_date")
        new_analysis = clone_analysis(self.object.id, self.request.user, **values)
        if values:
            new_analysis.needs_transaction_resync = True
            workflow = AnalysisWorkflow(new_analysis)
            workflow.invalidate_step("insights")
            new_analysis.save()
        self.duplicated = True
        if success_message:
            messages.success(self.request, success_message)
        log(
            actor=self.request.user,
            action=self.log_action,
            obj=new_analysis,
            message=self.get_log_message(obj_dict),
        )
        self.panel_commands.append(commands.Resolve({"operation": "duplicated"}))
        # return redirect(reverse('analysis-define-update', kwargs={'pk': new_analysis.pk}))
        return response

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        if self.object and not self.duplicated:
            obj_info = site.related_info_for(self.object)
            kwargs["title"] = obj_info["title"]
        kwargs["duplicated"] = getattr(self, "duplicated", False)
        kwargs["object_id"] = self.object.id
        return kwargs

    def get_success_message(self, data):
        if "title" not in data:
            data["title"] = str(self.object)
        return self.success_message % data

    def get_log_message(self, cleaned_data):
        return strip_tags(self.get_success_message(cleaned_data))

    def dispatch(self, request, *args, **kwargs):
        analysis = self.get_object()
        if not request.user.has_perm("website.duplicate_analysis", analysis):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
