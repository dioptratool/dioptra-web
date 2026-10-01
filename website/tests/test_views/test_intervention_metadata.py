"""Feature 95: the Metadata tab's child panels and the parent intervention save."""

import json
import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from website.forms.intervention_metadata import metadata_field_name as name_of
from website.intervention_metadata import build_draft
from website.workflows.utils import WORKFLOW_PREFETCHES, recalculate_analysis
from website.models import (
    Analysis,
    AnalysisStatus,
    Intervention,
    InterventionInstance,
    InterventionMetadataField,
    InterventionMetadataOption,
    MetadataFieldType,
    MetadataNumberType,
)
from website.models.output_metric import OUTPUT_METRIC_CHOICES
from website.tests.factories import (
    AnalysisFactory,
    InterventionFactory,
    InterventionInstanceFactory,
    InterventionMetadataFieldFactory,
    InterventionMetadataOptionFactory,
    UserFactory,
)

User = get_user_model()

ONE_WORKFLOW_VARIANT = pytest.mark.parametrize(
    "analysis_workflow_with_loaddata_complete", ["analysis_workflow_with_analysis"], indirect=True
)

PAYLOAD = re.compile(
    r'<script id="panel-command-payload-[0-9a-f]+" type="application/json">(.*?)</script>', re.S
)


def draft_url(mode, intervention=None):
    url = reverse("intervention-metadata-draft", kwargs={"mode": mode})
    return f"{url}?intervention={intervention.pk}" if intervention else url


def payload_of(response):
    match = PAYLOAD.search(response.content.decode())
    return json.loads(match.group(1)) if match else None


def text_row(name, **extra):
    return {"name": name, "field_type": MetadataFieldType.FREE_TEXT, **extra}


def choice_row(name, labels, field_type=MetadataFieldType.MULTIPLE_CHOICE, **extra):
    return {
        "name": name,
        "field_type": field_type,
        "options": [{"label": label} for label in labels],
        **extra,
    }


def number_row(name, number_type=MetadataNumberType.INTEGER, **extra):
    return {"name": name, "field_type": MetadataFieldType.NUMBER, "number_type": number_type, **extra}


def add_url():
    return reverse("ombucore.admin:website_intervention_add")


def change_url(intervention):
    return reverse("ombucore.admin:website_intervention_change", kwargs={"pk": intervention.pk})


def change_data(client, intervention, draft):
    """The change form's own initial values, as the browser would post them, with a new draft."""
    initial = client.get(change_url(intervention)).context["form"].initial
    data = {
        key: value
        for key, value in initial.items()
        if value is not None and not isinstance(value, (dict, list))
    }
    data["subcomponent_labels"] = json.dumps(initial.get("subcomponent_labels") or [])
    data["metadata_draft"] = json.dumps(draft)
    return data


