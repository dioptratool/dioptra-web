"""Feature 95: the metadata value controls and the definition draft forms."""

import json

import pytest
from django import forms

from website.forms.intervention_metadata import (
    MetadataDraftField,
    MetadataFieldDraftForm,
    MetadataNumberField,
    OptionLabelForm,
    control_for,
    metadata_field_name,
    metadata_from_cleaned_data,
)
from website.forms.widgets import MetadataNumberWidget
from website.models import MetadataFieldType, MetadataNumberType
from website.tests.factories import InterventionMetadataFieldFactory, InterventionMetadataOptionFactory


class TestMetadataNumberField:
    def test_optional_and_trimmed(self):
        field = MetadataNumberField(MetadataNumberType.INTEGER)
        assert field.clean("") == ""
        assert field.clean("  42 ") == "42"

    def test_subtype_rules_apply(self):
        with pytest.raises(forms.ValidationError):
            MetadataNumberField(MetadataNumberType.INTEGER).clean("1.5")
        assert MetadataNumberField(MetadataNumberType.DECIMAL).clean("1.5") == "1.5"
        with pytest.raises(forms.ValidationError):
            MetadataNumberField(MetadataNumberType.DECIMAL).clean("1" * 21)


@pytest.mark.django_db
class TestControls:
    def test_free_text_is_a_255_character_optional_input(self):
        field = control_for(InterventionMetadataFieldFactory(name="Partner"))
        assert isinstance(field, forms.CharField)
        assert field.required is False
        assert field.label == "Partner"
        assert field.max_length == 255

    def test_single_choice_offers_a_blank_and_the_options_by_key(self):
        definition = InterventionMetadataFieldFactory(field_type=MetadataFieldType.SINGLE_CHOICE)
        a = InterventionMetadataOptionFactory(field=definition, label="A", order=0)
        b = InterventionMetadataOptionFactory(field=definition, label="B", order=1)
        field = control_for(definition)
        assert isinstance(field, forms.ChoiceField)
        assert field.choices == [("", "(Choose)"), (a.storage_key, "A"), (b.storage_key, "B")]

    def test_multiple_choice_is_a_checkbox_group(self):
        definition = InterventionMetadataFieldFactory(field_type=MetadataFieldType.MULTIPLE_CHOICE)
        InterventionMetadataOptionFactory(field=definition, label="X")
        field = control_for(definition)
        assert isinstance(field, forms.MultipleChoiceField)
        assert isinstance(field.widget, forms.CheckboxSelectMultiple)

    @pytest.mark.parametrize(
        "number_type,affix",
        [
            (MetadataNumberType.PERCENTAGE, "%"),
            (MetadataNumberType.INTEGER, "Enter a whole number"),
            (MetadataNumberType.DECIMAL, "Enter a decimal number"),
        ],
    )
    def test_number_controls_use_the_text_backed_widget(self, number_type, affix):
        definition = InterventionMetadataFieldFactory(
            name="N", field_type=MetadataFieldType.NUMBER, number_type=number_type
        )
        field = control_for(definition)
        assert isinstance(field, MetadataNumberField)
        assert isinstance(field.widget, MetadataNumberWidget)
        html = field.widget.render(metadata_field_name(definition), "12.5")
        assert 'type="text"' in html
        assert 'inputmode="decimal"' in html
        assert 'value="12.5"' in html
        assert affix in html or affix in str(field.help_text)

    def test_currency_control_shows_the_symbol_without_a_step_restriction(self):
        definition = InterventionMetadataFieldFactory(
            field_type=MetadataFieldType.NUMBER, number_type=MetadataNumberType.CURRENCY
        )
        widget = control_for(definition).widget
        html = widget.render("x", "1000.123")
        assert "step=" not in html
        assert 'type="number"' not in html
        if widget.currency_symbol:
            assert widget.currency_symbol in html

    def test_values_are_collected_by_storage_key_without_blanks(self):
        text = InterventionMetadataFieldFactory(name="T")
        multi = InterventionMetadataFieldFactory(name="M", field_type=MetadataFieldType.MULTIPLE_CHOICE)
        number = InterventionMetadataFieldFactory(
            name="N", field_type=MetadataFieldType.NUMBER, number_type=MetadataNumberType.INTEGER
        )
        cleaned = {
            metadata_field_name(text): "",
            metadata_field_name(multi): ["k1", "k2"],
            metadata_field_name(number): "0",
        }
        assert metadata_from_cleaned_data([text, multi, number], cleaned) == {
            multi.storage_key: ["k1", "k2"],
            number.storage_key: "0",
        }


class TestDraftForms:
    def test_draft_field_defaults_and_rejects_other_shapes(self):
        field = MetadataDraftField()
        assert field.clean("") == {"fields": []}
        assert field.clean('{"fields": [{"name": "x"}]}') == {"fields": [{"name": "x"}]}
        with pytest.raises(forms.ValidationError):
            field.clean('{"nope": 1}')
        with pytest.raises(forms.ValidationError):
            field.clean("[1, 2]")

    def test_field_draft_form_returns_a_normalized_row(self):
        form = MetadataFieldDraftForm(
            data={
                "name": "  Treatment Approach ",
                "field_type": MetadataFieldType.MULTIPLE_CHOICE,
                "options": json.dumps(
                    [{"label": " Community ", "draft_id": "o1"}, {"label": "Inpatient", "id": "7"}]
                ),
                "id": "3",
                "key": "abc",
                "in_use": "true",
            }
        )
        assert form.is_valid(), form.errors
        row = form.normalized_row
        assert row["name"] == "Treatment Approach"
        assert row["id"] == 3
        assert row["key"] == "abc"
        assert row["in_use"] is True
        assert row["draft_id"]
        assert [(o["label"], o["draft_id"], o["id"]) for o in row["options"]] == [
            ("Community", "o1", None),
            ("Inpatient", row["options"][1]["draft_id"], 7),
        ]

    def test_field_draft_form_reports_rules_per_input(self):
        form = MetadataFieldDraftForm(
            data={"name": "", "field_type": MetadataFieldType.NUMBER, "options": "[]"}
        )
        assert not form.is_valid()
        assert "name" in form.errors
        assert "number_type" in form.errors

        form = MetadataFieldDraftForm(
            data={"name": "C", "field_type": MetadataFieldType.SINGLE_CHOICE, "options": "[]"}
        )
        assert not form.is_valid()
        assert "options" in form.errors

        form = MetadataFieldDraftForm(
            data={"name": "C", "field_type": MetadataFieldType.SINGLE_CHOICE, "options": "not json"}
        )
        assert not form.is_valid()
        assert "options" in form.errors

    def test_option_label_form(self):
        assert OptionLabelForm(data={"label": " Outpatient "}).is_valid()
        assert not OptionLabelForm(data={"label": ""}).is_valid()
        assert not OptionLabelForm(data={"label": "x" * 101}).is_valid()
