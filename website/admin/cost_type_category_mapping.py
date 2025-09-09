from io import BytesIO

import django_filters
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from openpyxl import Workbook

from ombucore.admin import panel_commands as commands
from ombucore.admin.actionlink import ActionLink
from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import AddView, ChangeView, DeleteView
from ombucore.admin.views import FormView
from website import models as website_models
from website.data_loading.cost_type_category_mapping import CostTypeCategoryMappingImporter
from website.forms.core import CostTypeCategoryMappingForm
from website.forms.cost_type_category_mapping import UploadCostTypeMappingForm
from website.models import AccountCodeDescription, CostTypeCategoryMapping


class CostTypeCategoryMappingDeleteView(DeleteView):
    def get_success_message(self, data):
        msg = (
            f"{getattr(self.object.cost_type, 'name', '<None>')} - {getattr(self.object.category, 'name', '<None>')} "
            f"mapping was successfully deleted."
        )
        return msg


class CostTypeCategoryMappingAddView(AddView):
    def get_success_message(self, data):
        msg = (
            f"{getattr(self.object.cost_type, 'name', '<None>')} - {getattr(self.object.category, 'name', '<None>')} "
            f"mapping was successfully created."
        )
        return msg


class CostTypeCategoryMappingChangeView(ChangeView):
    def get_success_message(self, data):
        msg = (
            f"{getattr(self.object.cost_type, 'name', '<None>')} - {getattr(self.object.category, 'name', '<None>')} "
            f"mapping was successfully updated."
        )
        return msg


class CostTypeCategoryMappingFilterSet(FilterSet):
    search = django_filters.CharFilter(field_name="search", method="filter_search")
    cost_type = django_filters.ModelChoiceFilter(
        label="Result Cost Type",
        queryset=website_models.CostType.objects.all(),
    )
    category = django_filters.ModelChoiceFilter(
        label="Result Category",
        queryset=website_models.Category.objects.all(),
    )

    class Meta:
        fields = ["search", "cost_type", "category"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(country_code__icontains=value)
            | Q(grant_code__icontains=value)
            | Q(budget_line_code__icontains=value)
            | Q(account_code__icontains=value)
            | Q(site_code__icontains=value)
            | Q(sector_code__icontains=value)
            | Q(budget_line_description__icontains=value)
            | Q(cost_type__name__icontains=value)
            | Q(category__name__icontains=value)
        )


class UploadCostTypeCategoryPanel(PermissionRequiredMixin, FormView):
    supertitle = "Upload"
    title = "Upload Cost Type Category Mapping"
    success_message = "Updated Cost Type Category Mapping"
    log_action = "Set"
    template_name = "panel-form.html"
    form_class = UploadCostTypeMappingForm
    permission_required = "website.change_costtypecategorymapping"

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

        importer = CostTypeCategoryMappingImporter()

        status, errors = importer.load_file(f)

        if not status:
            for err_msg in errors["errors"]:
                form.add_error("mapping_file", err_msg)
            return self.form_invalid(form)
        return super().form_valid(form)


class ExportCostTypeCategoryMapping(PermissionRequiredMixin, View):

    permission_required = "website.change_costtypecategorymapping"

    def get(self, request, *args, **kwargs):
        wb = Workbook()
        ws = wb.active
        ws.title = "Cost Type Category Mapping"

        headers = [
            "Country code",
            "Grant code",
            "Budget line code",
            "Account Code",
            "Account Code Description",
            "Site code",
            "Sector code",
            "Budget line description",
            "Category",
            "Cost type",
            "Sensitive Data?",
        ]
        ws.append(headers)

        account_codes = {a.account_code: a for a in AccountCodeDescription.objects.all()}

        for each in CostTypeCategoryMapping.objects.all():
            if each.account_code in account_codes:
                ac = account_codes[each.account_code]
                account_code_description = ac.account_description
                is_sensitive_data = ac.sensitive_data
            else:
                account_code_description = ""
                is_sensitive_data = False

            ws.append(
                [
                    each.country_code,
                    each.grant_code,
                    each.budget_line_code,
                    each.account_code,
                    account_code_description,
                    each.site_code,
                    each.sector_code,
                    each.budget_line_description,
                    each.category.name if each.category else "",
                    each.cost_type.name if each.cost_type else "",
                    is_sensitive_data,
                ]
            )

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="cost_type_category_mapping_export.xlsx"'
        return response


class CostTypeCategoryMappingAdmin(ModelAdmin):
    filterset_class = CostTypeCategoryMappingFilterSet
    form_class = CostTypeCategoryMappingForm

    add_view = CostTypeCategoryMappingAddView
    delete_view = CostTypeCategoryMappingDeleteView
    change_view = CostTypeCategoryMappingChangeView

    list_display = (
        ("country_code", _("Country code")),
        ("grant_code", _("Grant")),
        ("budget_line_code", _("Budget line code")),
        ("account_code", _("Account")),
        ("site_code", _("Site")),
        ("sector_code", _("Sector")),
        ("budget_line_description", _("Budget line description")),
        ("display_result", _("Result")),
    )

    def display_criteria(self, obj):
        fields = [
            "country_code",
            "grant_code",
            "budget_line_code",
            "account_code",
            "site_code",
            "sector_code",
            "budget_line_description",
        ]
        field_names = {field.name: field.verbose_name for field in obj._meta.fields}
        criteria = []
        for field in fields:
            if getattr(obj, field, None):
                field_name = field_names[field]
                field_value = getattr(obj, field)
                criteria.append(f"{field_name}: {field_value}")
        return ", ".join(criteria)

    def display_result(self, obj):
        items = []
        if obj.cost_type:
            items.append(obj.cost_type.name)
        if obj.category:
            items.append(obj.category.name)
        return " - ".join(items)

    def get_changelist_action_links(self):
        action_links = super().get_changelist_action_links()
        action_links.append(
            ActionLink(
                text=_("Upload"),
                href=reverse("upload-cost-type-category-mapping-panel"),
            )
        )
        action_links.append(
            ActionLink(
                text=_("Export"),
                href=reverse("export-cost-type-category-mapping"),
                panels_trigger=False,
            )
        )
        return action_links


site.register(website_models.CostTypeCategoryMapping, CostTypeCategoryMappingAdmin)
