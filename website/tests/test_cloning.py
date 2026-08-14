import datetime

import pytest

from website.models.analysis import AnalysisCostTypeCategoryGrantIntervention
from website.models.subcomponent import SubcomponentCostAllocation
from website.tests.factories import AnalysisFactory, UserFactory
from website.utils.duplicator import clone_analysis


class TestClonedAnalysis:
    @pytest.mark.django_db
    def test_cloning_analysis(self):
        analysis = AnalysisFactory(
            start_date=datetime.date(2000, 4, 1),
            end_date=datetime.date(2020, 4, 1),
            owner=UserFactory(),
        )

        cloned_analysis = clone_analysis(analysis.pk, owner=UserFactory())
        assert analysis.start_date == cloned_analysis.start_date
        assert analysis.end_date == cloned_analysis.end_date

    @pytest.mark.django_db
    def test_cloning_analysis_with_different_date_range(self):
        analysis = AnalysisFactory(
            start_date=datetime.date(2000, 4, 1),
            end_date=datetime.date(2020, 4, 1),
            owner=UserFactory(),
        )

        new_start_date = datetime.date(2020, 12, 12)
        new_end_date = datetime.date(2021, 12, 31)
        cloned_analysis = clone_analysis(
            analysis.pk,
            start_date=new_start_date,
            end_date=new_end_date,
            owner=UserFactory(),
        )

        assert analysis.start_date != cloned_analysis.start_date
        assert analysis.end_date != cloned_analysis.end_date
        assert analysis.owner != cloned_analysis.owner

    @pytest.mark.django_db
    def test_cloning_finished_analysis_cost_line_items(self, analysis_workflow_main_flow_complete):
        analysis = analysis_workflow_main_flow_complete.analysis

        cloned_analysis = clone_analysis(
            analysis.pk,
            owner=UserFactory(),
        )

        assert analysis.cost_line_items.count() == cloned_analysis.cost_line_items.count()

    @pytest.mark.django_db
    def test_cloning_ensure_intervention_instances_are_not_duplicated(
        self, analysis_workflow_main_flow_complete
    ):
        analysis = analysis_workflow_main_flow_complete.analysis

        cloned_analysis = clone_analysis(
            analysis.pk,
            owner=UserFactory(),
        )

        assert analysis.interventioninstance_set.count() == cloned_analysis.interventioninstance_set.count()

    @pytest.mark.django_db
    def test_cloning_CostTypeCategoryGrantIntervention_point_to_the_right_object(
        self,
        analysis_workflow_main_flow_complete,
    ):
        analysis = analysis_workflow_main_flow_complete.analysis

        cloned_analysis = clone_analysis(
            analysis.pk,
            owner=UserFactory(),
        )

        scgs = cloned_analysis.cost_type_category_grants
        for each_scg in scgs:
            each_contributor: AnalysisCostTypeCategoryGrantIntervention
            for each_contributor in each_scg.contributors.all():
                assert each_contributor.intervention_instance.analysis == cloned_analysis

    @pytest.mark.django_db
    def test_cloning_finished_analysis_cost_line_items_different(self, analysis_workflow_main_flow_complete):
        analysis = analysis_workflow_main_flow_complete.analysis

        cloned_analysis = clone_analysis(
            analysis.pk,
            owner=UserFactory(),
        )

        og_keys = analysis.cost_line_items.values_list("pk", flat=True)
        clone_keys = cloned_analysis.cost_line_items.values_list("pk", flat=True)

        assert sorted(og_keys) != sorted(clone_keys)

    @pytest.mark.django_db
    def test_cloning_analysis_with_subcomponent_analyses(
        self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        analysis = analysis_workflow_with_all_cost_lines_allocated_to_subcomponents.analysis
        subcomponent_analysis = analysis.subcomponent_cost_analyses()[0]
        cli_config = analysis.cost_line_items.first().config
        allocation, _ = SubcomponentCostAllocation.objects.update_or_create(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=cli_config,
            defaults={"allocations": {"0": "100"}},
        )

        cloned_analysis = clone_analysis(
            analysis.pk,
            owner=UserFactory(),
        )
        cloned_subcomponent_analysis = cloned_analysis.subcomponent_cost_analyses()[0]

        assert subcomponent_analysis.pk != cloned_subcomponent_analysis.pk

        assert subcomponent_analysis.subcomponent_labels == cloned_subcomponent_analysis.subcomponent_labels
        cloned_allocation = cloned_subcomponent_analysis.allocations.get(cloned_from=allocation)
        assert cloned_allocation.allocations == {"0": "100"}
        assert cloned_allocation.cli_config.cost_line_item.analysis == cloned_analysis
