from decimal import Decimal

import pytest
from django.conf import settings as django_settings
from django.urls import reverse

from website.models import Analysis
from website.tests.factories import InterventionFactory
from website.tests.factories import SubcomponentCostAnalysisFactory
from website.workflows import AnalysisWorkflow
from website.tests.factories import SubcomponentCostAnalysisFactory
from website.workflows import AnalysisWorkflow
from website.tests.factories import InterventionFactory


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

    def test_all_good_data_with_maximum_interventions(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        a_user,
        client_with_admin,
    ):
        analysis_wf = analysis_workflow_with_confirmed_categories_cost_line_item
        analysis = analysis_wf.analysis

        while analysis.interventioninstance_set.count() < django_settings.MAX_ANALYSIS_INTERVENTIONS:
            analysis.add_intervention(
                InterventionFactory(
                    output_metrics=[
                        "NumberOfTeacherDaysOfTraining",
                    ],
                ),
                parameters={
                    "number_of_teachers": 1,
                    "number_of_days_of_training": 1,
                },
            )
        analysis.ensure_cost_type_category_objects()

        data = {}
        for cli in analysis.cost_line_items.all():
            for intervention_instance in analysis.interventioninstance_set.all():
                data[f"cost_line_item_allocation_{cli.id}_{intervention_instance.id}"] = "2.00"

        cost_type_category_grant = analysis.cost_type_category_grants.first()
        grant = cost_type_category_grant.grant
        cost_type = cost_type_category_grant.cost_type_category.cost_type

        response = client_with_admin.post(
            reverse(
                "analysis-allocate-cost_type-grant",
                kwargs={
                    "pk": analysis.pk,
                    "cost_type_pk": cost_type.pk,
                    "grant": grant,
                },
            ),
            data=data,
            follow=True,
        )

        assert response.status_code == 200

        updated_analysis = Analysis.objects.get(pk=analysis.pk)
        for cli in updated_analysis.cost_line_items.all():
            allocations = cli.config.allocations.all()
            assert allocations.count() == django_settings.MAX_ANALYSIS_INTERVENTIONS
            for allocation in allocations:
                assert allocation.allocation == Decimal("2.00")
