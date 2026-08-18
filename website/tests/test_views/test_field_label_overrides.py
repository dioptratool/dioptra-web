import pytest
from django.urls import reverse

from website.models import FieldLabelOverrides
from website.models.utils import load_field_label_override

CUSTOM_FIELD_NAMES = [f"ci_dummy_field_{n}" for n in range(1, 6)] + [
    f"tr_dummy_field_{n}" for n in range(1, 6)
]


def _post_data(**overrides):
    """Every field on the singleton, so the ModelForm sees a complete submission."""
    data = {}
    for field in FieldLabelOverrides._meta.fields:
        if field.primary_key:
            continue
        if field.name.endswith("_overridden"):
            continue
        data[field.name] = ""
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestCustomFieldLabelOverrides:
    def test_model_exposes_a_label_pair_for_every_custom_field(self):
        overrides = FieldLabelOverrides.get()
        for field_name in CUSTOM_FIELD_NAMES:
            assert hasattr(overrides, field_name)
            assert hasattr(overrides, f"{field_name}_overridden")

    def test_default_label_is_used_when_not_overridden(self):
        FieldLabelOverrides.get()
        assert (
            load_field_label_override("ci_dummy_field_1", "Budget Custom Field 1") == "Budget Custom Field 1"
        )
        assert (
            load_field_label_override("tr_dummy_field_3", "Transaction Custom Field 3")
            == "Transaction Custom Field 3"
        )

    def test_saved_override_replaces_the_default_label(self):
        overrides = FieldLabelOverrides.get()
        overrides.ci_dummy_field_1 = "Cost Centre"
        overrides.ci_dummy_field_1_overridden = True
        overrides.tr_dummy_field_1 = "Project Code"
        overrides.tr_dummy_field_1_overridden = True
        overrides.save()

        assert load_field_label_override("ci_dummy_field_1", "Budget Custom Field 1") == "Cost Centre"
        assert load_field_label_override("tr_dummy_field_1", "Transaction Custom Field 1") == "Project Code"
        # Untouched custom fields still fall back to their defaults.
        assert (
            load_field_label_override("ci_dummy_field_2", "Budget Custom Field 2") == "Budget Custom Field 2"
        )

    def test_label_is_ignored_when_override_is_not_enabled(self):
        overrides = FieldLabelOverrides.get()
        overrides.ci_dummy_field_2 = "Donor"
        overrides.ci_dummy_field_2_overridden = False
        overrides.save()

        assert (
            load_field_label_override("ci_dummy_field_2", "Budget Custom Field 2") == "Budget Custom Field 2"
        )

    def test_panel_renders_both_custom_field_tabs(self, client_with_admin):
        overrides = FieldLabelOverrides.get()
        url = reverse("ombucore.admin:website_fieldlabeloverrides_change", args=[overrides.pk])

        response = client_with_admin.get(url)
        content = response.content.decode()

        assert response.status_code == 200
        assert "Budget Custom Fields" in content
        assert "Transaction Custom Fields" in content
        for field_name in CUSTOM_FIELD_NAMES:
            assert f'name="{field_name}"' in content
            assert f'name="{field_name}_overridden"' in content

    def test_panel_saves_a_custom_field_override(self, client_with_admin):
        overrides = FieldLabelOverrides.get()
        url = reverse("ombucore.admin:website_fieldlabeloverrides_change", args=[overrides.pk])

        response = client_with_admin.post(
            url,
            data=_post_data(
                ci_dummy_field_1="Cost Centre",
                ci_dummy_field_1_overridden="on",
            ),
        )

        assert response.status_code == 200
        overrides.refresh_from_db()
        assert overrides.ci_dummy_field_1 == "Cost Centre"
        assert overrides.ci_dummy_field_1_overridden is True
        assert load_field_label_override("ci_dummy_field_1", "Budget Custom Field 1") == "Cost Centre"

    def test_panel_rejects_an_enabled_override_with_no_label(self, client_with_admin):
        overrides = FieldLabelOverrides.get()
        url = reverse("ombucore.admin:website_fieldlabeloverrides_change", args=[overrides.pk])

        response = client_with_admin.post(
            url,
            data=_post_data(ci_dummy_field_1="", ci_dummy_field_1_overridden="on"),
        )

        assert response.status_code == 200
        assert response.context["form"].errors["ci_dummy_field_1"] == ["This field is required."]
        overrides.refresh_from_db()
        assert overrides.ci_dummy_field_1_overridden is False
