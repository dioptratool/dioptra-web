import json

import pytest
from django.urls import reverse

from website.tests.factories import CostLineItemFactory


@pytest.mark.django_db
def test_cost_line_item_add_note_sets_analysis_before_permission_check(client_with_admin):
    cost_line_item = CostLineItemFactory(note="")
    url = reverse("api--costlineitem--add-note", kwargs={"pk": cost_line_item.pk})

    response = client_with_admin.post(
        url,
        data=json.dumps({"note": "Reviewed"}),
        content_type="application/json",
    )

    cost_line_item.refresh_from_db()
    assert response.status_code == 200
    assert response.json() == {"id": cost_line_item.id, "note": "Reviewed"}
    assert cost_line_item.note == "Reviewed"
