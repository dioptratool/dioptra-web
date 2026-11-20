import pytest

from website.models import Analysis
from website.tests.factories import AnalysisFactory, InterventionFactory


class TestInterventionOrder:
    @pytest.mark.django_db
    def test_add_and_remove_intervention(self):
        analysis = AnalysisFactory()
        # Initially there should be no interventions associated.
        assert analysis.interventions.count() == 0

        intervention = InterventionFactory()
        # Add intervention and confirm it was associated.
        analysis.add_intervention(intervention=intervention)
        assert analysis.interventions.count() == 1
        assert intervention in analysis.interventions.all()

        # Remove intervention and confirm it was dissociated.
        analysis.remove_intervention(intervention.id)
        assert analysis.interventions.count() == 0

    @pytest.mark.django_db
    def test_add_intervention_increments_order(self):
        analysis: Analysis = AnalysisFactory()
        intervention = InterventionFactory()
        analysis.add_intervention(intervention=intervention)

        intervention_instances = analysis.interventioninstance_set.all()
        assert len(intervention_instances) == 1
        assert intervention_instances[0].order == 0

        intervention = InterventionFactory()
        analysis.add_intervention(intervention=intervention)
        intervention_instances = analysis.interventioninstance_set.all()
        assert len(intervention_instances) == 2
        assert intervention_instances[1].order == 1

    @pytest.mark.django_db
    def test_tied_orders_remain_stable_after_editing_an_intervention(self):
        analysis = AnalysisFactory()
        first_tied = analysis.add_intervention(InterventionFactory(), order=1)
        earlier = analysis.add_intervention(InterventionFactory(), order=0)
        last_tied = analysis.add_intervention(InterventionFactory(), order=1)

        # Updating a row can change its physical position without changing its display order.
        first_tied.label = "Updated label"
        first_tied.save(update_fields=["label"])

        expected = [earlier, first_tied, last_tied]
        assert list(analysis.interventioninstance_set.all()) == expected
        assert list(analysis.interventioninstance_set.select_related("intervention")) == expected
