import django_filters
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import path
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ombucore.admin.actionlink import ActionLink
from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import ChangeView, DeleteView
from website import models as website_models
from website.forms.analysis import ReassignOwnerForm

User = get_user_model()


class AnalysisFilterSet(FilterSet):
    search = django_filters.CharFilter(
        method="keyword_search",
    )
    country = django_filters.ModelChoiceFilter(
        label=_("Country"),
        field_name="country",
        queryset=website_models.Country.objects.all(),
        widget=forms.Select,
    )
    region = django_filters.ModelChoiceFilter(
        label=_("Region"),
        field_name="country__region",
        queryset=website_models.Region.objects.all(),
        widget=forms.Select,
    )
    analysis_type = django_filters.ModelChoiceFilter(
        label=_("Analysis Type"),
        field_name="analysis_type",
        queryset=website_models.AnalysisType.objects.all(),
        widget=forms.Select,
    )
    owner = django_filters.ModelChoiceFilter(
        label="Owner",
        field_name="owner",
        null_label="None",
        null_value="None",
        queryset=User.objects.all(),
    )
    owner.field.label_from_instance = lambda user: user.get_full_name()

    order_by = django_filters.OrderingFilter(
        choices=(
            ("title", _("Title (A-Z)")),
            ("-title", _("Title (Z-A)")),
            ("-updated", _("Last Updated (newest first)")),
            ("updated", _("Last Updated (oldest first)")),
        ),
        empty_label=None,
    )

    def keyword_search(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value) | Q(grants__icontains=value)
        )

    class Meta:
        fields = [
            "search",
        ]


class AnalysisDeleteView(DeleteView):
    def dispatch(self, request, *args, **kwargs):
        analysis = self.get_object()
        if not request.user.has_perm("website.delete_analysis", analysis):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AnalysisReassignView(ChangeView):
    form_class = ReassignOwnerForm


class AnalysisAdmin(ModelAdmin):
    filterset_class = AnalysisFilterSet
    add_view = False
    change_view = False
    reassign_view = AnalysisReassignView
    delete_view = AnalysisDeleteView
    form_config = {}

    list_display = (
        ("title", _("Title")),
        ("display_owner", _("Owner")),
        ("country", _("Country")),
        ("grants", _("Grants")),
        ("updated", _("Last Updated")),
    )

    def display_owner(self, analysis):
        if analysis.owner:
            return analysis.owner.name
        return None

    def get_changelist_action_links(self):
        action_links = []
        action_links.append(
            ActionLink(
                text=_("Create"),
                href=reverse("analysis-define-create"),
                panels_trigger=False,
                attrs={"target": "_blank"},
            )
        )
        return action_links

    def get_changelist_object_action_links(self, analysis):
        action_links = []
        action_links.append(
            ActionLink(
                text=_("Open"),
                href=reverse("analysis", kwargs={"pk": analysis.pk}),
                panels_trigger=False,
                attrs={"target": "_blank"},
            )
        )
        action_links.append(
            ActionLink(
                text=_("Reassign"),
                href=reverse(self.url_for("reassign"), kwargs={"pk": analysis.pk}),
                reload_on=["saved"],
            )
        )
        action_links.append(
            ActionLink(
                text=_("Duplicate"),
                href=reverse("analysis-create-copy", kwargs={"pk": analysis.pk}),
                reload_on=["duplicated"],
            )
        )

        action_links.append(
            ActionLink(
                text=_("Delete"),
                href=reverse(self.url_for("delete"), kwargs={"pk": analysis.pk}),
                reload_on=["deleted"],
            )
        )
        return action_links

    def admin_overlay_info_for(self, obj, user=None):
        # Don't show any contextual info for this object.
        return []

    def _initialize_views(self):
        super()._initialize_views()
        opts = {
            "__module__": self.model.__module__,
            "model": self.model,
            "model_admin": self,
        }
        self.reassign_view = type(f"{self.model.__name__}ReassignView", (self.reassign_view,), opts)

    def get_urls(self):
        urlpatterns = super().get_urls()
        reassign_view = self._wrap_view_with_permission(self.prepare_view(self.reassign_view), "reassign")
        urlpatterns.append(
            path(
                "<int:pk>/reassign/",
                reassign_view,
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_reassign",
            ),
        )
        return urlpatterns

    def _wrap_view_with_permission(self, view, permission_action):
        if permission_action == "delete":
            # Skip the permissioning here. Handle it on the DeleteView.
            return view
        return super()._wrap_view_with_permission(view, permission_action)


site.register(website_models.Analysis, AnalysisAdmin)
