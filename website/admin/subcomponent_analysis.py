from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.forms.models import model_to_dict

from app_log.logger import log
from ombucore.admin import panel_commands as commands
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import DeleteView
from website import models as website_models


class SubcomponentAnalysisAdmin(ModelAdmin):
    def get_delete_view(self):
        return SubcomponentsDeleteView


class SubcomponentsDeleteView(DeleteView):
    pk_url_kwarg = "subcomponent_pk"
    model = website_models.SubcomponentCostAnalysis
    model_admin = SubcomponentAnalysisAdmin
    supertitle = "RESET"
    template_name = "panel-overrides/subcomponent-analysis-delete.html"

    def dispatch(self, request, *args, **kwargs):
        analysis = self.get_object()
        if not request.user.has_perm("website.delete_analysis", analysis):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_message(self, data):
        if not "title" in data:
            data["title"] = str(self.object)
        return self.success_message % data

    def delete(self):
        # Generate the success message before the object is deleted.
        obj_dict = model_to_dict(self.object)
        # Log the event.
        log(
            actor=self.request.user,
            action=self.log_action,
            obj=self.object,
            message=self.get_log_message(obj_dict),
        )

        try:
            success_message = self.get_success_message(obj_dict)
            self.object.reset_cost_line_items()
            self.object.delete()
            self.deleted = True
            if success_message:
                messages.success(self.request, success_message)

            self.panel_commands.append(commands.Resolve({"operation": "deleted"}))
        except ProtectedError:
            self.protected = True
            messages.error(self.request, self.get_protected_error_message(obj_dict))

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        # Due to what appears to be a quirk in the DeleteView I'm unable to
        #  set the title using the normal ombucore means.   This does it manually.
        data["title"] = "Sub-component Analysis"
        return data


site.register(website_models.SubcomponentCostAnalysis, SubcomponentAnalysisAdmin)
