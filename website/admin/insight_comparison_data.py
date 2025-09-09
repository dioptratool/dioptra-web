import django_filters
from django import forms
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ombucore.admin import panel_commands as commands
from ombucore.admin.actionlink import ActionLink
from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import FormView
from website import models as website_models
from website.data_loading.insight_comparison_data import InsightComparisonDataImporter
from website.forms.insight_comparison_data import InsightComparisonDataForm, UploadInsightComparisonDataForm


class UploadInsightComparisonDataPanel(PermissionRequiredMixin, FormView):
    supertitle = "Upload"
    title = "Upload Insight Comparison Data"
    success_message = "Updated Insight Comparison Data"
    log_action = "Set"
    template_name = "panel-form.html"
    form_class = UploadInsightComparisonDataForm
    permission_required = "website.change_insightcomparisondata"

    def get_success_commands(self):
        return [
            commands.Resolve(
                {
                    "operation": "saved",
                }
            )
        ]

    def form_valid(self, form):
        """Handle the file parsing logic here, then call super if everything is good."""
        f = self.request.FILES.get("mapping_file")
        importer = InsightComparisonDataImporter()
        status, errors = importer.load_file(f)

        if not status:
            for err_msg in errors["errors"]:
                form.add_error("mapping_file", err_msg)
            return self.form_invalid(form)
        return super().form_valid(form)


class InsightComparisonDataFilterSet(FilterSet):
    search = django_filters.CharFilter(
        method="keyword_search",
    )
    country = django_filters.ModelChoiceFilter(
        label=_("Country"),
        field_name="country",
        queryset=website_models.Country.objects.all(),
        widget=forms.Select,
    )
    intervention = django_filters.ModelChoiceFilter(
        label=_("Intervention"),
        field_name="intervention",
        queryset=website_models.Intervention.objects.all(),
        widget=forms.Select,
    )
    order_by = django_filters.OrderingFilter(
        choices=(
            ("name", _("Name (A-Z)")),
            ("-name", _("Name (Z-A)")),
        ),
        empty_label=None,
    )

    def keyword_search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(grants__icontains=value))

    class Meta:
        fields = ["search", "country", "intervention"]


class InsightComparisonDataAdmin(ModelAdmin):
    filterset_class = InsightComparisonDataFilterSet
    form_class = InsightComparisonDataForm

    list_display = (
        ("name", _("Name")),
        ("country", _("Country")),
        ("display_grants", _("Grants")),
        ("intervention", _("Intervention")),
    )

    def display_grants(self, instance):
        return ", ".join(instance.grants_list())

    def get_changelist_action_links(self):
        action_links = super().get_changelist_action_links()
        action_links.append(
            ActionLink(
                text=_("Upload"),
                href=reverse("upload-insight-comparison-data-panel"),
            )
        )
        return action_links


site.register(website_models.InsightComparisonData, InsightComparisonDataAdmin)