@pytest.mark.django_db
class TestDraftPanelAccess:
    def test_admin_gets_the_field_panel_shell(self, client_with_admin):
        response = client_with_admin.get(draft_url("field"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "data-metadata-field-form" in content
        assert 'data-bound="false"' in content
        assert 'name="name"' in content and 'name="field_type"' in content and 'name="options"' in content
        assert "intervention-metadata-editor.js" in content

    def test_option_label_panel_shell(self, client_with_admin):
        response = client_with_admin.get(draft_url("option_label", InterventionFactory()))
        assert response.status_code == 200
        assert 'name="label"' in response.content.decode()

    def test_unknown_mode_is_not_found(self, client_with_admin):
        assert (
            client_with_admin.get(reverse("intervention-metadata-draft", kwargs={"mode": "nope"})).status_code
            == 404
        )

    def test_basic_users_are_forbidden_on_get_and_post(self, client):
        client.force_login(UserFactory())
        intervention = InterventionFactory()
        for url in (draft_url("field"), draft_url("field", intervention), draft_url("option_label")):
            assert client.get(url).status_code == 403
            assert client.post(url, data={"name": "x", "field_type": "free_text"}).status_code == 403

    def test_anonymous_is_sent_to_log_in(self, client):
        response = client.get(draft_url("field"))
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")


@pytest.mark.django_db
class TestFieldPanelPost:
    def test_valid_post_returns_the_normalized_row_and_writes_nothing(self, client_with_admin):
        response = client_with_admin.post(
            draft_url("field"),
            data={
                "draft_id": "f1",
                "name": "  Treatment Approach ",
                "field_type": MetadataFieldType.MULTIPLE_CHOICE,
                "options": json.dumps(
                    [
                        {"label": " Community-based "},
                        {"label": "Outpatient", "draft_id": "o2", "in_use": True},
                    ]
                ),
            },
        )

        assert response.status_code == 200
        row = payload_of(response)["row"]
        assert row["name"] == "Treatment Approach"
        assert row["draft_id"] == "f1"
        assert row["id"] is None and row["key"] is None
        assert [(o["label"], o["draft_id"], o["in_use"]) for o in row["options"]] == [
            ("Community-based", row["options"][0]["draft_id"], False),
            ("Outpatient", "o2", True),
        ]
        assert InterventionMetadataField.objects.count() == 0
        assert InterventionMetadataOption.objects.count() == 0

    def test_invalid_post_rerenders_the_posted_state_with_errors(self, client_with_admin):
        response = client_with_admin.post(
            draft_url("field"), data={"name": "", "field_type": MetadataFieldType.NUMBER, "options": "[]"}
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert 'data-bound="true"' in content
        assert "This field is required." in content
        assert "Choose a number type." in content
        assert payload_of(response) is None

    def test_choice_fields_need_an_option(self, client_with_admin):
        response = client_with_admin.post(
            draft_url("field"),
            data={"name": "C", "field_type": MetadataFieldType.SINGLE_CHOICE, "options": "[]"},
        )
        assert "Add at least one option." in response.content.decode()
        assert payload_of(response) is None

    def test_full_length_non_ascii_names_and_labels_travel_in_the_post_body(self, client_with_admin):
        name = "中" * 100
        labels = [f"é{n}" + "ü" * 97 for n in range(10)]
        response = client_with_admin.post(
            draft_url("field"),
            data={
                "name": name,
                "field_type": MetadataFieldType.SINGLE_CHOICE,
                "options": json.dumps([{"label": l} for l in labels]),
            },
        )
        row = payload_of(response)["row"]
        assert row["name"] == name
        assert [o["label"] for o in row["options"]] == labels

    def test_option_label_post(self, client_with_admin):
        response = client_with_admin.post(draft_url("option_label"), data={"label": "  Inpatient "})
        assert payload_of(response) == {"label": "Inpatient"}
        response = client_with_admin.post(draft_url("option_label"), data={"label": ""})
        assert payload_of(response) is None
        assert "This field is required." in response.content.decode()


@pytest.mark.django_db
class TestParentSave:
    def test_a_new_intervention_saves_together_with_its_definitions(self, client_with_admin):
        draft = {
            "fields": [
                text_row("Implementation Partner"),
                choice_row("Treatment Approach", ["Community-based", "Outpatient"]),
                choice_row("Target Age Group", ["0-5 months"], MetadataFieldType.SINGLE_CHOICE),
                number_row("Community Volunteers"),
            ]
        }

        response = client_with_admin.post(
            add_url(),
            data={
                "name": "Malnutrition Treatment",
                "icon": "cash",
                "output_metric_1": OUTPUT_METRIC_CHOICES[0][0],
                "show_in_menu": "on",
                "subcomponent_labels": "[]",
                "metadata_draft": json.dumps(draft),
            },
        )

        assert response.status_code == 200
        assert '"operation": "saved"' in response.content.decode()
        intervention = Intervention.objects.get(name="Malnutrition Treatment")
        fields = list(intervention.metadata_fields.all())
        assert [(f.name, f.field_type, f.number_type) for f in fields] == [
            ("Implementation Partner", MetadataFieldType.FREE_TEXT, None),
            ("Treatment Approach", MetadataFieldType.MULTIPLE_CHOICE, None),
            ("Target Age Group", MetadataFieldType.SINGLE_CHOICE, None),
            ("Community Volunteers", MetadataFieldType.NUMBER, MetadataNumberType.INTEGER),
        ]
        assert [o.label for o in fields[1].options.all()] == ["Community-based", "Outpatient"]
        assert all(f.key for f in fields)

    def test_the_metadata_tab_is_rendered_with_the_current_draft(self, client_with_admin):
        intervention = InterventionFactory(output_metrics=[OUTPUT_METRIC_CHOICES[0][0]])
        InterventionMetadataFieldFactory(intervention=intervention, name="Partner")
        content = client_with_admin.get(change_url(intervention)).content.decode()
        assert 'data-tab="metadata"' in content
        assert "data-metadata-editor" in content
        assert "Partner" in content
        assert f"intervention={intervention.pk}" in content

    def test_draft_edits_commit_together_on_change(self, client_with_admin):
        intervention = InterventionFactory(output_metrics=[OUTPUT_METRIC_CHOICES[0][0]])
        partner = InterventionMetadataFieldFactory(intervention=intervention, name="Partner", order=0)
        approach = InterventionMetadataFieldFactory(
            intervention=intervention, name="Approach", field_type=MetadataFieldType.MULTIPLE_CHOICE, order=1
        )
        community = InterventionMetadataOptionFactory(field=approach, label="Community", order=0)
        gone = InterventionMetadataFieldFactory(intervention=intervention, name="Gone", order=2)
        instance = InterventionInstanceFactory(
            intervention=intervention, metadata={partner.storage_key: "Amoud"}
        )

        draft = build_draft(intervention)
        by_name = {f["name"]: f for f in draft["fields"]}
        by_name["Partner"]["name"] = "Implementation Partner"
        by_name["Approach"]["options"][0]["label"] = "Community-based"
        by_name["Approach"]["options"].append({"label": "Inpatient"})
        draft["fields"] = [by_name["Approach"], by_name["Partner"], number_row("Volunteers")]

        response = client_with_admin.post(
            change_url(intervention), data=change_data(client_with_admin, intervention, draft)
        )

        assert response.status_code == 200
        assert '"operation": "saved"' in response.content.decode()
        fields = list(intervention.metadata_fields.all())
        assert [f.name for f in fields] == ["Approach", "Implementation Partner", "Volunteers"]
        assert InterventionMetadataField.objects.get(pk=partner.pk).key == partner.key
        assert not InterventionMetadataField.objects.filter(pk=gone.pk).exists()
        assert [(o.label, o.key == community.key) for o in fields[0].options.all()] == [
            ("Community-based", True),
            ("Inpatient", False),
        ]
        instance.refresh_from_db()
        assert instance.metadata == {partner.storage_key: "Amoud"}

    def test_an_invalid_draft_fails_the_save_and_keeps_the_draft(self, client_with_admin):
        intervention = InterventionFactory(output_metrics=[OUTPUT_METRIC_CHOICES[0][0]], name="Before")
        InterventionMetadataFieldFactory(intervention=intervention, name="Partner")
        draft = {"fields": [text_row("Funder"), text_row("funder ")]}
        data = change_data(client_with_admin, intervention, draft)
        data["name"] = "After"

        response = client_with_admin.post(change_url(intervention), data=data)

        assert response.status_code == 200
        content = response.content.decode()
        assert "field names must be unique" in content
        assert '"operation": "saved"' not in content
        assert "Funder" in content  # the draft is rendered again, not the stored definitions
        intervention.refresh_from_db()
        assert intervention.name == "Before"
        assert [f.name for f in intervention.metadata_fields.all()] == ["Partner"]

    def test_a_type_change_through_the_parent_rotates_the_key(self, client_with_admin):
        intervention = InterventionFactory(output_metrics=[OUTPUT_METRIC_CHOICES[0][0]])
        field = InterventionMetadataFieldFactory(intervention=intervention, name="Count")
        draft = build_draft(intervention)
        draft["fields"][0].update(
            {"field_type": MetadataFieldType.NUMBER, "number_type": MetadataNumberType.DECIMAL}
        )

        client_with_admin.post(
            change_url(intervention), data=change_data(client_with_admin, intervention, draft)
        )

        stored = InterventionMetadataField.objects.get(pk=field.pk)
        assert stored.field_type == MetadataFieldType.NUMBER
        assert stored.key != field.key

    def test_basic_users_cannot_open_the_intervention_editor(self, client):
        client.force_login(UserFactory())
        assert client.get(change_url(InterventionFactory())).status_code == 403


# ---------------------------------------------------------------------------------------------
# Values in the intervention instance panel
# ---------------------------------------------------------------------------------------------


def instance_change_url(instance):
    return reverse("ombucore.admin:website_interventioninstance_change", args=[instance.pk])


PARAMETERS = {"parameter__number_of_teachers": "1", "parameter__number_of_days_of_training": "1"}


@pytest.fixture
def admin():
    return UserFactory(role=User.ADMIN)


@pytest.fixture
def admin_client(client, admin):
    client.force_login(admin)
    return client


@pytest.fixture
def panel_setup(defaults):
    intervention = InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"])
    text = InterventionMetadataFieldFactory(intervention=intervention, name="Partner", order=0)
    number = InterventionMetadataFieldFactory(
        intervention=intervention,
        name="Volunteers",
        field_type=MetadataFieldType.NUMBER,
        number_type=MetadataNumberType.INTEGER,
        order=1,
    )
    other = InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"])
    budget = InterventionMetadataFieldFactory(
        intervention=other,
        name="Budget",
        field_type=MetadataFieldType.NUMBER,
        number_type=MetadataNumberType.DECIMAL,
    )
    analysis = AnalysisFactory()
    instance = InterventionInstanceFactory(
        analysis=analysis,
        intervention=intervention,
        parameters={"number_of_teachers": 1.0, "number_of_days_of_training": 1.0},
        metadata={text.storage_key: "Amoud", number.storage_key: "172"},
    )
    return {
        "intervention": intervention,
        "text": text,
        "number": number,
        "other": other,
        "budget": budget,
        "analysis": analysis,
        "instance": instance,
    }


@pytest.mark.django_db
class TestInstancePanelValues:
    def test_change_panel_renders_every_interventions_controls_and_the_warning(
        self, admin_client, panel_setup
    ):
        s = panel_setup
        content = admin_client.get(instance_change_url(s["instance"])).content.decode()

        assert "data-metadata-section" in content
        assert f'name="{name_of(s["text"])}"' in content and 'value="Amoud"' in content
        assert f'name="{name_of(s["number"])}"' in content and 'value="172"' in content
        assert f'name="{name_of(s["budget"])}"' in content
        assert re.search(rf'name="{name_of(s["budget"])}"[^>]*disabled', content)
        assert (
            str(s["intervention"].pk) in content
            and f'&quot;{s["other"].pk}&quot;' in content
            or "data-metadata-mapping" in content
        )
        assert "sub-component data and metadata" in content  # metadata alone is dependent data

    def test_a_validation_error_keeps_active_values_and_every_control(self, admin_client, panel_setup):
        s = panel_setup
        response = admin_client.post(
            instance_change_url(s["instance"]),
            data={
                "intervention": str(s["intervention"].pk),
                **PARAMETERS,
                name_of(s["text"]): "Changed",
                name_of(s["number"]): "1.5",
            },
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Enter a whole number." in content
        assert 'value="Changed"' in content
        assert f'name="{name_of(s["budget"])}"' in content
        assert "data-metadata-mapping" in content
        assert '"operation": "saved"' not in content
        assert InterventionInstance.objects.get(pk=s["instance"].pk).metadata == {
            s["text"].storage_key: "Amoud",
            s["number"].storage_key: "172",
        }

    def test_switching_the_intervention_saves_only_its_metadata_even_with_invalid_inactive_values(
        self, admin_client, panel_setup
    ):
        s = panel_setup
        response = admin_client.post(
            instance_change_url(s["instance"]),
            data={
                "intervention": str(s["other"].pk),
                **PARAMETERS,
                name_of(s["budget"]): "99.99",
                name_of(s["number"]): "not a number",
            },
        )

        assert '"operation": "saved"' in response.content.decode()
        row = InterventionInstance.objects.get(pk=s["instance"].pk)
        assert row.intervention == s["other"]
        assert row.metadata == {s["budget"].storage_key: "99.99"}

    def test_basic_owner_cannot_edit_an_instance_of_a_validated_analysis_but_an_admin_can(
        self, admin_client, panel_setup
    ):
        s = panel_setup
        Analysis.objects.filter(pk=s["analysis"].pk).update(analysis_status=AnalysisStatus.VALIDATED)
        owner_client = Client()
        owner_client.force_login(s["analysis"].owner)
        assert owner_client.get(instance_change_url(s["instance"])).status_code == 403
        assert admin_client.get(instance_change_url(s["instance"])).status_code == 200

    def test_a_primary_country_editor_can_enter_values(self, client, panel_setup):
        s = panel_setup
        editor = UserFactory()
        editor.primary_countries.add(s["analysis"].country)
        client.force_login(editor)
        response = client.post(
            instance_change_url(s["instance"]),
            data={"intervention": str(s["intervention"].pk), **PARAMETERS, name_of(s["text"]): "Edited"},
        )
        assert '"operation": "saved"' in response.content.decode()
        assert InterventionInstance.objects.get(pk=s["instance"].pk).metadata == {
            s["text"].storage_key: "Edited"
        }


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestMetadataOnlyEditsOnACompleteWorkflow:
    def test_lifecycle_fields_are_kept_while_updated_advances(
        self, analysis_workflow_main_flow_complete, admin, admin_client
    ):
        analysis = analysis_workflow_main_flow_complete.analysis
        actor = UserFactory()
        Analysis.objects.filter(pk=analysis.pk).update(
            analysis_status=AnalysisStatus.VALIDATED, status_changed_by=actor
        )
        instance = analysis.interventioninstance_set.first()
        text = InterventionMetadataFieldFactory(intervention=instance.intervention, name="Partner")
        # The fixture's stored outputs predate its last data changes; start from current outputs.
        recalculate_analysis(Analysis.objects.prefetch_related(*WORKFLOW_PREFETCHES).get(pk=analysis.pk))
        before = Analysis.objects.get(pk=analysis.pk)

        response = admin_client.post(
            instance_change_url(instance),
            data={"intervention": str(instance.intervention.pk), **PARAMETERS, name_of(text): "Amoud"},
        )

        assert '"operation": "saved"' in response.content.decode()
        assert InterventionInstance.objects.get(pk=instance.pk).metadata == {text.storage_key: "Amoud"}
        after = Analysis.objects.get(pk=analysis.pk)
        assert after.analysis_status == AnalysisStatus.VALIDATED
        assert after.status_changed_by == actor
        assert after.status_changed_at == before.status_changed_at
        assert after.output_costs == before.output_costs
        assert after.updated > before.updated
