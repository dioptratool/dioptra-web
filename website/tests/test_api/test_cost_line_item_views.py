import json

import pytest
from django.urls import reverse

from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestCostLineItemAddNoteView:
    def test_add_note_success(self, defaults, client_with_admin):
        analysis = AnalysisFactory()
        cli = CostLineItemFactory(analysis=analysis)
        CostLineItemConfigFactory(cost_line_item=cli)

        url = reverse("api--costlineitem--add-note", kwargs={"pk": cli.pk})
        response = client_with_admin.post(
            url,
            data=json.dumps({"note": "test note"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cli.pk
        assert data["note"] == "test note"

    def test_add_note_unauthenticated(self, defaults, client):
        analysis = AnalysisFactory()
        cli = CostLineItemFactory(analysis=analysis)
        CostLineItemConfigFactory(cost_line_item=cli)

        url = reverse("api--costlineitem--add-note", kwargs={"pk": cli.pk})
        response = client.post(
            url,
            data=json.dumps({"note": "test note"}),
            content_type="application/json",
        )

        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    def test_add_note_unauthorized_user(self, defaults, client):
        analysis = AnalysisFactory()
        cli = CostLineItemFactory(analysis=analysis)
        CostLineItemConfigFactory(cost_line_item=cli)
        user = UserFactory()
        client.force_login(user)

        url = reverse("api--costlineitem--add-note", kwargs={"pk": cli.pk})
        response = client.post(
            url,
            data=json.dumps({"note": "test note"}),
            content_type="application/json",
        )

        assert response.status_code == 403

    def test_add_note_nonexistent_cli(self, defaults, client_with_admin):
        url = reverse("api--costlineitem--add-note", kwargs={"pk": 999999})
        response = client_with_admin.post(
            url,
            data=json.dumps({"note": "test note"}),
            content_type="application/json",
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestCostLineItemUpdateCostTypeCategoryView:
    def test_update_cost_type_category_success(self, defaults, client_with_admin):
        analysis = AnalysisFactory()
        cli = CostLineItemFactory(analysis=analysis)
        config = CostLineItemConfigFactory(cost_line_item=cli)

        url = reverse("api--costlineitem--edit-cost_type-category", kwargs={"pk": cli.pk})
        response = client_with_admin.post(
            url,
            data=json.dumps(
                {
                    "cost_type_id": config.cost_type_id,
                    "category_id": config.category_id,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cli.pk
        assert data["cost_type_id"] == config.cost_type_id
        assert data["category_id"] == config.category_id

    def test_update_cost_type_category_unauthenticated(self, defaults, client):
        analysis = AnalysisFactory()
        cli = CostLineItemFactory(analysis=analysis)
        CostLineItemConfigFactory(cost_line_item=cli)

        url = reverse("api--costlineitem--edit-cost_type-category", kwargs={"pk": cli.pk})
        response = client.post(
            url,
            data=json.dumps({"cost_type_id": 1, "category_id": 1}),
            content_type="application/json",
        )

        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    def test_update_cost_type_category_unauthorized_user(self, defaults, client):
        analysis = AnalysisFactory()
        cli = CostLineItemFactory(analysis=analysis)
        CostLineItemConfigFactory(cost_line_item=cli)
        user = UserFactory()
        client.force_login(user)

        url = reverse("api--costlineitem--edit-cost_type-category", kwargs={"pk": cli.pk})
        response = client.post(
            url,
            data=json.dumps({"cost_type_id": 1, "category_id": 1}),
            content_type="application/json",
        )

        assert response.status_code == 403

    def test_update_cost_type_category_nonexistent_cli(self, defaults, client_with_admin):
        url = reverse("api--costlineitem--edit-cost_type-category", kwargs={"pk": 999999})
        response = client_with_admin.post(
            url,
            data=json.dumps({"cost_type_id": 1, "category_id": 1}),
            content_type="application/json",
        )

        assert response.status_code == 404
