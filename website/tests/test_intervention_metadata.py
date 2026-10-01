"""Feature 95: intervention metadata definitions and the value contract on intervention instances."""

import datetime
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from website.currency import currency_symbol
from website.intervention_metadata import (
    build_draft,
    excel_number_format,
    format_number,
    metadata_usage,
    MetadataDraftError,
    prune_metadata,
    resolve_metadata,
    save_draft,
    validate_draft,
    validate_number,
)
from website.models import (
    Intervention,
    InterventionInstance,
    InterventionMetadataField,
    InterventionMetadataOption,
    MetadataFieldType,
    MetadataNumberType,
)
from website.tests.factories import (
    InterventionFactory,
    InterventionInstanceFactory,
    InterventionMetadataFieldFactory,
    InterventionMetadataOptionFactory,
)
from website.intervention_metadata import excel_number, metadata_lookup, significant_digits
from website.models import Analysis
from website.tests.factories import AnalysisFactory


def stored(instance):
    return InterventionInstance.objects.get(pk=instance.pk)


@pytest.mark.django_db
class TestInstanceMetadataValues:
    def test_new_instances_start_with_their_own_empty_dict(self):
        first = InterventionInstanceFactory()
        second = InterventionInstanceFactory()
        assert first.metadata == {}
        assert second.metadata == {}
        first.metadata["k"] = "v"
        assert second.metadata == {}
        assert stored(second).metadata == {}

    def test_strings_and_lists_of_strings_round_trip_exactly(self):
        number = "-1234567890.123456789"
        text = 'quotes " backslash \\ tab \t newline \n return \r non-ascii éλ中 emoji 🙂'
        value = {str(uuid.uuid4()): number, str(uuid.uuid4()): ["a", "b"], str(uuid.uuid4()): text}

        instance = InterventionInstanceFactory(metadata=value)

        assert stored(instance).metadata == value

    def test_zero_is_a_value(self):
        key = str(uuid.uuid4())
        instance = InterventionInstanceFactory(metadata={key: "0"})
        assert stored(instance).metadata == {key: "0"}

    @pytest.mark.parametrize("bad", [{"k": 1}, {"k": [1]}, {"k": None}, {"k": {"nested": "x"}}, ["list"]])
    def test_other_shapes_are_rejected_on_save(self, bad):
        instance = InterventionInstanceFactory()
        instance.metadata = bad
        with pytest.raises(ValidationError):
            instance.save()

    def test_metadata_is_independent_of_the_metric_parameters(self):
        key = str(uuid.uuid4())
        instance = InterventionInstanceFactory(parameters={"number_of_people": 5.0}, metadata={key: "x"})
        row = stored(instance)
        assert row.parameters == {"number_of_people": 5.0}
        assert row.metadata == {key: "x"}


