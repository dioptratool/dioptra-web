import pytest
from django.urls import reverse

from website.models import SubcomponentCostAnalysis


@pytest.mark.django_db
class TestSubcomponentCostAnalysisDelete:
    def test_delete_subcomponent_cost_analysis(
        self,
        analysis_workflow_with_subcomponent_labels,
        client_with_admin,
    ):
        analysis_wf = analysis_workflow_with_subcomponent_labels
        analysis = analysis_wf.analysis
        subcomponent = analysis.subcomponent_cost_analysis

        assert SubcomponentCostAnalysis.objects.filter(pk=subcomponent.pk).exists()

        url = reverse(
            "subcomponent-cost-analysis-delete",
            kwargs={
                "pk": analysis.pk,
                "subcomponent_pk": subcomponent.pk,
            },
        )
        response = client_with_admin.get(f"{url}?confirmed", follow=True)

        assert response.status_code == 200
        assert not SubcomponentCostAnalysis.objects.filter(pk=subcomponent.pk).exists()
