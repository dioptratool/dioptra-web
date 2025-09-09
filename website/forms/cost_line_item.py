from decimal import Decimal

from babel.numbers import get_currency_symbol
from django import forms
from django.conf import settings
from django.utils.translation import gettext as _

from website.currency import get_currency_locale
from website.forms.fields import InterventionInstanceChoiceField, PositiveFixedDecimalField
from website.forms.widgets import CurrencyWidget, PercentWidget
from website.models import (
    Analysis,
    AnalysisCostType,
    CostLineItem,
    CostLineItemConfig,
    CostType,
)
from website.models.cost_line_item import CostLineItemInterventionAllocation

COMMON_COST_LINE_ITEM_FIELDS = [
    "analysis",
    "budget_line_description",
    "loe_or_unit",
    "quantity",
    "unit_cost",
    "total_cost",
    "note",
]

COMMON_WIDGETS = {
    "analysis": forms.HiddenInput(),
    "note": forms.Textarea(attrs={"placeholder": "Source of this information and any other important notes"}),
}


class AddCostLineItemForm(forms.ModelForm):
    ANALYSIS_COST_TYPE = None
    SUB_TITLE = _("Cost Item")
    SUPER_TITLE = _("Cost Line Item")

    class Meta:
        model = CostLineItem
        fields = COMMON_COST_LINE_ITEM_FIELDS
        widgets = COMMON_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Extract Analysis to use in various field params
        if self.instance and self.instance.id:
            self.analysis = self.instance.analysis
        else:
            self.analysis = self.initial["analysis"]

        # If the form has an "allocation" field we replace it with a multi-intervention version of
        #   this and remove the original
        if "allocation" in self.fields:
            for intervention_instance in self.analysis.interventioninstance_set.all():
                if hasattr(self.instance, "config"):
                    cli_allocation = CostLineItemInterventionAllocation.objects.filter(
                        intervention_instance=intervention_instance,
                        cli_config=self.instance.config,
                    ).first()
                    if cli_allocation:
                        allocation_amount = cli_allocation.allocation
                    else:
                        allocation_amount = None

                else:
                    allocation_amount = None
                self.fields[f"intervention_allocation_{intervention_instance.id}"] = (
                    PositiveFixedDecimalField(
                        label=f"How much did this contribute to {intervention_instance.display_name()}?",
                        initial=allocation_amount,
                        widget=PercentWidget(),
                        help_text="Enter a percent amount between 0 and 100",
                        allow_zero=True,
                    )
                )
            del self.fields["allocation"]

        self.fields["note"].label = _("Notes")

        for fieldname in self.fields:
            # Logic to pass currency type into any CurrencyWidgets
            if isinstance(self.fields[fieldname].widget, CurrencyWidget):
                currency_symbol = get_currency_symbol(
                    settings.ISO_CURRENCY_CODE,
                    locale=get_currency_locale(),
                )
                if self.analysis.source != Analysis.DATA_STORE_NAME and self.analysis.currency_code:
                    currency_symbol = get_currency_symbol(
                        self.analysis.currency_code,
                        locale=get_currency_locale(),
                    )
                self.fields[fieldname].widget.attrs["currency_symbol"] = currency_symbol

            # Logic to add "required" to necessary fields
            if fieldname == "note":
                continue
            if isinstance(self.fields[fieldname].widget, forms.HiddenInput):
                # Do not require hidden fields
                continue
            self.fields[fieldname].required = True

        # Note should be last field
        self.fields["note"] = self.fields.pop("note")

    def save(self, commit=True):
        result = super().save(commit=commit)
        if commit:
            config, created = CostLineItemConfig.objects.get_or_create(
                cost_line_item=result,
                defaults={
                    "analysis_cost_type": self.ANALYSIS_COST_TYPE,
                },
            )

            for k, v in self.cleaned_data.items():
                if k.startswith("intervention_allocation_"):
                    allocation = v
                    intervention_instance_id = int(k.split("_")[-1])
                    if allocation is not None:
                        if created:
                            CostLineItemInterventionAllocation.objects.create(
                                cli_config=config,
                                intervention_instance_id=intervention_instance_id,
                                allocation=v,
                            )
                        else:
                            cli_allocation = CostLineItemInterventionAllocation.objects.filter(
                                cli_config=config,
                                intervention_instance_id=intervention_instance_id,
                            )
                            if not cli_allocation.exists():
                                CostLineItemInterventionAllocation.objects.create(
                                    cli_config=config,
                                    intervention_instance_id=intervention_instance_id,
                                    allocation=v,
                                )

                            cli_allocation.update(allocation=allocation)

        return result

    def clean(self):
        cleaned_data = super().clean()

        allocation_sum = 0
        for k, v in cleaned_data.items():
            if k.startswith("intervention_allocation_"):
                if v < 0 or v > 100:
                    raise forms.ValidationError({k: "Allocations must be between 0-100%"})
                allocation_sum += v
        if allocation_sum > 100:
            raise forms.ValidationError("Allocations for cost line item cannot exceed 100% when summed")
        return cleaned_data


