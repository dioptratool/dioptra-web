import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestMultiinterventionSetup:
    def test_creating_a_multiintervention_analysis(
        self,
        analysis_workflow_with_analysis_multiintervention,
    ):
        analysis = analysis_workflow_with_analysis_multiintervention.analysis
        assert analysis.interventions.count() == 2
