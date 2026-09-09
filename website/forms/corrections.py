"""
Edit panels for cost items and transactions (Feature 91, spec section 5).

One form class serves every panel: the field set follows the section 5 matrix (record kind and
step), every field is a patch input where blank means "make no change", and a bulk selection
prefills a field only when all selected records agree, otherwise showing a grey
``<multiple values>`` placeholder. Grant, Site, Sector Code and Account Code are closed searchable
lists (section 5) rendered with ``FilterableChoiceWidget``: a value that appears on no row cannot be
entered.
"""

from __future__ import annotations

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _l

from ombucore.admin.widgets import FlatpickrDateWidget
from website.corrections import TRANSACTION, CorrectionPatch, field_labels
from website.corrections.fields import (
    MULTIPLE,
    account_code_choices,
    code_suggestions,
    grant_choices,
    visible_custom_fields,
)
from website.corrections.patch import CUSTOM_FIELD_NAMES
from website.forms.widgets import FilterableChoiceWidget
from website.models import Category, CostType

MULTIPLE_VALUES_PLACEHOLDER = "<multiple values>"
DERIVED_AMOUNT_HELP_TEXT = _l(
    "This amount is calculated from the underlying transactions. Edit transaction amounts to change it."
)
DESCRIPTION_SCOPE_HELP_TEXT = _l(
    "Applies to the cost item these transactions belong to and to all of its transactions."
)


class CorrectionForm(forms.Form):
    """
    ``record_kind``: what the panel edits (``COST_ITEM`` or ``TRANSACTION``).
    ``step``: ``"categorize"`` or ``"allocate"``; Cost Type and Category appear only on Confirm
    Categories panels.
    ``custom_family``: which custom fields the panel offers (``"ci"`` or ``"tr"``).
    ``amount_editable``: False on a transaction-based cost-item panel, where Amount is derived.
    ``initial_values``: field name -> value, or ``MULTIPLE`` when the selection disagrees.
    """

    def __init__(
        self,
        *args,
        analysis,
        record_kind,
        step,
        custom_family,
        amount_editable=True,
        initial_values=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.analysis = analysis
        self.record_kind = record_kind
        self.step = step
        self.custom_family = custom_family
        self.labels = field_labels(record_kind, custom_family)
        initial_values = initial_values or {}

        if step == "categorize":
            self.fields["cost_type"] = forms.ModelChoiceField(
                CostType.objects.all(), required=False, empty_label=""
            )
            self.fields["category"] = forms.ModelChoiceField(
                Category.objects.all(), required=False, empty_label=""
            )
        # The cost item's description on every panel; from a transaction panel it still applies to
        # the whole cost item (section 5).
        self.fields["description"] = forms.CharField(required=False, max_length=1000)
        if record_kind == TRANSACTION:
            self.fields["description"].help_text = DESCRIPTION_SCOPE_HELP_TEXT
            self.fields["transaction_description"] = forms.CharField(required=False)
        self.fields["grant_code"] = _closed_list([(grant, grant) for grant in grant_choices(analysis)])
        for name in ("site_code", "sector_code"):
            self.fields[name] = _closed_list([(v, v) for v in code_suggestions(analysis, name)])
        self.fields["account_code"] = _closed_list(account_code_choices(analysis))
        if record_kind == TRANSACTION:
            self.fields["date"] = forms.DateField(
                required=False,
                input_formats=settings.DATE_INPUT_FORMATS,
                widget=FlatpickrDateWidget(
                    options={
                        "dateFormat": settings.DATE_FORMAT,
                        "minDate": analysis.start_date.isoformat(),
                        "maxDate": analysis.end_date.isoformat(),
                        "allowInput": True,
                    },
                    format="%d-%b-%Y",
                ),
                help_text=_l("Between {start} and {end}.").format(
                    start=analysis.start_date.strftime("%d-%b-%Y"),
                    end=analysis.end_date.strftime("%d-%b-%Y"),
                ),
            )
        self.fields["amount"] = forms.DecimalField(
            required=False,
            max_digits=14,
            decimal_places=settings.DECIMAL_PLACES,
            widget=forms.TextInput(attrs={"inputmode": "decimal"}),
        )
        if not amount_editable:
            self.fields["amount"].disabled = True
            self.fields["amount"].help_text = DERIVED_AMOUNT_HELP_TEXT
        # Custom fields form the last group, after Amount (section 5).
        for name in visible_custom_fields(analysis, custom_family):
            self.fields[name] = forms.CharField(required=False, max_length=255)

        for name, field in self.fields.items():
            field.label = self.labels[name]
            self._prefill(name, field, initial_values.get(name))

    def _prefill(self, name, field, value):
        if value is MULTIPLE:
            if isinstance(field.widget, FilterableChoiceWidget):
                field.widget.attrs["placeholder"] = MULTIPLE_VALUES_PLACEHOLDER
            elif isinstance(field.widget, forms.Select):
                self._set_blank_label(field, MULTIPLE_VALUES_PLACEHOLDER)
            else:
                field.widget.attrs["placeholder"] = MULTIPLE_VALUES_PLACEHOLDER
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} correction-field--multiple".strip()
            return
        if value is not None:
            field.initial = value

    @staticmethod
    def _set_blank_label(field, label):
        if isinstance(field, forms.ModelChoiceField):
            field.empty_label = label
        else:
            field.choices = [(value, label if value == "" else text) for value, text in field.choices]

    def clean_date(self):
        value = self.cleaned_data.get("date")
        if value and not (self.analysis.start_date <= value <= self.analysis.end_date):
            raise ValidationError(
                _l("The date must be between {start} and {end}.").format(
                    start=self.analysis.start_date.strftime("%d-%b-%Y"),
                    end=self.analysis.end_date.strftime("%d-%b-%Y"),
                )
            )
        return value

    def to_patch(self) -> CorrectionPatch:
        """The non-empty, editable fields as a patch; everything else is "no change"."""

        def value(name):
            field = self.fields.get(name)
            if field is None or field.disabled:
                return None
            cleaned = self.cleaned_data.get(name)
            if cleaned is None or cleaned == "":
                return None
            return cleaned

        return CorrectionPatch(
            cost_type=value("cost_type"),
            category=value("category"),
            description=value("description"),
            transaction_description=value("transaction_description"),
            grant_code=value("grant_code"),
            site_code=value("site_code"),
            sector_code=value("sector_code"),
            account_code=value("account_code"),
            date=value("date"),
            amount=value("amount"),
            custom_fields={name: value(name) for name in CUSTOM_FIELD_NAMES if name in self.fields},
        )


def _closed_list(choices):
    """
    A filterable dropdown of the given (value, label) pairs; blank means "no change" and only a
    listed value validates.

    The saved value is always the code; a label such as "code — description" is display only.
    """
    return forms.ChoiceField(required=False, choices=[("", ""), *choices], widget=FilterableChoiceWidget)
