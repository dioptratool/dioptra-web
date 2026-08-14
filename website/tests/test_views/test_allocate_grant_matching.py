"""
Regression tests for allocate sub-step resolution and suggested allocations
against production data shapes: grant codes containing URL sub-delimiters
(e.g. commas) and AnalysisCostTypeCategory rows with a null cost_type.
"""

import pytest
from django.urls import reverse

from website.models import (
    AnalysisCostTypeCategory,
    AnalysisCostTypeCategoryGrant,
)

COMMA_GRANT = "If needed, we can even us this as a helper column"


@pytest.mark.django_db
class TestAllocateCostTypeGrantStepMatching:
    def test_grant_with_comma_loads(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        """
        reverse() leaves sub-delimiters like "," unescaped in hrefs, which broke
        the previous quoted-path comparison and 500ed with
        "'NoneType' object has no attribute 'cost_type'".
        """
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        analysis.unfiltered_cost_line_items.update(grant_code=COMMA_GRANT)
        AnalysisCostTypeCategoryGrant.objects.filter(
            cost_type_category__analysis=analysis,
        ).update(grant=COMMA_GRANT)

        cost_type_category_grant = analysis.cost_type_category_grants.first()
        response = client_with_admin.get(
            reverse(
                "analysis-allocate-cost_type-grant",
                kwargs={
                    "pk": analysis.pk,
                    "cost_type_pk": cost_type_category_grant.cost_type_category.cost_type.pk,
                    "grant": COMMA_GRANT,
                },
            )
        )

        assert response.status_code == 200

    def test_unknown_grant_redirects_to_analysis(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        cost_type_category_grant = analysis.cost_type_category_grants.first()

        response = client_with_admin.get(
            reverse(
                "analysis-allocate-cost_type-grant",
                kwargs={
                    "pk": analysis.pk,
                    "cost_type_pk": cost_type_category_grant.cost_type_category.cost_type.pk,
                    "grant": "NO-SUCH-GRANT",
                },
            )
        )

        assert response.status_code == 302
        assert response.url == reverse("analysis", kwargs={"pk": analysis.pk})


@pytest.mark.django_db
class TestSuggestedAllocationsNullCostType:
    def test_null_cost_type_category_is_skipped(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
    ):
        """
        Production data contains AnalysisCostTypeCategory rows with
        cost_type=NULL (the workflow already skips them when building allocate
        sub-steps); get_suggested_allocations must skip them too instead of
        raising "'NoneType' object has no attribute 'type_obj'".
        """
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        null_cost_type_category = AnalysisCostTypeCategory.objects.create(
            analysis=analysis,
            cost_type=None,
            category=None,
        )
        AnalysisCostTypeCategoryGrant.objects.create(
            cost_type_category=null_cost_type_category,
            grant=analysis.cost_type_category_grants.first().grant,
        )

        suggestions = analysis.get_suggested_allocations()

        assert None not in suggestions