class OtherHQCostLineItemForm(AddCostLineItemForm):
    ANALYSIS_COST_TYPE = AnalysisCostType.OTHER_HQ
    SUPER_TITLE = _("Other HQ Cost")

    allocation = PositiveFixedDecimalField(
        widget=PercentWidget(),
        allow_zero=True,
    )
    cost_type = forms.ModelChoiceField(
        label="Cost Type",
        queryset=CostType.objects.all(),
    )

    class Meta:
        model = CostLineItem
        fields = COMMON_COST_LINE_ITEM_FIELDS
        widgets = {
            **COMMON_WIDGETS,
            **{
                "loe_or_unit": forms.HiddenInput(),
                "quantity": forms.HiddenInput(),
                "total_cost": CurrencyWidget(),
                "unit_cost": forms.HiddenInput(),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["budget_line_description"].label = _("What is the name of the other HQ Costs?")
        self.fields["total_cost"].label = _("What is the total cost?")

        # Remove the default (used to prevent errors on other forms) when adding
        if not self.instance.id:
            self.initial.pop("total_cost", None)

        if self.instance.id and self.instance.config:
            self.fields["cost_type"].initial = self.instance.config.cost_type
        else:
            # The Default Cost Type for Other HQ costs is different from the one set in the
            #   Settings file for the rest of the CostLineItems
            self.fields["cost_type"].initial = CostType.objects.get(name="Support Costs")

    def save(self, commit=True):
        cost_line_item = super().save(commit=commit)
        cost_line_item.config.cost_type = self.cleaned_data["cost_type"]
        cost_line_item.config.save()
        return cost_line_item


class InKindCostLineItemForm(AddCostLineItemForm):
    ANALYSIS_COST_TYPE = AnalysisCostType.IN_KIND
    SUPER_TITLE = _("In-Kind Contributions")

    allocation = PositiveFixedDecimalField(
        widget=PercentWidget(),
        allow_zero=True,
    )

    class Meta:
        model = CostLineItem
        fields = COMMON_COST_LINE_ITEM_FIELDS
        widgets = {
            **COMMON_WIDGETS,
            **{
                "loe_or_unit": forms.HiddenInput(),
                "total_cost": forms.HiddenInput(),
                "unit_cost": CurrencyWidget(),
                "budget_line_description": forms.TextInput(
                    attrs={"placeholder": "Example: Medical Supplies"}
                ),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["budget_line_description"].label = _(
            "What is the name of the item that was contributed in-kind?"
        )
        self.fields["quantity"].label = _("How many items were contributed in-kind?")
        self.fields["unit_cost"].label = _("What is the unit cost per item?")

    def clean(self):
        cleaned_data = super().clean()

        quantity = cleaned_data.get("quantity", 0)
        unit_cost = cleaned_data.get("unit_cost", 0)
        total_cost = quantity * unit_cost
        cleaned_data["total_cost"] = round(Decimal(total_cost), 4)

        return cleaned_data


class ClientTimeCostLineItemForm(AddCostLineItemForm):
    ANALYSIS_COST_TYPE = AnalysisCostType.CLIENT_TIME
    SUB_TITLE = _("Client Time Cost")
    SUPER_TITLE = _("Client Time")

    class Meta:
        model = CostLineItem
        fields = COMMON_COST_LINE_ITEM_FIELDS
        widgets = {
            **COMMON_WIDGETS,
            **{
                "total_cost": forms.HiddenInput(),
                "unit_cost": CurrencyWidget(),
                "budget_line_description": forms.TextInput(attrs={"placeholder": "Example: Caregivers"}),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        country_name = self.analysis.country.name

        self.fields["intervention_instance"] = InterventionInstanceChoiceField(
            label="Which Intervention is this for?",
            queryset=self.analysis.interventioninstance_set.all(),
            initial=(self.instance.config.get_sole_allocator if hasattr(self.instance, "config") else None),
        )

        self.fields["budget_line_description"].label = _("What is the name of this group of clients?")
        self.fields["loe_or_unit"].label = _(f"How many of them participated in this intervention?")
        self.fields["quantity"].label = _(
            f"How many hours did each of them spend to participate in this intervention?"
        )
        self.fields["unit_cost"].label = _(f"Hourly cost per person for {country_name}")

        # Note should be last field
        self.fields["note"] = self.fields.pop("note")

    def clean(self):
        cleaned_data = super().clean()

        loe_or_unit = cleaned_data.get("loe_or_unit", 0)
        quantity = cleaned_data.get("quantity", 0)
        unit_cost = cleaned_data.get("unit_cost", 0)
        total_cost = loe_or_unit * quantity * unit_cost
        cleaned_data["total_cost"] = round(Decimal(total_cost), 4)

        return cleaned_data

    def save(self, commit=True):
        # We call the save command of the parent's parent NOT the parent
        # because this form is special in that it creates a line item
        # with 100% allocation to a single event
        result = super(AddCostLineItemForm, self).save(commit=commit)
        if commit:
            config, _ = CostLineItemConfig.objects.get_or_create(
                cost_line_item=result,
                defaults={
                    "analysis_cost_type": self.ANALYSIS_COST_TYPE,
                },
            )

            intervention_instance = self.cleaned_data["intervention_instance"]

            existing_allocations = CostLineItemInterventionAllocation.objects.filter(cli_config=config).all()
            for each_allocation in existing_allocations:
                if each_allocation.intervention_instance != intervention_instance:
                    each_allocation.allocation = 0
                    each_allocation.save()

            (
                relevant_allocation,
                _,
            ) = CostLineItemInterventionAllocation.objects.get_or_create(
                cli_config=config,
                intervention_instance=intervention_instance,
            )
            relevant_allocation.allocation = 100
            relevant_allocation.save()

        return result
