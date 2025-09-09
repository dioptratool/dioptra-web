import django_filters
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.forms import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ombucore.admin import panel_commands as commands
from ombucore.admin.actionlink import ActionLink
from ombucore.admin.filterset import FilterSet
from ombucore.admin.forms.base import ModelFormBase
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import FormView
from website import models as website_models
from website.data_loading.countries import CountriesImporter
from website.forms.country import UploadCountriesForm


class UploadCountriesPanel(PermissionRequiredMixin, FormView):
    supertitle = "Upload"
    title = "Upload Countries"
    success_message = "Updated Countries"
    log_action = "Set"
    template_name = "panel-form.html"
    form_class = UploadCountriesForm
    permission_required = "website.change_country"

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
        importer = CountriesImporter()
        status, errors = importer.load_file(f)

        if not status:
            for err_msg in errors["errors"]:
                form.add_error("mapping_file", err_msg)
            return self.form_invalid(form)
        return super().form_valid(form)


class CountryFilterSet(FilterSet):
    search = django_filters.CharFilter(field_name="search", method="filter_search")
    order_by = django_filters.OrderingFilter(
        choices=(
            ("name", _("Name (A-Z)")),
            ("-name", _("Name (Z-A)")),
            ("code", _("Code (A-Z)")),
            ("-code", _("Code (Z-A)")),
            ("region__name", _("Region (A-Z)")),
            ("-region__name", _("Region (Z-A)")),
        ),
        empty_label=None,
    )

    class Meta:
        fields = ["search", "region", "order_by"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(code__icontains=value))


class CountryAdminForm(ModelFormBase):
    class Meta:
        model = website_models.Country
        fields = ["name", "code", "region", "is_default", "always_include_costs"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If the global Settings instance does not allow country filtering, then the always_include_costs field will
        # be ignored in analysis calculations and should be hidden from view
        if not website_models.Settings.country_filtering_enabled():
            self.fields.pop("always_include_costs", None)

    def clean(self):
        """Raise error if default country is already set."""
        cleaned_data = super().clean()
        if cleaned_data.get("is_default") is True:
            current_default_country = website_models.Country.get_default_country()
            if current_default_country and current_default_country != self:
                raise ValidationError(
                    f"{current_default_country.name} is already set as the default country. "
                    f"Change {current_default_country.name} so it is no longer the default in order to continue."
                )


class CountryAdmin(ModelAdmin):
    form_class = CountryAdminForm
    filterset_class = CountryFilterSet

    list_display = (
        ("name", _("Name")),
        ("code", _("Code")),
        ("region", _("Region")),
    )

    def get_changelist_action_links(self):
        action_links = super().get_changelist_action_links()
        action_links.append(
            ActionLink(
                text=_("Upload"),
                href=reverse("upload-countries-panel"),
            )
        )
        return action_links


site.register(website_models.Country, CountryAdmin)
