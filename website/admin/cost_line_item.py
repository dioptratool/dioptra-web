from django.core.exceptions import PermissionDenied

from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import DeleteView
from website import models as website_models
from website.workflows import AnalysisWorkflow


class CostLineItemDeleteView(DeleteView):
    template_name = "panel-overrides/cost-line-item-delete.html"

    def dispatch(self, request, *args, **kwargs):
        cost_line_item = self.get_object()
        if not request.user.has_perm("website.change_analysis", cost_line_item.analysis):
            raise PermissionDenied
        if not cost_line_item.config:
            raise PermissionDenied
        # We only allow delete of "Other Costs", which will always have a non-null `analysis_cost_type`
        if not cost_line_item.config.analysis_cost_type:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def delete(self):
        super().delete()

        # Hack to make sure deleting other CostLineItems correctly refreshes output costs
        workflow = AnalysisWorkflow(self.object.analysis)
        workflow.calculate_if_possible()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.deleted:
            return context

        cost_type = self.object.config.analysis_cost_type
        if cost_type == website_models.AnalysisCostType.CLIENT_TIME:
            context["supertitle"] = "Client Time"
            context["title"] = "Delete Client Time Cost"
        elif cost_type == website_models.AnalysisCostType.IN_KIND:
            context["supertitle"] = "In-Kind Contributions"
            context["title"] = "Delete Cost Item"
        elif cost_type == website_models.AnalysisCostType.OTHER_HQ:
            context["supertitle"] = "Other HQ Costs"
            context["title"] = "Delete Cost Item"

        return context


class CostLineItemAdmin(ModelAdmin):
    add_view = False
    change_view = False
    delete_view = CostLineItemDeleteView
    form_config = {}

    def _wrap_view_with_permission(self, view, permission_action):
        if permission_action == "delete":
            # Skip the permissioning here. Handle it on the DeleteView.
            return view
        return super()._wrap_view_with_permission(view, permission_action)


site.register(website_models.CostLineItem, CostLineItemAdmin)
