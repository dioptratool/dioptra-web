from decimal import Decimal, DecimalException

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
    SubcomponentCostAllocation,
)
from website.models.cost_line_item import CostLineItemInterventionAllocation
from website.models.cost_type import Support

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
            #   Settings file for the rest of the CostLineItems. Cost type names are
            #   admin-editable, so look it up by its fixed type; without a match the user
            #   simply picks one manually.
            self.fields["cost_type"].initial = CostType.objects.filter(type=Support.id).first()

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

    class Media:
        js = ("website/js/bulk-allocate-form.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["budget_line_description"].label = _(
            "What is the name of the item that was contributed in-kind?"
        )
        self.fields["quantity"].label = _("How many items were contributed in-kind?")
        self.fields["unit_cost"].label = _("What is the unit cost per item?")
        self._add_subcomponent_allocation_fields()
        self._build_allocation_groups()

    def _subcomponent_allocations_by_analysis_id(self):
        if not (self.instance and self.instance.id and hasattr(self.instance, "config")):
            return {}

        return {
            allocation.subcomponent_analysis_id: allocation
            for allocation in self.instance.config.subcomponent_cost_allocations.all()
        }

    def _add_subcomponent_allocation_fields(self):
        existing_allocations = self._subcomponent_allocations_by_analysis_id()
        for intervention_instance in self.analysis.interventioninstance_set.all():
            if not hasattr(intervention_instance, "subcomponent_cost_analysis"):
                continue

            subcomponent_analysis = intervention_instance.subcomponent_cost_analysis
            allocation_row = existing_allocations.get(subcomponent_analysis.id)
            allocations = allocation_row.allocations if allocation_row else {}
            for idx, label in enumerate(subcomponent_analysis.subcomponent_labels or []):
                self.fields[self.subcomponent_field_name(subcomponent_analysis.id, idx)] = (
                    PositiveFixedDecimalField(
                        label=label,
                        initial=allocations.get(str(idx), ""),
                        widget=PercentWidget(),
                        help_text="Enter a percent amount between 0 and 100",
                        allow_zero=True,
                        required=False,
                    )
                )

    @staticmethod
    def subcomponent_field_name(subcomponent_analysis_id, idx):
        return f"intervention_subcomponent_allocation_{subcomponent_analysis_id}_{idx}"

    @staticmethod
    def is_intervention_allocation_field(field_name):
        return field_name.startswith("intervention_allocation_")

    @classmethod
    def is_subcomponent_allocation_field(cls, field_name):
        return field_name.startswith("intervention_subcomponent_allocation_")

    def _build_allocation_groups(self):
        for field_name, field in self.fields.items():
            if self.is_intervention_allocation_field(field_name) or self.is_subcomponent_allocation_field(
                field_name
            ):
                classes = field.widget.attrs.get("class", "").split()
                if "bulk-allocation-input" not in classes:
                    classes.append("bulk-allocation-input")
                field.widget.attrs["class"] = " ".join(classes)

        allocation_groups = []
        for intervention_instance in self.analysis.interventioninstance_set.all():
            allocation_field_name = f"intervention_allocation_{intervention_instance.id}"
            group = {
                "intervention": intervention_instance,
                "allocation_field": self[allocation_field_name],
                "subcomponent_fields": [],
                "subcomponent_total": None,
            }

            if hasattr(intervention_instance, "subcomponent_cost_analysis"):
                subcomponent_analysis = intervention_instance.subcomponent_cost_analysis
                total = Decimal(0)
                total_has_value = False
                for idx, label in enumerate(subcomponent_analysis.subcomponent_labels or []):
                    field = self[self.subcomponent_field_name(subcomponent_analysis.id, idx)]
                    group["subcomponent_fields"].append(
                        {
                            "label": label,
                            "field": field,
                        }
                    )
                    value = field.value()
                    if value not in (None, ""):
                        try:
                            total += Decimal(str(value))
                            total_has_value = True
                        except DecimalException:
                            pass

                group["subcomponent_total"] = total if total_has_value else Decimal(0)

            allocation_groups.append(group)

        self.allocation_groups = allocation_groups
        self.non_allocation_fields = [
            self[field_name]
            for field_name in self.fields
            if not self.is_intervention_allocation_field(field_name)
            and not self.is_subcomponent_allocation_field(field_name)
            and not self[field_name].is_hidden
            and field_name != "note"
        ]
        self.note_field = self["note"] if "note" in self.fields else None

    def clean(self):
        cleaned_data = super().clean()

        quantity = cleaned_data.get("quantity", 0)
        unit_cost = cleaned_data.get("unit_cost", 0)
        total_cost = quantity * unit_cost
        cleaned_data["total_cost"] = round(Decimal(total_cost), 4)
        self._clean_subcomponent_allocations(cleaned_data)

        return cleaned_data

    def _clean_subcomponent_allocations(self, cleaned_data):
        for intervention_instance in self.analysis.interventioninstance_set.all():
            if not hasattr(intervention_instance, "subcomponent_cost_analysis"):
                continue

            allocation = cleaned_data.get(f"intervention_allocation_{intervention_instance.id}")
            if allocation in (None, 0):
                continue

            subcomponent_analysis = intervention_instance.subcomponent_cost_analysis
            labels = subcomponent_analysis.subcomponent_labels or []
            if not labels:
                continue

            allocation_sum = Decimal(0)
            has_error = False
            for idx, _label in enumerate(labels):
                field_name = self.subcomponent_field_name(subcomponent_analysis.id, idx)
                subcomponent_allocation = cleaned_data.get(field_name)
                if subcomponent_allocation is None:
                    self.add_error(field_name, _("This field is required."))
                    has_error = True
                    continue
                if subcomponent_allocation < 0 or subcomponent_allocation > 100:
                    self.add_error(field_name, _("Allocations must be between 0-100%."))
                    has_error = True
                allocation_sum += subcomponent_allocation

            if not has_error and allocation_sum != Decimal(100):
                for idx, _label in enumerate(labels):
                    field_name = self.subcomponent_field_name(subcomponent_analysis.id, idx)
                    self.add_error(field_name, _("Sub-component allocations must total 100%."))

    def save(self, commit=True):
        result = super().save(commit=commit)
        if commit:
            self._save_subcomponent_allocations(result.config)

        return result

    def _save_subcomponent_allocations(self, config):
        for intervention_instance in self.analysis.interventioninstance_set.all():
            if not hasattr(intervention_instance, "subcomponent_cost_analysis"):
                continue

            subcomponent_analysis = intervention_instance.subcomponent_cost_analysis
            labels = subcomponent_analysis.subcomponent_labels or []
            if not labels:
                continue

            intervention_allocation = self.cleaned_data.get(
                f"intervention_allocation_{intervention_instance.id}"
            )
            if not intervention_allocation:
                SubcomponentCostAllocation.objects.filter(
                    cli_config=config,
                    subcomponent_analysis=subcomponent_analysis,
                ).delete()
                continue

            allocations = {}
            for idx, _label in enumerate(labels):
                allocation = self.cleaned_data.get(
                    self.subcomponent_field_name(subcomponent_analysis.id, idx)
                )
                if allocation is not None:
                    allocations[str(idx)] = str(allocation)

            SubcomponentCostAllocation.objects.update_or_create(
                cli_config=config,
                subcomponent_analysis=subcomponent_analysis,
                defaults={
                    "allocations": allocations,
                    "skipped": False,
                },
            )


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
        self.fields["loe_or_unit"].label = _("How many of them participated in this intervention?")
        self.fields["quantity"].label = _(
            "How many hours did each of them spend to participate in this intervention?"
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
