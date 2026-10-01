import datetime

import pytest
from django.utils import timezone

from website.models import Analysis, AnalysisStatus
from website.models.analysis import AnalysisCostTypeCategoryGrantIntervention
from website.models.subcomponent import SubcomponentCostAllocation
from website.tests.factories import AnalysisFactory, UserFactory
from website.utils.duplicator import clone_analysis
from website.intervention_metadata import resolve_metadata
from website.models import InterventionInstance
from website.models.intervention_metadata import MetadataFieldType, MetadataNumberType
from website.tests.factories import (
    InterventionFactory,
    InterventionInstanceFactory,
    InterventionMetadataFieldFactory,
    InterventionMetadataOptionFactory,
)


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

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "new_dates",
        [
            {},
            {"start_date": datetime.date(2022, 1, 1), "end_date": datetime.date(2022, 12, 31)},
        ],
        ids=["same_dates", "new_dates"],
    )
    def test_cloning_resets_lifecycle_and_archive_fields(self, new_dates):
        """A duplicate starts its own lifecycle; the source's status, archive state and audits are not copied."""
        actor = UserFactory()
        long_ago = timezone.now() - datetime.timedelta(days=90)
        analysis = AnalysisFactory(
            owner=UserFactory(),
            lifecycle__analysis_status=AnalysisStatus.VALIDATED,
            lifecycle__status_changed_by=actor,
            lifecycle__status_changed_at=long_ago,
            lifecycle__is_archived=True,
            lifecycle__archived_by=actor,
            lifecycle__archived_at=long_ago,
        )
        new_owner = UserFactory()

        cloned_analysis = clone_analysis(analysis.pk, owner=new_owner, **new_dates)

        stored_clone = Analysis.objects.get(pk=cloned_analysis.pk)
        assert stored_clone.cloned_from == analysis
        assert stored_clone.analysis_status == AnalysisStatus.IN_PROGRESS
        assert stored_clone.is_archived is False
        assert stored_clone.status_changed_by == new_owner
        assert stored_clone.status_changed_at == stored_clone.created
        assert stored_clone.created > analysis.created
        assert stored_clone.archived_by is None
        assert stored_clone.archived_at is None
        # The returned instance carries the stored values, not the provisional ones.
        assert cloned_analysis.status_changed_at == stored_clone.status_changed_at

        source = Analysis.objects.get(pk=analysis.pk)
        assert source.analysis_status == AnalysisStatus.VALIDATED
        assert source.status_changed_by == actor
        assert source.status_changed_at == long_ago
        assert source.is_archived is True
        assert source.archived_by == actor
        assert source.archived_at == long_ago

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "new_dates",
        [
            {},
            {"start_date": datetime.date(2022, 1, 1), "end_date": datetime.date(2022, 12, 31)},
        ],
        ids=["same_dates", "new_dates"],
    )
    def test_cloning_copies_intervention_metadata_exactly(self, new_dates):
        """Each copied instance carries its own metadata JSON unchanged, under the same field and option keys."""
        intervention = InterventionFactory()
        text = InterventionMetadataFieldFactory(intervention=intervention, name="Partner", order=1)
        number = InterventionMetadataFieldFactory(
            intervention=intervention,
            name="Budget",
            field_type=MetadataFieldType.NUMBER,
            number_type=MetadataNumberType.DECIMAL,
            order=2,
        )
        multi = InterventionMetadataFieldFactory(
            intervention=intervention, name="Approach", field_type=MetadataFieldType.MULTIPLE_CHOICE, order=3
        )
        options = [
            InterventionMetadataOptionFactory(field=multi, label=label, order=i)
            for i, label in enumerate("XY")
        ]
        tricky_text = (
            "Quote \" backslash \\ tab \t cr \r lf \r\n newline \n apostrophe ' Ñandú 日本語 🙂 =SUM(A1)"
        )
        metadata = {
            text.storage_key: tricky_text,
            number.storage_key: "-1234567890.123456789",
            multi.storage_key: [option.storage_key for option in options],
            "0d5a2c1e-orphan": "invisible but copied as is",
        }
        analysis = AnalysisFactory(owner=UserFactory())
        first = InterventionInstanceFactory(
            analysis=analysis, intervention=intervention, label="First", metadata=metadata
        )
        # The same intervention again, with its own values.
        second = InterventionInstanceFactory(
            analysis=analysis, intervention=intervention, label="Second", metadata={text.storage_key: "Other"}
        )

        cloned_analysis = clone_analysis(analysis.pk, owner=UserFactory(), **new_dates)

        copies = {
            copy.cloned_from_id: copy
            for copy in InterventionInstance.objects.filter(analysis=cloned_analysis)
        }
        assert set(copies) == {first.pk, second.pk}
        first_copy, second_copy = copies[first.pk], copies[second.pk]
        assert first_copy.metadata == metadata
        assert first_copy.metadata[text.storage_key] == tricky_text
        assert first_copy.intervention_id == intervention.pk
        assert first_copy.label == "First"
        assert second_copy.metadata == {text.storage_key: "Other"}
        assert second_copy.label == "Second"
        # The copy resolves against the same definitions as the source: same labels, same values.
        assert (
            [(row.name, row.display) for row in resolve_metadata(first_copy)]
            == [(row.name, row.display) for row in resolve_metadata(first)]
            == [("Partner", tricky_text), ("Budget", "-1,234,567,890.123456789"), ("Approach", "X, Y")]
        )

        # Independent objects: editing the copy leaves the source alone, and vice versa.
        first_copy.metadata = {text.storage_key: "Changed on the copy"}
        first_copy.save()
        assert InterventionInstance.objects.get(pk=first.pk).metadata == metadata
        InterventionInstance.objects.filter(pk=first.pk).update(metadata={})
        assert InterventionInstance.objects.get(pk=first_copy.pk).metadata == {
            text.storage_key: "Changed on the copy"
        }
