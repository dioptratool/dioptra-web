from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.forms.models import model_to_dict
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_filters import filters

from ombucore.admin import panel_commands as commands
from ombucore.admin.actionlink import ActionLink
from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import AddView, ChangelistView, ChangeView, DeleteView, ReorderView
from website import models as website_models
from website.forms.intervention_instance import InterventionInstanceForm
from website.models.utils import intervention_parameters_display
from website.workflows import AnalysisWorkflow
from website.workflows.utils import recalculate_analysis


def _authorized_analysis_from_request(request):
    """
    Resolve the parent Analysis from the `analysis` query parameter and check
    that the user may change it. Panel forms post to `action="#"`, so the query
    string survives POSTs.
    """
    try:
        analysis_pk = int(request.GET.get("analysis", ""))
    except (TypeError, ValueError):
        raise Http404("Missing or invalid analysis parameter.")
    analysis = get_object_or_404(website_models.Analysis, pk=analysis_pk)
    _check_analysis_permission(request, analysis)
    return analysis


def _check_analysis_permission(request, analysis):
    if not request.user.has_perm("website.change_analysis", analysis):
        raise PermissionDenied


def _can_delete_intervention_instance(intervention_instance):
    analysis = intervention_instance.analysis
    workflow = AnalysisWorkflow(analysis)
    return not workflow.get_step("load-data").is_complete


class InterventionInstanceFilterSet(FilterSet):
    # Declared so the `?analysis=` scoping parameter survives filter-form
    # round-trips; the widget is hidden because it isn't a user-facing filter.
    analysis = filters.NumberFilter(widget=forms.HiddenInput())

    class Meta:
        model = website_models.InterventionInstance
        fields = ["analysis"]


class InterventionInstanceChangelistView(ChangelistView):
    supertitle = _("Manage")
    template_name = "filter-list/intervention-instance-changelist.html"
    list_template_name = "filter-list/_intervention-instance-list.html"

    def dispatch(self, request, *args, **kwargs):
        self.analysis = _authorized_analysis_from_request(request)
        return super().dispatch(request, *args, **kwargs)

    def get_title(self):
        return _("Interventions being analyzed")

    def modify_queryset(self, queryset):
        return queryset.filter(analysis=self.analysis)

    def process_result(self, obj):
        result = super().process_result(obj)
        result["params"] = intervention_parameters_display(obj)
        return result

    def get_panel_action_links(self):
        action_links = []
        intervention_count = self.analysis.interventioninstance_set.count()
        if intervention_count < settings.MAX_ANALYSIS_INTERVENTIONS:
            action_links.append(
                ActionLink(
                    text="Create",
                    href=self._scoped_url("add"),
                )
            )
        if intervention_count > 1:
            action_links.append(
                ActionLink(
                    text="Reorder",
                    href=self._scoped_url("reorder"),
                    primary=False,
                )
            )
        return action_links

    def _scoped_url(self, url_name):
        return f"{reverse(self.model_admin.url_for(url_name))}?analysis={self.analysis.pk}"


class InterventionInstanceAddView(AddView):
    supertitle = _("Add")
    template_name = "panel-form-add-intervention.html"

    def dispatch(self, request, *args, **kwargs):
        self.analysis = _authorized_analysis_from_request(request)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["analysis"] = self.analysis
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        recalculate_analysis(self.analysis)
        return response


class InterventionInstanceChangeView(ChangeView):
    template_name = "panel-form-add-intervention.html"

    def dispatch(self, request, *args, **kwargs):
        _check_analysis_permission(request, self.get_object().analysis)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        recalculate_analysis(self.object.analysis)
        return response


class InterventionInstanceDeleteView(DeleteView):
    def dispatch(self, request, *args, **kwargs):
        _check_analysis_permission(request, self.get_object().analysis)
        return super().dispatch(request, *args, **kwargs)

    def delete(self):
        analysis = self.object.analysis
        if not _can_delete_intervention_instance(self.object):
            messages.error(
                self.request,
                _("Interventions cannot be deleted after cost data has been loaded."),
            )
            return

        # Log before deleting; app_log can't reference an already-deleted object.
        obj_dict = model_to_dict(self.object)
        self.model_admin.log(
            actor=self.request.user,
            action=self.log_action,
            obj=self.object,
            message=self.get_log_message(obj_dict),
        )

        try:
            success_message = self.get_success_message(obj_dict)
            self.object.delete()
            self.deleted = True
            if success_message:
                messages.success(self.request, success_message)
            self.panel_commands.append(commands.Resolve({"operation": "deleted"}))
        except ProtectedError:
            self.protected = True
            messages.error(self.request, self.get_protected_error_message(obj_dict))

        if self.deleted:
            recalculate_analysis(analysis)


class InterventionInstanceReorderView(ReorderView):
    template_name = "panel-form-intervention-instance-reorder.html"

    def dispatch(self, request, *args, **kwargs):
        self.analysis = _authorized_analysis_from_request(request)
        self.queryset = website_models.InterventionInstance.objects.filter(
            analysis=self.analysis
        ).select_related("intervention")
        # Reordering fewer than two interventions is meaningless, and the
        # guard keeps an empty queryset from ever reaching the base view.
        if self.queryset.count() < 2:
            raise Http404("Not enough interventions to reorder.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reorder_items"] = [
            {
                "obj": obj,
                "params": intervention_parameters_display(obj),
            }
            for obj in context["form"].queryset
        ]
        return context


class InterventionInstanceAdmin(ModelAdmin):
    form_class = InterventionInstanceForm
    add_view = InterventionInstanceAddView
    change_view = InterventionInstanceChangeView
    delete_view = InterventionInstanceDeleteView
    changelist_view = InterventionInstanceChangelistView
    changelist_select_view = False
    reorder_view = InterventionInstanceReorderView
    filterset_class = InterventionInstanceFilterSet
    list_display = (
        ("display_name", _("Name")),
        ("intervention", _("Intervention")),
    )

    def _wrap_view_with_permission(self, view, permission_action):
        # BASIC-role users don't have InterventionInstance model permissions;
        # each view enforces object-level `change_analysis` in dispatch instead.
        return view

    def get_changelist_action_links(self):
        # Replaced by analysis-scoped links on the changelist view.
        return []

    def get_changelist_object_action_links(self, obj):
        action_links = super().get_changelist_object_action_links(obj)
        for action_link in action_links:
            action_link.attrs = {
                **action_link.attrs,
                "class": "intervention-action",
            }
        delete_route = self.url_for("delete")
        if delete_route and _can_delete_intervention_instance(obj):
            action_links.append(
                ActionLink(
                    text="Delete",
                    href=reverse(delete_route, args=[obj.id]),
                    primary=False,
                    attrs={"class": "intervention-action intervention-action--delete"},
                )
            )
        return action_links


site.register(website_models.InterventionInstance, InterventionInstanceAdmin)
