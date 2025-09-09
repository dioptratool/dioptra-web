from decimal import Decimal

import pytest
from django.urls import reverse

from website.models import Analysis


@pytest.mark.django_db
class TestAllocateCostFormSubmissions:
    def test_all_good_data(
        self,
        analysis_workflow_with_loaddata_complete,
        a_user,
        client_with_admin,
    ):
        analysis_wf = analysis_workflow_with_loaddata_complete
        data = {}
        for cli in analysis_wf.analysis.cost_line_items.all():
            for intervention_instance in analysis_wf.analysis.interventioninstance_set.all():
                data[f"cost_line_item_allocation_{cli.id}_{intervention_instance.id}"] = "2.00"

        cost_type_category_grant = analysis_wf.analysis.cost_type_category_grants.first()
        grant = cost_type_category_grant.grant
        category = cost_type_category_grant.cost_type_category.category
        cost_type = cost_type_category_grant.cost_type_category.cost_type

        response = client_with_admin.post(
            reverse(
                "analysis-allocate-cost_type-grant",
                kwargs={
                    "pk": analysis_wf.analysis.pk,
                    "cost_type_pk": cost_type.pk,
                    "grant": grant,
                },
            ),
            data=data,
            follow=True,
        )

        assert response.status_code == 200

        updated_analysis = Analysis.objects.get(pk=analysis_wf.analysis.pk)
        for cli in updated_analysis.cost_line_items.all():
            for allocation in cli.config.allocations.all():
                assert allocation.allocation == Decimal("2.00")
