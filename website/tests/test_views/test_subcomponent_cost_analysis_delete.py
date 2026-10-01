import pytest
from django.urls import reverse

from website.models import Analysis, AnalysisStatus, SubcomponentCostAnalysis
from website.tests.factories import UserFactory


@pytest.mark.django_db
class TestSubcomponentCostAnalysisDelete:
    def test_delete_subcomponent_cost_analysis(
        self,
        analysis_workflow_with_subcomponent_labels,
        client_with_admin,
    ):
        analysis_wf = analysis_workflow_with_subcomponent_labels
        analysis = analysis_wf.analysis
        subcomponent = analysis.subcomponent_cost_analyses()[0]

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

    def test_primary_country_editor_can_reset(self, analysis_workflow_with_subcomponent_labels, client):
        """The reset is an edit, so the edit permission applies (it used to require delete)."""
        analysis = analysis_workflow_with_subcomponent_labels.analysis
        subcomponent = analysis.subcomponent_cost_analyses()[0]
        editor = UserFactory()
        editor.primary_countries.add(analysis.country)
        client.force_login(editor)
        url = reverse(
            "subcomponent-cost-analysis-delete",
            kwargs={"pk": analysis.pk, "subcomponent_pk": subcomponent.pk},
        )

        response = client.get(f"{url}?confirmed", follow=True)

        assert response.status_code == 200
        assert not SubcomponentCostAnalysis.objects.filter(pk=subcomponent.pk).exists()

    def test_basic_users_cannot_reset_a_validated_analysis(
        self, analysis_workflow_with_subcomponent_labels, client
    ):
        analysis = analysis_workflow_with_subcomponent_labels.analysis
        subcomponent = analysis.subcomponent_cost_analyses()[0]
        Analysis.objects.filter(pk=analysis.pk).update(analysis_status=AnalysisStatus.VALIDATED)
        client.force_login(analysis.owner)
        url = reverse(
            "subcomponent-cost-analysis-delete",
            kwargs={"pk": analysis.pk, "subcomponent_pk": subcomponent.pk},
        )

        response = client.get(f"{url}?confirmed")

        assert response.status_code == 403
        assert SubcomponentCostAnalysis.objects.filter(pk=subcomponent.pk).exists()