@pytest.mark.django_db
class TestDefinitions:
    def test_fields_belong_to_one_intervention_in_configured_order(self):
        intervention = InterventionFactory()
        second = InterventionMetadataFieldFactory(intervention=intervention, name="B", order=2)
        first = InterventionMetadataFieldFactory(intervention=intervention, name="A", order=1)
        InterventionMetadataFieldFactory(name="Elsewhere")

        assert list(intervention.metadata_fields.all()) == [first, second]

    def test_keys_are_server_generated_and_unique(self):
        field = InterventionMetadataFieldFactory()
        other = InterventionMetadataFieldFactory()
        option = InterventionMetadataOptionFactory()
        assert isinstance(field.key, uuid.UUID)
        assert field.key != other.key
        assert field.storage_key == str(field.key)
        assert option.storage_key == str(option.key)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                InterventionMetadataFieldFactory(key=field.key)

    def test_names_are_unique_within_an_intervention_regardless_of_case(self):
        intervention = InterventionFactory()
        InterventionMetadataFieldFactory(intervention=intervention, name="Partner")

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                InterventionMetadataFieldFactory(intervention=intervention, name="PARTNER")

        # The same name on another intervention is fine.
        InterventionMetadataFieldFactory(name="partner")
        assert InterventionMetadataField.objects.filter(name__iexact="partner").count() == 2

    def test_a_number_field_needs_a_number_type_and_nothing_else_may_have_one(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                InterventionMetadataFieldFactory(field_type=MetadataFieldType.NUMBER, number_type=None)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                InterventionMetadataFieldFactory(
                    field_type=MetadataFieldType.FREE_TEXT, number_type=MetadataNumberType.INTEGER
                )
        field = InterventionMetadataFieldFactory(
            field_type=MetadataFieldType.NUMBER, number_type=MetadataNumberType.CURRENCY
        )
        assert field.is_number and not field.is_choice

    def test_rotating_the_key_retires_the_old_storage_key(self):
        field = InterventionMetadataFieldFactory()
        old = field.key
        field.rotate_key()
        field.save()
        assert InterventionMetadataField.objects.get(pk=field.pk).key != old

    def test_options_keep_their_order_and_cascade_with_their_field(self):
        field = InterventionMetadataFieldFactory(field_type=MetadataFieldType.MULTIPLE_CHOICE)
        later = InterventionMetadataOptionFactory(field=field, label="B", order=2)
        earlier = InterventionMetadataOptionFactory(field=field, label="A", order=1)
        assert list(field.options.all()) == [earlier, later]
        assert field.is_choice

        field.delete()

        assert not InterventionMetadataOption.objects.filter(pk__in=[earlier.pk, later.pk]).exists()

    def test_deleting_an_intervention_removes_its_definitions(self):
        field = InterventionMetadataFieldFactory(field_type=MetadataFieldType.SINGLE_CHOICE)
        InterventionMetadataOptionFactory(field=field)
        Intervention.objects.filter(pk=field.intervention_id).delete()
        assert not InterventionMetadataField.objects.filter(pk=field.pk).exists()
        assert not InterventionMetadataOption.objects.filter(field_id=field.pk).exists()


# ---------------------------------------------------------------------------------------------
# Numeric rules
# ---------------------------------------------------------------------------------------------

TWENTY_DIGITS = "1234567890123456789.0"


class TestNumberRules:
    @pytest.mark.parametrize("value", ["0", "-1", "125", "-0.5", "007", TWENTY_DIGITS, "0" * 20, " 12 "])
    def test_decimal_subtypes_accept_plain_numbers(self, value):
        assert validate_number(value, MetadataNumberType.DECIMAL) == value.strip()

    @pytest.mark.parametrize(
        "value",
        [
            "+1",
            "1e5",
            "1,000",
            "1.",
            ".5",
            "abc",
            "",
            "1 000",
            "--1",
            "1.2.3",
            "NaN",
            "Infinity",
            "0" * 21,
            TWENTY_DIGITS + "1",
        ],
    )
    def test_decimal_subtypes_reject_everything_else(self, value):
        with pytest.raises(ValidationError):
            validate_number(value, MetadataNumberType.DECIMAL)

    def test_integer_requires_a_whole_number(self):
        assert validate_number("-7", MetadataNumberType.INTEGER) == "-7"
        assert validate_number("0" * 20, MetadataNumberType.INTEGER) == "0" * 20
        with pytest.raises(ValidationError):
            validate_number("1.5", MetadataNumberType.INTEGER)
        with pytest.raises(ValidationError):
            validate_number("1" * 21, MetadataNumberType.INTEGER)

    def test_leading_and_trailing_zeros_count_toward_the_cap(self):
        with pytest.raises(ValidationError):
            validate_number("0" * 20 + ".0", MetadataNumberType.DECIMAL)

    @pytest.mark.parametrize("number_type", [MetadataNumberType.PERCENTAGE, MetadataNumberType.CURRENCY])
    def test_percentage_and_currency_follow_the_decimal_rules(self, number_type):
        assert validate_number("-150.25", number_type) == "-150.25"
        with pytest.raises(ValidationError):
            validate_number("12%", number_type)

    def test_display_formatting_keeps_precision_and_adds_units(self):
        assert format_number("1234567", MetadataNumberType.INTEGER) == "1,234,567"
        assert (
            format_number("-1234567890.123456789", MetadataNumberType.DECIMAL) == "-1,234,567,890.123456789"
        )
        assert format_number("125", MetadataNumberType.PERCENTAGE) == "125%"
        assert format_number("0", MetadataNumberType.INTEGER) == "0"
        assert format_number("1000.5", MetadataNumberType.CURRENCY) == f"{currency_symbol() or ''}1,000.5"


# ---------------------------------------------------------------------------------------------
# Resolving values against current definitions
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def definitions():
    """A text, a single-choice (A, B), a multiple-choice (X, Y, Z) and an integer field."""
    intervention = InterventionFactory()
    text = InterventionMetadataFieldFactory(intervention=intervention, name="Partner", order=1)
    single = InterventionMetadataFieldFactory(
        intervention=intervention, name="Age", field_type=MetadataFieldType.SINGLE_CHOICE, order=2
    )
    options_single = [
        InterventionMetadataOptionFactory(field=single, label=label, order=i) for i, label in enumerate("AB")
    ]
    multi = InterventionMetadataFieldFactory(
        intervention=intervention, name="Approach", field_type=MetadataFieldType.MULTIPLE_CHOICE, order=3
    )
    options_multi = [
        InterventionMetadataOptionFactory(field=multi, label=label, order=i) for i, label in enumerate("XYZ")
    ]
    number = InterventionMetadataFieldFactory(
        intervention=intervention,
        name="Volunteers",
        field_type=MetadataFieldType.NUMBER,
        number_type=MetadataNumberType.INTEGER,
        order=4,
    )
    return {
        "intervention": intervention,
        "text": text,
        "single": single,
        "A": options_single[0],
        "B": options_single[1],
        "multi": multi,
        "X": options_multi[0],
        "Y": options_multi[1],
        "Z": options_multi[2],
        "number": number,
    }


def instance_with(definitions, metadata):
    return InterventionInstanceFactory(intervention=definitions["intervention"], metadata=metadata)


@pytest.mark.django_db
class TestResolveMetadata:
    def test_rows_follow_the_configured_order_and_omit_blanks(self, definitions):
        d = definitions
        instance = instance_with(
            d,
            {
                d["number"].storage_key: "172",
                d["text"].storage_key: "Amoud",
                d["multi"].storage_key: [d["Z"].storage_key, d["X"].storage_key],
            },
        )
        rows = resolve_metadata(instance)
        assert [(row.name, row.display) for row in rows] == [
            ("Partner", "Amoud"),
            ("Approach", "X, Z"),
            ("Volunteers", "172"),
        ]
        assert rows[1].items == ("X", "Z")
        assert rows[1].raw == [d["X"].storage_key, d["Z"].storage_key]

    def test_zero_is_a_value_and_empty_strings_are_not(self, definitions):
        d = definitions
        instance = instance_with(d, {d["number"].storage_key: "0", d["text"].storage_key: ""})
        assert [(row.name, row.display) for row in resolve_metadata(instance)] == [("Volunteers", "0")]

    def test_retired_fields_and_options_are_left_out(self, definitions):
        d = definitions
        instance = instance_with(
            d,
            {
                str(uuid.uuid4()): "orphan",
                d["single"].storage_key: str(uuid.uuid4()),
                d["multi"].storage_key: [d["Y"].storage_key, str(uuid.uuid4())],
            },
        )
        rows = resolve_metadata(instance)
        assert [(row.name, row.display) for row in rows] == [("Approach", "Y")]

    def test_renamed_fields_and_options_display_their_current_labels(self, definitions):
        d = definitions
        instance = instance_with(d, {d["single"].storage_key: d["A"].storage_key})
        d["single"].name = "Target Age"
        d["single"].save()
        d["A"].label = "0-5 months"
        d["A"].save()
        rows = resolve_metadata(InterventionInstance.objects.get(pk=instance.pk))
        assert [(row.name, row.display) for row in rows] == [("Target Age", "0-5 months")]

    def test_malformed_stored_numbers_and_wrong_shapes_are_treated_as_blank(self, definitions):
        d = definitions
        instance = instance_with(
            d,
            {
                d["number"].storage_key: "abc",
                d["multi"].storage_key: "not-a-list",
                d["single"].storage_key: ["list"],
            },
        )
        assert resolve_metadata(instance) == []

    def test_prune_keeps_only_live_values(self, definitions):
        d = definitions
        metadata = {
            str(uuid.uuid4()): "orphan",
            d["text"].storage_key: "",
            d["single"].storage_key: d["B"].storage_key,
            d["multi"].storage_key: [d["X"].storage_key, str(uuid.uuid4())],
            d["number"].storage_key: "5",
        }
        pruned = prune_metadata(d["intervention"].metadata_fields.all(), metadata)
        assert pruned == {
            d["single"].storage_key: d["B"].storage_key,
            d["multi"].storage_key: [d["X"].storage_key],
            d["number"].storage_key: "5",
        }

    def test_usage_flags_cover_fields_and_choice_options(self, definitions):
        d = definitions
        instance_with(d, {d["text"].storage_key: "x", d["multi"].storage_key: [d["Y"].storage_key]})
        instance_with(d, {d["single"].storage_key: d["A"].storage_key, d["number"].storage_key: ""})
        used_fields, used_options = metadata_usage(d["intervention"])
        assert used_fields == {d["text"].storage_key, d["multi"].storage_key, d["single"].storage_key}
        assert used_options == {d["Y"].storage_key, d["A"].storage_key}


# ---------------------------------------------------------------------------------------------
# Definition drafts
# ---------------------------------------------------------------------------------------------


def text_row(name, **extra):
    return {"name": name, "field_type": MetadataFieldType.FREE_TEXT, **extra}


def choice_row(name, labels, field_type=MetadataFieldType.SINGLE_CHOICE, **extra):
    return {
        "name": name,
        "field_type": field_type,
        "options": [{"label": label} for label in labels],
        **extra,
    }


def rows_for(draft_fields):
    return [
        {k: v for k, v in field.items() if k in ("id", "key", "name", "field_type", "number_type", "options")}
        for field in draft_fields
    ]


def apply(intervention, fields):
    save_draft(intervention, validate_draft(intervention, {"fields": fields}))


@pytest.mark.django_db
class TestDraftValidation:
    def test_build_draft_reflects_definitions_and_usage(self, definitions):
        d = definitions
        instance_with(d, {d["text"].storage_key: "x", d["multi"].storage_key: [d["Y"].storage_key]})
        draft = build_draft(d["intervention"])
        names = [field["name"] for field in draft["fields"]]
        assert names == ["Partner", "Age", "Approach", "Volunteers"]
        by_name = {field["name"]: field for field in draft["fields"]}
        assert by_name["Partner"]["in_use"] is True
        assert by_name["Age"]["in_use"] is False
        assert by_name["Partner"]["id"] == d["text"].pk
        assert by_name["Partner"]["key"] == d["text"].storage_key
        assert [option["label"] for option in by_name["Approach"]["options"]] == ["X", "Y", "Z"]
        assert [option["in_use"] for option in by_name["Approach"]["options"]] == [False, True, False]
        assert all(field["draft_id"] for field in draft["fields"])

    def test_unsaved_or_missing_intervention_has_an_empty_draft(self):
        assert build_draft(None) == {"fields": []}
        assert build_draft(Intervention(name="new")) == {"fields": []}

    def test_twenty_fields_are_allowed_and_twenty_one_are_not(self):
        intervention = InterventionFactory()
        apply(intervention, [text_row(f"Field {n}") for n in range(20)])
        assert intervention.metadata_fields.count() == 20
        with pytest.raises(ValidationError):
            validate_draft(intervention, {"fields": [text_row(f"Field {n}") for n in range(21)]})

    @pytest.mark.parametrize(
        "field_type", [MetadataFieldType.SINGLE_CHOICE, MetadataFieldType.MULTIPLE_CHOICE]
    )
    def test_choice_fields_need_one_to_ten_options(self, field_type):
        intervention = InterventionFactory()
        for count in (0, 11):
            with pytest.raises(ValidationError):
                validate_draft(
                    intervention, {"fields": [choice_row("C", [f"o{n}" for n in range(count)], field_type)]}
                )
        for count in (1, 10):
            rows = validate_draft(
                intervention, {"fields": [choice_row("C", [f"o{n}" for n in range(count)], field_type)]}
            )
            assert len(rows[0]["options"]) == count

    def test_names_and_labels_are_limited_to_100_characters(self):
        intervention = InterventionFactory()
        validate_draft(intervention, {"fields": [text_row("n" * 100)]})
        with pytest.raises(ValidationError):
            validate_draft(intervention, {"fields": [text_row("n" * 101)]})
        validate_draft(intervention, {"fields": [choice_row("C", ["l" * 100])]})
        with pytest.raises(ValidationError):
            validate_draft(intervention, {"fields": [choice_row("C", ["l" * 101])]})

    def test_names_are_trimmed_and_unique_regardless_of_case(self):
        intervention = InterventionFactory()
        rows = validate_draft(intervention, {"fields": [text_row("  Partner  ")]})
        assert rows[0]["name"] == "Partner"
        with pytest.raises(ValidationError) as excinfo:
            validate_draft(intervention, {"fields": [text_row(" Partner"), text_row("partner ")]})
        assert "unique" in str(excinfo.value)
        # The same name on another intervention is fine.
        apply(intervention, [text_row("Partner")])
        apply(InterventionFactory(), [text_row("partner")])

    def test_number_fields_need_a_number_type_and_other_types_drop_it(self):
        intervention = InterventionFactory()
        with pytest.raises(ValidationError):
            validate_draft(intervention, {"fields": [{"name": "N", "field_type": MetadataFieldType.NUMBER}]})
        rows = validate_draft(
            intervention,
            {
                "fields": [
                    {
                        "name": "N",
                        "field_type": MetadataFieldType.NUMBER,
                        "number_type": MetadataNumberType.CURRENCY,
                    },
                    text_row("T", number_type=MetadataNumberType.INTEGER),
                ]
            },
        )
        assert rows[0]["number_type"] == MetadataNumberType.CURRENCY
        assert rows[1]["number_type"] is None
        assert rows[1]["options"] == []

    def test_foreign_and_missing_ids_are_rejected(self, definitions):
        d = definitions
        foreign = InterventionMetadataFieldFactory(name="Elsewhere")
        with pytest.raises(ValidationError):
            validate_draft(d["intervention"], {"fields": [text_row("Elsewhere", id=foreign.pk)]})
        with pytest.raises(ValidationError):
            validate_draft(d["intervention"], {"fields": [text_row("Gone", id=10**9)]})
        other_option = d["X"]
        with pytest.raises(ValidationError):
            validate_draft(
                d["intervention"],
                {
                    "fields": [
                        {
                            "id": d["single"].pk,
                            "name": "Age",
                            "field_type": MetadataFieldType.SINGLE_CHOICE,
                            "options": [{"id": other_option.pk, "label": "X"}],
                        }
                    ]
                },
            )

    def test_validation_failure_persists_nothing(self, definitions):
        d = definitions
        before = list(d["intervention"].metadata_fields.values_list("pk", "name", "key"))
        with pytest.raises(ValidationError):
            apply(d["intervention"], [text_row("Partner"), text_row("partner")])
        assert list(d["intervention"].metadata_fields.values_list("pk", "name", "key")) == before


@pytest.mark.django_db
class TestDraftPersistence:
    def test_save_creates_definitions_with_server_keys_in_order(self):
        intervention = InterventionFactory()
        apply(
            intervention,
            [
                choice_row("Approach", ["X", "Y"], MetadataFieldType.MULTIPLE_CHOICE, key="client-key"),
                {
                    "name": "Volunteers",
                    "field_type": MetadataFieldType.NUMBER,
                    "number_type": MetadataNumberType.INTEGER,
                },
                text_row("Partner"),
            ],
        )
        fields = list(intervention.metadata_fields.all())
        assert [(f.name, f.order) for f in fields] == [("Approach", 0), ("Volunteers", 1), ("Partner", 2)]
        assert all(isinstance(f.key, uuid.UUID) for f in fields)
        assert [o.label for o in fields[0].options.all()] == ["X", "Y"]
        assert fields[1].number_type == MetadataNumberType.INTEGER

    def test_rename_and_reorder_preserve_keys_and_values(self, definitions):
        d = definitions
        instance = instance_with(
            d, {d["text"].storage_key: "Amoud", d["single"].storage_key: d["A"].storage_key}
        )
        draft = build_draft(d["intervention"])["fields"]
        by_name = {f["name"]: f for f in draft}
        by_name["Partner"]["name"] = "Implementation Partner"
        by_name["Age"]["options"][0]["label"] = "0-5 months"
        reordered = [by_name["Volunteers"], by_name["Age"], by_name["Partner"], by_name["Approach"]]

        apply(d["intervention"], rows_for(reordered))

        fields = list(d["intervention"].metadata_fields.all())
        assert [f.name for f in fields] == ["Volunteers", "Age", "Implementation Partner", "Approach"]
        assert InterventionMetadataField.objects.get(pk=d["text"].pk).key == d["text"].key
        assert InterventionMetadataOption.objects.get(pk=d["A"].pk).key == d["A"].key
        rows = resolve_metadata(InterventionInstance.objects.get(pk=instance.pk))
        assert [(r.name, r.display) for r in rows] == [
            ("Age", "0-5 months"),
            ("Implementation Partner", "Amoud"),
        ]

    def test_two_fields_can_swap_names(self, definitions):
        d = definitions
        draft = build_draft(d["intervention"])["fields"]
        by_name = {f["name"]: f for f in draft}
        by_name["Partner"]["name"], by_name["Age"]["name"] = "Age", "Partner"
        apply(d["intervention"], rows_for(draft))
        assert InterventionMetadataField.objects.get(pk=d["text"].pk).name == "Age"
        assert InterventionMetadataField.objects.get(pk=d["single"].pk).name == "Partner"

    def test_type_change_rotates_the_key_and_retires_the_values(self, definitions):
        d = definitions
        instance = instance_with(d, {d["text"].storage_key: "Amoud"})
        draft = build_draft(d["intervention"])["fields"]
        partner = next(f for f in draft if f["name"] == "Partner")
        partner["field_type"] = MetadataFieldType.NUMBER
        partner["number_type"] = MetadataNumberType.DECIMAL

        apply(d["intervention"], rows_for(draft))

        field = InterventionMetadataField.objects.get(pk=d["text"].pk)
        assert field.key != d["text"].key
        assert field.field_type == MetadataFieldType.NUMBER
        assert resolve_metadata(InterventionInstance.objects.get(pk=instance.pk)) == []
        # The instance JSON itself is untouched until that instance is saved or cleaned up.
        assert InterventionInstance.objects.get(pk=instance.pk).metadata == {d["text"].storage_key: "Amoud"}

    def test_number_type_change_also_rotates_the_key(self, definitions):
        d = definitions
        draft = build_draft(d["intervention"])["fields"]
        next(f for f in draft if f["name"] == "Volunteers")["number_type"] = MetadataNumberType.PERCENTAGE
        apply(d["intervention"], rows_for(draft))
        assert InterventionMetadataField.objects.get(pk=d["number"].pk).key != d["number"].key

    def test_same_type_in_the_final_draft_keeps_the_key(self, definitions):
        """A type toggled in the editor and put back before Save is not a type change."""
        d = definitions
        apply(d["intervention"], rows_for(build_draft(d["intervention"])["fields"]))
        assert InterventionMetadataField.objects.get(pk=d["text"].pk).key == d["text"].key
        assert InterventionMetadataField.objects.get(pk=d["number"].pk).key == d["number"].key

    def test_changing_the_type_back_after_a_save_does_not_restore_values(self, definitions):
        d = definitions
        instance = instance_with(d, {d["text"].storage_key: "Amoud"})
        for field_type, number_type in (
            (MetadataFieldType.NUMBER, MetadataNumberType.INTEGER),
            (MetadataFieldType.FREE_TEXT, None),
        ):
            draft = build_draft(d["intervention"])["fields"]
            partner = next(f for f in draft if f["name"] == "Partner")
            partner["field_type"], partner["number_type"] = field_type, number_type
            apply(d["intervention"], rows_for(draft))
        field = InterventionMetadataField.objects.get(pk=d["text"].pk)
        assert field.field_type == MetadataFieldType.FREE_TEXT
        assert field.key != d["text"].key
        assert resolve_metadata(InterventionInstance.objects.get(pk=instance.pk)) == []

    def test_deleting_a_field_hides_its_values_without_touching_instances(self, definitions):
        d = definitions
        instance = instance_with(d, {d["text"].storage_key: "Amoud", d["number"].storage_key: "3"})
        draft = [f for f in build_draft(d["intervention"])["fields"] if f["name"] != "Partner"]
        apply(d["intervention"], rows_for(draft))
        assert not InterventionMetadataField.objects.filter(pk=d["text"].pk).exists()
        row = InterventionInstance.objects.get(pk=instance.pk)
        assert row.metadata == {d["text"].storage_key: "Amoud", d["number"].storage_key: "3"}
        assert [(r.name, r.display) for r in resolve_metadata(row)] == [("Volunteers", "3")]

    def test_deleting_an_option_removes_only_that_selection(self, definitions):
        d = definitions
        instance = instance_with(
            d,
            {
                d["multi"].storage_key: [d["X"].storage_key, d["Y"].storage_key],
                d["single"].storage_key: d["A"].storage_key,
            },
        )
        draft = build_draft(d["intervention"])["fields"]
        by_name = {f["name"]: f for f in draft}
        by_name["Approach"]["options"] = [o for o in by_name["Approach"]["options"] if o["label"] != "X"]
        by_name["Age"]["options"] = [o for o in by_name["Age"]["options"] if o["label"] != "A"]
        apply(d["intervention"], rows_for(draft))
        rows = resolve_metadata(InterventionInstance.objects.get(pk=instance.pk))
        assert [(r.name, r.display) for r in rows] == [("Approach", "Y")]
        assert not InterventionMetadataOption.objects.filter(pk__in=[d["X"].pk, d["A"].pk]).exists()

    def test_switching_to_a_non_choice_type_drops_the_options(self, definitions):
        d = definitions
        draft = build_draft(d["intervention"])["fields"]
        age = next(f for f in draft if f["name"] == "Age")
        age["field_type"], age["options"] = MetadataFieldType.FREE_TEXT, []
        apply(d["intervention"], rows_for(draft))
        assert InterventionMetadataField.objects.get(pk=d["single"].pk).options.count() == 0

    def test_adding_a_definition_leaves_existing_instances_blank(self, definitions):
        d = definitions
        instance = instance_with(d, {d["text"].storage_key: "Amoud"})
        draft = build_draft(d["intervention"])["fields"] + [text_row("Funder")]
        apply(d["intervention"], rows_for(draft))
        row = InterventionInstance.objects.get(pk=instance.pk)
        assert row.metadata == {d["text"].storage_key: "Amoud"}
        assert [r.name for r in resolve_metadata(row)] == ["Partner"]

    def test_a_field_deleted_after_validation_is_a_conflict_that_writes_nothing(self, definitions):
        d = definitions
        draft = build_draft(d["intervention"])["fields"]
        next(f for f in draft if f["name"] == "Partner")["name"] = "Implementation Partner"
        rows = validate_draft(d["intervention"], {"fields": rows_for(draft)})
        d["number"].delete()  # another editor, between validation and persistence

        with pytest.raises(MetadataDraftError):
            save_draft(d["intervention"], rows)

        # Rolled back: the rename that preceded the missing row is gone too.
        names = list(d["intervention"].metadata_fields.values_list("name", flat=True))
        assert names == ["Partner", "Age", "Approach"]

    def test_an_option_deleted_after_validation_is_a_conflict_that_writes_nothing(self, definitions):
        d = definitions
        draft = build_draft(d["intervention"])["fields"]
        next(f for f in draft if f["name"] == "Partner")["name"] = "Implementation Partner"
        rows = validate_draft(d["intervention"], {"fields": rows_for(draft)})
        d["Z"].delete()  # another editor, between validation and persistence

        with pytest.raises(MetadataDraftError):
            save_draft(d["intervention"], rows)

        names = list(d["intervention"].metadata_fields.values_list("name", flat=True))
        assert names == ["Partner", "Age", "Approach", "Volunteers"]
        assert [o.label for o in d["multi"].options.all()] == ["X", "Y"]


class TestExcelNumbers:
    """A spreadsheet cell holds a stored number only when it can do so exactly."""

    @pytest.mark.parametrize(
        ("value", "digits"),
        [
            ("0", 1),
            ("-0", 1),
            ("100", 1),
            ("0.0005", 1),
            ("1.50", 2),
            ("1000.001", 7),
            ("-123456789012345", 15),
        ],
    )
    def test_significant_digits_ignore_outer_zeros(self, value, digits):
        assert significant_digits(value) == digits

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("0", 0.0),
            ("42", 42.0),
            ("-1234567890.12345", -1234567890.12345),  # 15 significant digits
            ("123456789012345", 123456789012345.0),  # 15 significant digits
            ("0.000000000000001", 1e-15),
            ("-10000000000000000000", -1e19),  # 20 digits as entered, one significant
            ("1234567890123456", None),  # 16 significant digits
            ("-1234567890.123456", None),
            ("12345678901234567890", None),  # the accepted 20-digit maximum
            ("1" + "0" * 400, None),  # not finite as a float
            ("abc", None),
        ],
    )
    def test_excel_number(self, value, expected):
        assert excel_number(value) == expected

    @pytest.mark.parametrize(
        ("value", "number_type", "symbol", "number_format"),
        [
            ("42", MetadataNumberType.INTEGER, "$", "#,##0"),
            ("-1234567", MetadataNumberType.INTEGER, None, "#,##0"),
            ("1000", MetadataNumberType.DECIMAL, None, "#,##0"),
            ("0.25", MetadataNumberType.DECIMAL, "$", "#,##0.00"),
            ("12.50", MetadataNumberType.DECIMAL, None, "#,##0.00"),
            ("125", MetadataNumberType.PERCENTAGE, None, '#,##0"%"'),
            ("12.5", MetadataNumberType.PERCENTAGE, "$", '#,##0.0"%"'),
            ("0.001", MetadataNumberType.CURRENCY, "\u20ac", '"\u20ac"#,##0.000'),
            ("1000.50", MetadataNumberType.CURRENCY, "$", '"$"#,##0.00'),
            ("7", MetadataNumberType.CURRENCY, None, "#,##0"),
        ],
    )
    def test_excel_number_format_keeps_the_entered_places_like_insights(
        self, value, number_type, symbol, number_format
    ):
        assert excel_number_format(value, number_type, symbol) == number_format


