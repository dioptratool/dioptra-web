from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from ombucore.admin.forms.base import ModelFormBase
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import ChangeView
from ombucore.imagewidget.fields import PreviewableImageInput
from website.data_loading.transaction_templates import get_transaction_template_choices
from website import models as website_models


class SettingsForm(ModelFormBase):
    iso_currency_code = forms.CharField(required=False, disabled=True, initial=settings.ISO_CURRENCY_CODE)
    transaction_data_template = forms.ChoiceField(choices=get_transaction_template_choices)

    class Meta:
        fields = [
            "google_analytics_code",
            "show_transactions",
            "budget_upload_template",
            "transaction_data_template",
            "instance_logo",
            "paginate_by",
            "transaction_country_filter",
        ]
        fieldsets = (
            (
                _("Instance"),
                {
                    "fields": (
                        "instance_logo",
                        "iso_currency_code",
                        "transaction_country_filter",
                        "paginate_by",
                    ),
                },
            ),
            (
                _("Analysis"),
                {
                    "fields": (
                        "show_transactions",
                        "budget_upload_template",
                        "transaction_data_template",
                    ),
                },
            ),
            (
                _("Analytics"),
                {
                    "fields": ("google_analytics_code",),
                },
            ),
        )
        widgets = {
            "instance_logo": PreviewableImageInput(),
        }
        labels = {
            "transaction_country_filter": _(
                "Enable country filter when loading transactions from the transaction data store"
            )
        }
        help_texts = {
            "instance_logo": _("Logo appears on the login screen."),
            "paginate_by": _(
                "Pagination setting affects the list of analyses on the dashboard, "
                "Assign Cost Type & Category step, and the full cost model table."
            ),
            "transaction_data_template": _(
                "Select the transaction upload template available on the Load Data step."
            ),
        }


class SettingsChangeView(ChangeView):
    form_class = SettingsForm

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.model_admin and self.log_action and "transaction_country_filter" in form.changed_data:
            if form.cleaned_data.get("transaction_country_filter"):
                self.model_admin.log(
                    actor=self.request.user,
                    action=self.log_action,
                    obj=self.object,
                    message="Transaction country filter setting was successfully enabled",
                )
            else:
                self.model_admin.log(
                    actor=self.request.user,
                    action=self.log_action,
                    obj=self.object,
                    message="Transaction country filter setting was successfully disabled",
                )
        return response


class SettingsAdmin(ModelAdmin):
    form_class = SettingsForm
    change_view = SettingsChangeView
    add_view = False
    changelist_view = False
    delete_view = False


site.register(website_models.Settings, SettingsAdmin)


