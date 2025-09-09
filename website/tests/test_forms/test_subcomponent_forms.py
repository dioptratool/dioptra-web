import pytest

from website.forms.subcomponent import (
    ConfirmSubcomponentCostAnalysisForm,
    EditSubcomponentCostAnalysisLabelsForm,
)
from website.models import SubcomponentCostAnalysis
from website.tests.factories import SubcomponentCostAnalysisFactory


@pytest.mark.django_db
class TestEditSubcomponentCostAnalysisLabelsForm:
    def test_form_valid(self, analysis_workflow_with_subcomponent_labels, a_user):
        data = {
            "subcomponent_labels": ["one", "two", "three"],
        }
        form = EditSubcomponentCostAnalysisLabelsForm(
            data=data,
            instance=analysis_workflow_with_subcomponent_labels.analysis.subcomponent_cost_analysis,
            user=a_user,
        )
        assert form.is_valid()

    def test_form_invalid(self, analysis_workflow_with_subcomponent_labels, a_user):
        data = {"subcomponent_labels": "honk"}
        form = EditSubcomponentCostAnalysisLabelsForm(
            data=data,
            instance=analysis_workflow_with_subcomponent_labels.analysis.subcomponent_cost_analysis,
            user=a_user,
        )
        assert not form.is_valid()

    def test_form_subcomponent_labels_field(self, analysis_workflow_with_subcomponent_labels, a_user):
        form = EditSubcomponentCostAnalysisLabelsForm(
            instance=analysis_workflow_with_subcomponent_labels.analysis.subcomponent_cost_analysis,
            user=a_user,
        )
        assert "subcomponent_labels" in form.fields


@pytest.mark.django_db
class TestCreateSubcomponentCostAnalysisForm:
    def test_subcomponent_labels_confirmed_validation_error(self, analysis_workflow_with_client_time_added):
        subcomponent_cost_analysis = SubcomponentCostAnalysisFactory(
            analysis=analysis_workflow_with_client_time_added.analysis,
            subcomponent_labels_confirmed=False,
        )

        form = ConfirmSubcomponentCostAnalysisForm(
            data={"subcomponent_labels_confirmed": None},
            instance=analysis_workflow_with_client_time_added.analysis,
        )
        assert not form.is_valid()
        assert "subcomponent_labels_confirmed" in form.errors
        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.get(pk=subcomponent_cost_analysis.pk)
        assert not subcomponent_cost_analysis.subcomponent_labels_confirmed

    def test_subcomponent_labels_confirmed_validation_success(self, analysis_workflow_with_client_time_added):
        subcomponent_cost_analysis = SubcomponentCostAnalysisFactory(
            analysis=analysis_workflow_with_client_time_added.analysis,
            subcomponent_labels_confirmed=False,
        )
        assert not subcomponent_cost_analysis.subcomponent_labels_confirmed

        form = ConfirmSubcomponentCostAnalysisForm(
            data={"subcomponent_labels_confirmed": True},
            instance=analysis_workflow_with_client_time_added.analysis,
        )
        assert form.is_valid()

        form.save()

        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.get(pk=subcomponent_cost_analysis.pk)
        assert subcomponent_cost_analysis.subcomponent_labels_confirmed
