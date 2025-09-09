from decimal import Decimal

import pytest
from django.contrib import messages
from django.forms.models import model_to_dict
from django.urls import reverse

from website.models import (
    AnalysisCostType,
    CostLineItem,
    CostLineItemConfig,
    CostType,
)
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
)
from website.views.analysis.analysis import CostLineItemUpsertView


@pytest.fixture
def insights_analysis():
    analysis = AnalysisFactory()
    analysis.add_intervention(InterventionFactory())
    return analysis


class TestInsights:
    @pytest.mark.django_db
    def test_get_cost_line_items_in_kind(self, rf, insights_analysis):
        request = rf.get(
            reverse(
                "cost-line-item-create",
                kwargs={
                    "pk": insights_analysis.id,
                    "cost_type": int(AnalysisCostType.IN_KIND),
                },
            )
        )
        request.user = insights_analysis.owner
        response = CostLineItemUpsertView.as_view()(
            request,
            pk=insights_analysis.id,
            cost_type=int(AnalysisCostType.IN_KIND),
        )
        assert response.status_code == 200
        response_form = response.context_data["form"]
        assert response_form.ANALYSIS_COST_TYPE == AnalysisCostType.IN_KIND
        assert response_form.initial == {"analysis": insights_analysis, "total_cost": 0}

    @pytest.mark.django_db
    def test_get_cost_line_items_client_time(self, rf, insights_analysis):
        request = rf.get(
            reverse(
                "cost-line-item-create",
                kwargs={
                    "pk": insights_analysis.id,
                    "cost_type": int(AnalysisCostType.CLIENT_TIME),
                },
            )
        )
        request.user = insights_analysis.owner
        response = CostLineItemUpsertView.as_view()(
            request,
            pk=insights_analysis.id,
            cost_type=int(AnalysisCostType.CLIENT_TIME),
        )

        assert response.status_code == 200
        response_form = response.context_data["form"]
        assert response_form.ANALYSIS_COST_TYPE == AnalysisCostType.CLIENT_TIME
        assert response_form.initial == {"analysis": insights_analysis, "total_cost": 0}

    @pytest.mark.django_db
    def test_get_cost_line_items_other_hq(self, rf, defaults, insights_analysis):
        request = rf.get(
            reverse(
                "cost-line-item-create",
                kwargs={
                    "pk": insights_analysis.id,
                    "cost_type": int(AnalysisCostType.OTHER_HQ),
                },
            )
        )
        request.user = insights_analysis.owner
        response = CostLineItemUpsertView.as_view()(
            request,
            pk=insights_analysis.id,
            cost_type=int(AnalysisCostType.OTHER_HQ),
        )

        assert response.status_code == 200
        response_form = response.context_data["form"]
        assert response_form.ANALYSIS_COST_TYPE == AnalysisCostType.OTHER_HQ
        assert response_form.initial == {"analysis": insights_analysis}

    @pytest.mark.django_db
    def test_create_cost_line_items_in_kind(self, rf, insights_analysis):
        assert CostLineItem.objects.count() == 0
        data = {
            "analysis": insights_analysis.pk,
            "budget_line_description": "Test Budget Line Description",
            "total_cost": "0",
            "note": "Test Note",
        }

        data["quantity"] = Decimal("3.00")
        data["unit_cost"] = Decimal("5.00")

        intervention_id = insights_analysis.interventioninstance_set.first().id
        data[f"intervention_allocation_{intervention_id}"] = Decimal("80.00")

        request = rf.post(
            reverse(
                "cost-line-item-create",
                kwargs={
                    "pk": insights_analysis.id,
                    "cost_type": int(AnalysisCostType.IN_KIND),
                },
            ),
            data,
        )
        request.user = insights_analysis.owner
        request._messages = messages.storage.default_storage(request)

        response = CostLineItemUpsertView.as_view()(
            request,
            pk=insights_analysis.pk,
            cost_type=int(AnalysisCostType.IN_KIND),
        )
        assert response.status_code == 200
        assert CostLineItem.objects.count() > 0, "At this point CostLineItems should have been created"

        cost_line_item = CostLineItem.objects.all().last()
        assert cost_line_item.analysis == insights_analysis
        assert cost_line_item.budget_line_description == data["budget_line_description"]
        assert cost_line_item.quantity == data["quantity"]
        assert cost_line_item.unit_cost == data["unit_cost"]
        assert (
            cost_line_item.config.allocations.first().allocation
            == data[f"intervention_allocation_{intervention_id}"]
        )
        assert cost_line_item.config.analysis_cost_type == AnalysisCostType.IN_KIND
        assert cost_line_item.total_cost == Decimal("15.00")
        assert cost_line_item.note == data["note"]

    @pytest.mark.django_db
    def test_create_cost_line_items_client_time(self, rf, insights_analysis):
        assert CostLineItem.objects.count() == 0
        data = {
            "analysis": insights_analysis.pk,
            "budget_line_description": "Test Budget Line Description",
            "total_cost": "0",
            "intervention_instance": insights_analysis.interventioninstance_set.first().id,
            "note": "Test Note",
        }

        data["quantity"] = Decimal("3.00")
        data["loe_or_unit"] = Decimal("4.00")
        data["unit_cost"] = Decimal("5.00")

        request = rf.post(
            reverse(
                "cost-line-item-create",
                kwargs={
                    "pk": insights_analysis.id,
                    "cost_type": int(AnalysisCostType.CLIENT_TIME),
                },
            ),
            data,
        )
        request.user = insights_analysis.owner
        request._messages = messages.storage.default_storage(request)

        response = CostLineItemUpsertView.as_view()(
            request,
            pk=insights_analysis.pk,
            cost_type=int(AnalysisCostType.CLIENT_TIME),
        )

        assert response.status_code == 200
        assert CostLineItem.objects.count() > 0, "At this point CostLineItems should have been created"

        cost_line_item = CostLineItem.objects.all().last()
        assert cost_line_item.analysis == insights_analysis
        assert cost_line_item.budget_line_description == data["budget_line_description"]
        assert cost_line_item.quantity == data["quantity"]
        assert cost_line_item.unit_cost == data["unit_cost"]
        for each_allocation in cost_line_item.config.allocations.all():
            assert each_allocation.allocation == Decimal("100")
        assert cost_line_item.config.analysis_cost_type == AnalysisCostType.CLIENT_TIME
        assert cost_line_item.total_cost == Decimal("60.00")
        assert cost_line_item.note == data["note"]

    @pytest.mark.django_db
    def test_create_cost_line_items_other_hq(self, rf, defaults, insights_analysis):
        assert CostLineItem.objects.count() == 0
        data = {
            "analysis": insights_analysis.pk,
            "budget_line_description": "Test Budget Line Description",
            "total_cost": "0",
            "note": "Test Note",
            "cost_type": CostType.objects.get(name="Support Costs").id,
        }

        data["total_cost"] = Decimal("5.00")
        intervention_id = insights_analysis.interventioninstance_set.first().id
        data[f"intervention_allocation_{intervention_id}"] = Decimal("90.00")

        request = rf.post(
            reverse(
                "cost-line-item-create",
                kwargs={
                    "pk": insights_analysis.id,
                    "cost_type": int(AnalysisCostType.OTHER_HQ),
                },
            ),
            data,
        )
        request.user = insights_analysis.owner
        request._messages = messages.storage.default_storage(request)

        response = CostLineItemUpsertView.as_view()(
            request,
            pk=insights_analysis.pk,
            cost_type=int(AnalysisCostType.OTHER_HQ),
        )
        assert not response.context_data[
            "form"
        ].errors, f"Errors on form: {response.context_data['form'].errors}"
        assert CostLineItem.objects.count() > 0, "At this point CostLineItems should have been created"

        assert response.status_code == 200
        cost_line_item = CostLineItem.objects.all().last()
        assert cost_line_item.analysis == insights_analysis
        assert cost_line_item.budget_line_description == data["budget_line_description"]
        assert cost_line_item.quantity is None
        assert cost_line_item.unit_cost is None
        assert (
            cost_line_item.config.allocations.first().allocation
            == data[f"intervention_allocation_{intervention_id}"]
        )
        assert cost_line_item.config.analysis_cost_type == AnalysisCostType.OTHER_HQ
        assert cost_line_item.total_cost == Decimal("5.00")
        assert cost_line_item.note == data["note"]

    @pytest.mark.django_db
    def test_update_cost_line_items(self, rf, insights_analysis):
        analysis = insights_analysis
        cost_line_item = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="Test Budget Line Description",
            country_code="JO",
            grant_code="GRANT123",
            sector_code="HEAL",
            unit_cost=100,
            quantity=5,
            total_cost=500.00,
        )
        config = CostLineItemConfig.objects.create(
            cost_line_item=cost_line_item,
            analysis_cost_type=AnalysisCostType.IN_KIND,
        )
        allocation = CostLineItemInterventionAllocationFactory(
            cli_config=config,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=80,
        )

        # IN KIND
        data = model_to_dict(cost_line_item)
        del data["loe_or_unit"]
        del data["months_or_unit"]
        del data["cloned_from"]

        intervention_id = analysis.interventioninstance_set.first().id
        data[f"intervention_allocation_{intervention_id}"] = allocation.allocation
        data["unit_cost"] = Decimal("200.00")

        request = rf.post(
            reverse(
                "cost-line-item-update",
                kwargs={
                    "pk": analysis.id,
                    "cost_type": int(AnalysisCostType.IN_KIND),
                    "cost_pk": cost_line_item.pk,
                },
            ),
            data,
        )
        request.user = analysis.owner
        request._messages = messages.storage.default_storage(request)

        response = CostLineItemUpsertView.as_view()(
            request,
            pk=insights_analysis.pk,
            cost_type=int(AnalysisCostType.IN_KIND),
            cost_pk=cost_line_item.pk,
        )

        assert response.status_code == 200
        cost_line_item = CostLineItem.objects.filter(pk=cost_line_item.pk).first()
        assert cost_line_item.unit_cost == Decimal("200.00")
        assert cost_line_item.total_cost == Decimal("1000.00")