class ManageFieldLabelOverridesForm(ModelFormBase):
    @property
    def override_field_names(self):
        return [field_name for field_name in self.fields if not field_name.endswith("_overridden")]

    def clean(self):
        data = self.cleaned_data
        for fname in self.fields:
            if not fname.endswith("_overridden") and data[f"{fname}_overridden"] and not data[fname]:
                self.add_error(fname, "This field is required.")
        return data

    class Meta:
        fields = "__all__"
        fieldsets = (
            (
                _("Transactions"),
                {
                    "intro": (
                        "Override the text labels that appear for transaction data model fields. "
                        "This will update the labels for analyses that use transaction data, "
                        "seen when cost line items are expanded."
                    ),
                    "fields": (
                        "transaction_help_text",
                        "tr_date",
                        "tr_date_overridden",
                        "tr_site_code",
                        "tr_site_code_overridden",
                        "tr_amount",
                        "tr_amount_overridden",
                    ),
                },
            ),
            (
                _("Cost Items"),
                {
                    "intro": (
                        "Override the text labels that appear for cost item data model fields. "
                        "This will update the table heading text for all tables showing cost line items."
                    ),
                    "fields": (
                        "cost_item_help_text",
                        "ci_grant_code",
                        "ci_grant_code_overridden",
                        "ci_site_code",
                        "ci_site_code_overridden",
                        "ci_account_code",
                        "ci_account_code_overridden",
                        "ci_sector_code",
                        "ci_sector_code_overridden",
                        "ci_budget_line_description",
                        "ci_budget_line_description_overridden",
                        "ci_cost_type",
                        "ci_cost_type_overridden",
                        "ci_total_cost",
                        "ci_total_cost_overridden",
                    ),
                },
            ),
            (
                _("Budget Custom Fields"),
                {
                    "intro": (
                        "Override the text labels that appear for the five custom columns imported "
                        "from the budget upload. A custom column is only shown in an analysis when "
                        "the imported data actually contains values for it."
                    ),
                    "fields": (
                        "ci_dummy_field_1",
                        "ci_dummy_field_1_overridden",
                        "ci_dummy_field_2",
                        "ci_dummy_field_2_overridden",
                        "ci_dummy_field_3",
                        "ci_dummy_field_3_overridden",
                        "ci_dummy_field_4",
                        "ci_dummy_field_4_overridden",
                        "ci_dummy_field_5",
                        "ci_dummy_field_5_overridden",
                    ),
                },
            ),
            (
                _("Transaction Custom Fields"),
                {
                    "intro": (
                        "Override the text labels that appear for the five custom columns imported "
                        "from the transaction data. A custom column is only shown in an analysis "
                        "when the imported data actually contains values for it."
                    ),
                    "fields": (
                        "tr_dummy_field_1",
                        "tr_dummy_field_1_overridden",
                        "tr_dummy_field_2",
                        "tr_dummy_field_2_overridden",
                        "tr_dummy_field_3",
                        "tr_dummy_field_3_overridden",
                        "tr_dummy_field_4",
                        "tr_dummy_field_4_overridden",
                        "tr_dummy_field_5",
                        "tr_dummy_field_5_overridden",
                    ),
                },
            ),
        )
        help_texts = {
            "tr_date": _("Anytime transactions are expanded, there is a Date column header."),
            "tr_site_code": _("Anytime transactions are expanded, there is a Site column header."),
            "tr_amount": _("Anytime transactions are expanded, there is an Amount column header."),
            "ci_grant_code": _(
                "Seen on Define Analysis, Load Data, and "
                "Confirm Categories steps, and the full cost model table."
            ),
            "ci_site_code": _(
                "Seen on Confirm Categories, Allocate Costs, and Identify Output Value steps, and the full cost "
                "model table."
            ),
            "ci_cost_type": _("Seen on Confirm Categories step, and the full cost model table."),
            "ci_total_cost": _("Seen on the full cost model table."),
            "ci_account_code": _(
                "Seen in the budget upload template and cost item and transaction edit panels."
            ),
            "ci_sector_code": _(
                "Seen in the budget upload template, analysis tables, and cost item and transaction edit panels."
            ),
            "ci_budget_line_description": _(
                "Seen in the budget upload template, cost model, and cost item and transaction edit panels."
            ),
            **{
                f"ci_dummy_field_{n}": _(
                    "Seen on Confirm Categories and Allocate Costs steps, "
                    "when budget data populates this custom column."
                )
                for n in range(1, 6)
            },
            **{
                f"tr_dummy_field_{n}": _(
                    "Seen anytime transactions are expanded, "
                    "when transaction data populates this custom column."
                )
                for n in range(1, 6)
            },
        }

    class Media:
        js = ("website/js/admin/panel-field-label-overrides.js",)


class FieldLabelOverridesChangeView(ChangeView):
    template_name = "field-label-overrides/manage-overrides-form.html"
    form_class = ManageFieldLabelOverridesForm


class FieldLabelOverridesAdmin(ModelAdmin):
    change_view = FieldLabelOverridesChangeView
    add_view = False
    changelist_view = False
    delete_view = False


site.register(website_models.FieldLabelOverrides, FieldLabelOverridesAdmin)
