"""Form pieces for intervention metadata: value controls per definition, and the definition drafts."""

import json

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _l

from website.currency import currency_symbol
from website.forms.widgets import MetadataNumberWidget
from website.intervention_metadata import normalize_field_row, validate_number
from website.models.intervention_metadata import (
    FREE_TEXT_MAX_LENGTH,
    NAME_MAX_LENGTH,
    MetadataFieldType,
    MetadataNumberType,
)

FIELD_NAME_PREFIX = "metadata__"

NUMBER_HELP_TEXTS = {
    MetadataNumberType.INTEGER: _l("Enter a whole number"),
    MetadataNumberType.DECIMAL: _l("Enter a decimal number"),
}


class MetadataNumberField(forms.CharField):
    """A number kept as the exact string entered, validated for its subtype."""

    def __init__(self, number_type, **kwargs):
        self.number_type = number_type
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def validate(self, value):
        super().validate(value)
        if value:
            validate_number(value, self.number_type)


def metadata_field_name(definition) -> str:
    return f"{FIELD_NAME_PREFIX}{definition.storage_key}"


def is_metadata_field_name(name: str) -> bool:
    return name.startswith(FIELD_NAME_PREFIX)


def control_for(definition, analysis=None) -> forms.Field:
    """The optional form field that enters a value for one definition."""
    common = {"label": definition.name, "required": False}
    if definition.field_type == MetadataFieldType.FREE_TEXT:
        return forms.CharField(max_length=FREE_TEXT_MAX_LENGTH, **common)
    if definition.field_type == MetadataFieldType.SINGLE_CHOICE:
        choices = [("", _l("(Choose)"))] + [
            (option.storage_key, option.label) for option in definition.options.all()
        ]
        return forms.ChoiceField(choices=choices, **common)
    if definition.field_type == MetadataFieldType.MULTIPLE_CHOICE:
        choices = [(option.storage_key, option.label) for option in definition.options.all()]
        return forms.MultipleChoiceField(choices=choices, widget=forms.CheckboxSelectMultiple, **common)
    return MetadataNumberField(
        definition.number_type,
        widget=MetadataNumberWidget(definition.number_type, currency_symbol(analysis)),
        help_text=NUMBER_HELP_TEXTS.get(definition.number_type, ""),
        **common,
    )


def metadata_from_cleaned_data(definitions, cleaned_data: dict) -> dict:
    """The JSON to store for the given definitions from a validated form; blanks are left out."""
    metadata = {}
    for definition in definitions:
        value = cleaned_data.get(metadata_field_name(definition))
        if value in (None, "", []):
            continue
        metadata[definition.storage_key] = list(value) if isinstance(value, (list, tuple)) else value
    return metadata


class MetadataDraftField(forms.JSONField):
    """The hidden definition draft on the intervention form."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("widget", forms.HiddenInput)
        super().__init__(**kwargs)

    def prepare_value(self, value):
        # The draft is handed around as its JSON text; do not quote it a second time.
        if isinstance(value, str):
            return value
        return super().prepare_value(value)

    def clean(self, value):
        value = super().clean(value)
        if value in (None, ""):
            return {"fields": []}
        if not isinstance(value, dict) or not isinstance(value.get("fields"), list):
            raise ValidationError(_l("Invalid metadata draft."), code="invalid")
        return value


class MetadataFieldDraftForm(forms.Form):
    """
    The child panel for one field of the draft. Nothing is saved: a valid submission returns the
    normalized row to the parent editor.
    """

    # The editor script fills the controls from the parent's draft; that is not an abandonable edit.
    allow_abandonment = True

    class Media:
        js = ("panels/lib/Sortable.js", "website/js/intervention-metadata-editor.js")

    draft_id = forms.CharField(widget=forms.HiddenInput, required=False)
    id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    key = forms.CharField(widget=forms.HiddenInput, required=False)
    in_use = forms.BooleanField(widget=forms.HiddenInput, required=False)
    name = forms.CharField(label=_l("Name"), max_length=NAME_MAX_LENGTH)
    field_type = forms.ChoiceField(
        label=_l("Type"), choices=[("", _l("(Choose)"))] + MetadataFieldType.choices
    )
    number_type = forms.ChoiceField(
        label=_l("Number type"), choices=[("", _l("(Choose)"))] + MetadataNumberType.choices, required=False
    )
    options = forms.CharField(widget=forms.HiddenInput, required=False)

    def clean_options(self):
        raw = self.cleaned_data.get("options") or "[]"
        try:
            options = json.loads(raw)
        except ValueError:
            raise ValidationError(_l("Invalid options."), code="invalid")
        if not isinstance(options, list):
            raise ValidationError(_l("Invalid options."), code="invalid")
        return options

    def clean(self):
        cleaned = super().clean()
        self.normalized_row = None
        try:
            self.normalized_row = normalize_field_row(
                {
                    "draft_id": cleaned.get("draft_id"),
                    "id": cleaned.get("id"),
                    "key": cleaned.get("key"),
                    "in_use": cleaned.get("in_use"),
                    "name": cleaned.get("name"),
                    "field_type": cleaned.get("field_type"),
                    "number_type": cleaned.get("number_type"),
                    "options": cleaned.get("options"),
                }
            )
        except ValidationError as error:
            for field, messages in error.message_dict.items():
                if field in self.errors:
                    continue  # already reported by the field's own validation
                for message in messages:
                    self.add_error(field if field in self.fields else None, message)
        return cleaned


class OptionLabelForm(forms.Form):
    """The one-field child panel that renames an option; its identity travels untouched."""

    allow_abandonment = True

    class Media:
        js = ("website/js/intervention-metadata-editor.js",)

    label = forms.CharField(label=_l("Label"), max_length=NAME_MAX_LENGTH)
