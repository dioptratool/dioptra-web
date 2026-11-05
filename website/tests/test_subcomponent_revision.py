"""
Feature 86, Issue 3: a form opened before an intervention's sub-components were added,
removed or reordered is rejected instead of writing percentages onto the wrong components.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from website.forms.analysis import SubcomponentLabelsForm
from website.forms.cost_line_item import InKindCostLineItemForm
from website.models import SubcomponentCostAllocation, SubcomponentCostAnalysis
from website.models.cost_type import ProgramCost
from website.subcomponent_labels import Component, update_subcomponent_labels
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
    InterventionInstanceFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
    UserFactory,
)
from website.utils.duplicator import clone_analysis

STALE = "changed after this form was opened"


def components(*pairs):
    return [Component(label=label, source=source) for label, source in pairs]


@pytest.fixture
def subcomponent_analysis(defaults):
    return SubcomponentCostAnalysisFactory(subcomponent_labels=["A", "B", "C"])


@pytest.mark.django_db
class TestRevision:
    def test_new_analysis_starts_at_zero(self, subcomponent_analysis):
        assert subcomponent_analysis.revision == 0

    def test_structural_edits_bump_the_revision_and_renames_do_not(self, subcomponent_analysis):
        update_subcomponent_labels(subcomponent_analysis, components(("A2", 0), ("B", 1), ("C", 2)))
        assert subcomponent_analysis.revision == 0  # rename only

        update_subcomponent_labels(subcomponent_analysis, components(("B", 1), ("A2", 0), ("C", 2)))
        assert subcomponent_analysis.revision == 1  # reorder

        update_subcomponent_labels(subcomponent_analysis, components(("B", 0), ("C", 2)))
        assert subcomponent_analysis.revision == 2  # remove

        update_subcomponent_labels(subcomponent_analysis, components(("B", 0), ("C", 1), ("D", None)))
        assert subcomponent_analysis.revision == 3  # add

        subcomponent_analysis.refresh_from_db()
        assert subcomponent_analysis.revision == 3


def _row(subcomponent_analysis, allocations):
    config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(analysis=subcomponent_analysis.analysis)
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config,
        intervention_instance=subcomponent_analysis.intervention_instance,
        allocation=Decimal("100"),
    )
    return SubcomponentCostAllocationFactory(
        subcomponent_analysis=subcomponent_analysis, cli_config=config, allocations=allocations
    )


@pytest.mark.django_db
class TestLabelEditorStaleCheck:
    def _data(self, subcomponent_analysis, revision, analysis_id=None):
        return {
            "subcomponent_labels": '["C", "A", "B"]',
            "subcomponent_sources": "[2, 0, 1]",
            "subcomponent_analysis_id": str(analysis_id or subcomponent_analysis.id),
            "subcomponent_revision": str(revision),
        }

    def test_stale_revision_is_rejected_without_writing(self, subcomponent_analysis):
        row = _row(subcomponent_analysis, {"0": "20", "1": "30", "2": "50"})
        update_subcomponent_labels(subcomponent_analysis, components(("B", 1), ("A", 0), ("C", 2)))
        instance = subcomponent_analysis.intervention_instance
        instance.refresh_from_db()

        form = SubcomponentLabelsForm(
            data=self._data(subcomponent_analysis, revision=0), intervention_instance=instance
        )

        assert not form.is_valid()
        assert STALE in str(form.non_field_errors())
        row.refresh_from_db()
        subcomponent_analysis.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["B", "A", "C"]
        assert row.allocations == {"0": "30", "1": "20", "2": "50"}

    def test_matching_revision_saves(self, subcomponent_analysis):
        instance = subcomponent_analysis.intervention_instance

        form = SubcomponentLabelsForm(
            data=self._data(subcomponent_analysis, revision=0), intervention_instance=instance
        )

        assert form.is_valid(), form.errors
        form.save()
        subcomponent_analysis.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["C", "A", "B"]
        assert subcomponent_analysis.revision == 1

    def test_form_opened_before_delete_and_recreate_is_rejected(self, subcomponent_analysis):
        instance = subcomponent_analysis.intervention_instance
        old_id = subcomponent_analysis.id
        subcomponent_analysis.delete()
        SubcomponentCostAnalysisFactory(intervention_instance=instance, subcomponent_labels=["A", "B", "C"])
        instance = type(instance).objects.get(pk=instance.pk)

        form = SubcomponentLabelsForm(
            data=self._data(subcomponent_analysis, revision=0, analysis_id=old_id),
            intervention_instance=instance,
        )

        assert not form.is_valid()
        assert STALE in str(form.non_field_errors())

    def test_form_opened_before_creation_is_rejected_once_an_analysis_exists(self, subcomponent_analysis):
        instance = subcomponent_analysis.intervention_instance
        data = {
            "subcomponent_labels": '["X", "Y"]',
            "subcomponent_sources": "[null, null]",
            "subcomponent_analysis_id": "",
            "subcomponent_revision": "",
        }

        form = SubcomponentLabelsForm(data=data, intervention_instance=instance)

        assert not form.is_valid()
        assert STALE in str(form.non_field_errors())

    def test_editor_renders_identity_fields(self, subcomponent_analysis):
        form = SubcomponentLabelsForm(intervention_instance=subcomponent_analysis.intervention_instance)
        html = form.as_p()

        assert f'name="subcomponent_analysis_id" value="{subcomponent_analysis.id}"' in html
        assert 'name="subcomponent_revision" value="0"' in html


def _allocate_setup(analysis):
    intervention_instance = analysis.interventioninstance_set.first()
    subcomponent_analysis = SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance, subcomponent_labels=["Treatment", "Outreach"]
    )
    cost_type_category_grant = analysis.cost_type_category_grants.filter(
        cost_type_category__cost_type__type=ProgramCost.id
    ).first()
    cost_line_items = list(
        analysis.cost_line_items.filter(
            grant_code=cost_type_category_grant.grant,
            config__cost_type=cost_type_category_grant.cost_type_category.cost_type,
        )
    )
    return intervention_instance, subcomponent_analysis, cost_type_category_grant.grant, cost_line_items


def _bump(subcomponent_analysis):
    """A structural edit made in another tab: swap the two components."""
    update_subcomponent_labels(subcomponent_analysis, components(("Outreach", 1), ("Treatment", 0)))
    return subcomponent_analysis.revision


@pytest.mark.django_db
class TestAllocatePageStaleCheck:
    def _url(self, analysis, intervention_instance, grant):
        return reverse(
            "analysis-allocate-subcomponents-intervention-grant",
            kwargs={"pk": analysis.pk, "intervention_instance_pk": intervention_instance.pk, "grant": grant},
        )

    def _data(self, subcomponent_analysis, cost_line_items, revision):
        data = {
            "subcomponent_analysis_id": str(subcomponent_analysis.id),
            "subcomponent_revision": str(revision),
        }
        for cli in cost_line_items:
            data[f"cost_line_item_subcomponent_allocation_{cli.id}_{subcomponent_analysis.id}_0"] = "60"
            data[f"cost_line_item_subcomponent_allocation_{cli.id}_{subcomponent_analysis.id}_1"] = "40"
        return data

    def test_page_renders_identity_inputs(self, analysis_workflow_with_allocations, client_with_admin):
        analysis = analysis_workflow_with_allocations.analysis
        instance, subcomponent_analysis, grant, _ = _allocate_setup(analysis)

        response = client_with_admin.get(self._url(analysis, instance, grant))

        content = response.content.decode()
        assert f'name="subcomponent_analysis_id" value="{subcomponent_analysis.id}"' in content
        assert 'name="subcomponent_revision" value="0"' in content

    def test_stale_submission_is_rejected_whole(self, analysis_workflow_with_allocations, client_with_admin):
        analysis = analysis_workflow_with_allocations.analysis
        instance, subcomponent_analysis, grant, cost_line_items = _allocate_setup(analysis)
        _bump(subcomponent_analysis)

        response = client_with_admin.post(
            self._url(analysis, instance, grant),
            data=self._data(subcomponent_analysis, cost_line_items, revision=0),
        )

        assert response.status_code == 200
        assert STALE in response.content.decode()
        assert not SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis
        ).exists()

    def test_current_submission_saves(self, analysis_workflow_with_allocations, client_with_admin):
        analysis = analysis_workflow_with_allocations.analysis
        instance, subcomponent_analysis, grant, cost_line_items = _allocate_setup(analysis)
        revision = _bump(subcomponent_analysis)

        response = client_with_admin.post(
            self._url(analysis, instance, grant),
            data=self._data(subcomponent_analysis, cost_line_items, revision=revision),
        )

        assert response.status_code == 302
        assert SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis, allocations={"0": "60", "1": "40"}
        ).count() == len(cost_line_items)


@pytest.mark.django_db
class TestBulkPanelStaleCheck:
    def _url(self, analysis, intervention_instance, grant):
        return reverse(
            "analysis-allocate-subcomponents-intervention-grant-bulk",
            kwargs={"pk": analysis.pk, "intervention_instance_pk": intervention_instance.pk, "grant": grant},
        )

    def test_panel_renders_revision_field(self, analysis_workflow_with_allocations, client_with_admin):
        analysis = analysis_workflow_with_allocations.analysis
        instance, subcomponent_analysis, grant, cost_line_items = _allocate_setup(analysis)
        config_ids = ",".join(str(cli.config.id) for cli in cost_line_items)

        response = client_with_admin.get(f"{self._url(analysis, instance, grant)}?config_ids={config_ids}")

        assert 'name="subcomponent_revision" value="0"' in response.content.decode()

    def test_stale_submission_is_rejected(self, analysis_workflow_with_allocations, client_with_admin):
        analysis = analysis_workflow_with_allocations.analysis
        instance, subcomponent_analysis, grant, cost_line_items = _allocate_setup(analysis)
        _bump(subcomponent_analysis)

        response = client_with_admin.post(
            self._url(analysis, instance, grant),
            data={
                "config_ids": [str(cli.config.id) for cli in cost_line_items],
                "subcomponent_allocation_0": "60",
                "subcomponent_allocation_1": "40",
                "subcomponent_revision": "0",
            },
        )

        assert response.status_code == 200
        assert STALE in response.content.decode()
        assert not SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis
        ).exists()


@pytest.mark.django_db
class TestInKindFormStaleCheck:
    def _setup(self):
        analysis = AnalysisFactory(in_kind_contributions=True)
        instance = analysis.add_intervention(InterventionFactory())
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=instance, subcomponent_labels=["Treatment", "Outreach"]
        )
        data = {
            "analysis": analysis.pk,
            "budget_line_description": "Medical Supplies",
            "total_cost": "0",
            "quantity": "3.00",
            "unit_cost": "5.00",
            "note": "",
            f"intervention_allocation_{instance.id}": "100",
            InKindCostLineItemForm.subcomponent_field_name(subcomponent_analysis.id, 0): "40",
            InKindCostLineItemForm.subcomponent_field_name(subcomponent_analysis.id, 1): "60",
        }
        return analysis, subcomponent_analysis, data

    def test_form_renders_revision_hidden_field(self, defaults):
        analysis, subcomponent_analysis, _ = self._setup()

        form = InKindCostLineItemForm(initial={"analysis": analysis, "total_cost": 0})

        names = {field.name: field.value() for field in form.hidden_fields()}
        assert names[f"subcomponent_revision_{subcomponent_analysis.id}"] == 0

    def test_stale_submission_is_rejected(self, defaults):
        analysis, subcomponent_analysis, data = self._setup()
        _bump(subcomponent_analysis)
        data[f"subcomponent_revision_{subcomponent_analysis.id}"] = "0"

        form = InKindCostLineItemForm(data=data, initial={"analysis": analysis, "total_cost": 0})

        assert not form.is_valid()
        assert STALE in str(form.non_field_errors())
        assert not analysis.cost_line_items.exists()

    def test_current_submission_saves(self, defaults):
        analysis, subcomponent_analysis, data = self._setup()
        data[f"subcomponent_revision_{subcomponent_analysis.id}"] = str(_bump(subcomponent_analysis))

        form = InKindCostLineItemForm(data=data, initial={"analysis": analysis, "total_cost": 0})

        assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_cloning_copies_the_revision(analysis_workflow_with_subcomponent_labels):
    analysis = analysis_workflow_with_subcomponent_labels.analysis
    subcomponent_analysis = analysis.subcomponent_cost_analyses()[0]
    labels = subcomponent_analysis.subcomponent_labels
    update_subcomponent_labels(
        subcomponent_analysis, [Component(label, idx) for idx, label in reversed(list(enumerate(labels)))]
    )
    assert subcomponent_analysis.revision == 1

    clone = clone_analysis(analysis.pk, owner=UserFactory())

    cloned = SubcomponentCostAnalysis.objects.get(intervention_instance__analysis=clone)
    assert cloned.revision == 1
    assert cloned.subcomponent_labels == list(reversed(labels))