@pytest.mark.django_db
class TestMetadataLookup:
    def test_rows_for_every_instance_of_an_analysis_with_bounded_queries(
        self, definitions, django_assert_num_queries
    ):
        analysis = AnalysisFactory()
        text = definitions["text"]
        first = InterventionInstanceFactory(
            analysis=analysis, intervention=definitions["intervention"], metadata={text.storage_key: "One"}
        )
        second = InterventionInstanceFactory(
            analysis=analysis,
            intervention=definitions["intervention"],
            metadata={
                text.storage_key: "Two",
                definitions["multi"].storage_key: [definitions["Z"].storage_key],
            },
        )
        third = InterventionInstanceFactory(analysis=analysis, intervention=InterventionFactory())
        stored = Analysis.objects.get(pk=analysis.pk)

        # Instances, their interventions, the fields and the options: four queries however many
        # instances there are, and repeated interventions do not add any.
        with django_assert_num_queries(4):
            lookup = metadata_lookup(stored)

        assert set(lookup) == {first.id, second.id, third.id}
        assert [(row.name, row.display) for row in lookup[first.id]] == [("Partner", "One")]
        assert [(row.name, row.display) for row in lookup[second.id]] == [
            ("Partner", "Two"),
            ("Approach", "Z"),
        ]
        assert lookup[third.id] == []
