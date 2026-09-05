from decimal import Decimal

import pytest
from django.urls import reverse

from website.models import CostType
from website.models.cost_line_item import CostLineItemInterventionAllocation
from website.models.cost_type import ProgramCost, Support
from website.tests.factories import (
    AnalysisFactory,
    CategoryFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
)
from website.views.analysis.steps.allocate import AllocateCostTypeGrant


@pytest.fixture
def program_cost_case(defaults):
    analysis = AnalysisFactory(grants="Grant / A")
    interventions = [
        analysis.add_intervention(
            InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"]),
            label=label,
            parameters={"number_of_teachers": 10, "number_of_days_of_training": 5},
        )
        for label in ["Malnutrition Prevention", "Treatments at Stabilization Center"]
    ]
    category = CategoryFactory(name="Travel & Transportation")
    cost_type = CostType.objects.get(type=ProgramCost.id)

    def make_item(amount, allocations=None, **kwargs):
        item = CostLineItemFactory(analysis=analysis, grant_code="Grant / A", total_cost=amount)
        config = CostLineItemConfigFactory(
            cost_line_item=item,
            cost_type=cost_type,
            category=kwargs.pop("category", category),
            **kwargs,
        )
        if allocations is not None:
            for intervention, allocation in zip(interventions, allocations):
                CostLineItemInterventionAllocationFactory(
                    cli_config=config,
                    intervention_instance=intervention,
                    allocation=allocation,
                )
        return item

    known = [make_item(100, [100, 0]), make_item(100, [0, 100])]
    selected = [make_item(60), make_item(40)]
    analysis.ensure_cost_type_category_objects()
    analysis.cost_type_categories.update(confirmed=True)
    category_grant = analysis.cost_type_category_grants.get(
        grant="Grant / A",
        cost_type_category__category=category,
        cost_type_category__cost_type=cost_type,
    )
    url_kwargs = {"pk": analysis.pk, "cost_type_pk": cost_type.pk, "grant": "Grant / A"}
    return {
        "analysis": analysis,
        "interventions": interventions,
        "known": known,
        "selected": selected,
        "category": category_grant,
        "make_item": make_item,
        "kwargs": url_kwargs,
        "bulk_url": reverse("analysis-allocate-cost_type-grant-bulk", kwargs=url_kwargs),
        "single_url": reverse("analysis-allocate-cost_type-grant-suggest", kwargs=url_kwargs),
    }


def selection(case):
    return ",".join(str(item.config.pk) for item in case["selected"])


@pytest.mark.django_db
class TestProgramCostSuggestions:
    def test_legacy_calculation_includes_zeroes_and_counts_each_intervention(self, program_cost_case):
        suggestion = program_cost_case["category"].program_cost_suggestion()
        assert suggestion == {
            "numerator": Decimal(200),
            "denominator": Decimal(400),
            "allocation": "50.00",
            "uses_fallback": False,
        }

    def test_fallback_matches_legacy_arithmetic(self, program_cost_case):
        case = program_cost_case
        category = CategoryFactory()
        target = case["make_item"](20, category=category)
        case["analysis"].ensure_cost_type_category_objects()
        target_category = case["analysis"].cost_type_category_grants.get(
            cost_type_category__category=category, grant=target.grant_code
        )
        legacy = AllocateCostTypeGrant()
        legacy.cost_type_category_grants = case["analysis"].cost_type_category_grants.filter(
            cost_type_category__cost_type__type=ProgramCost.id, grant=target.grant_code
        )
        suggestion = target_category.program_cost_suggestion()
        assert suggestion["uses_fallback"]
        assert suggestion["numerator"] == legacy.calc_item_costs()
        assert round(suggestion["numerator"], 4) == Decimal(200)
        assert suggestion["denominator"] == legacy.calc_item_totals() == Decimal(120)
        assert suggestion["allocation"] + "%" == legacy.calc_all_errors_suggest() == "166.67%"

    def test_preview_uses_whole_category_and_never_saves(self, program_cost_case, client_with_admin):
        case = program_cost_case
        response = client_with_admin.get(
            case["bulk_url"],
            {
                "config_ids": selection(case),
                "suggestion": "1",
                "site_code": "hidden-site",
            },
        )
        assert response.status_code == 200
        assert response["Cache-Control"] == "no-store"
        assert response.json()["allocation"] == "50.00"
        for intervention in case["interventions"]:
            assert intervention.display_name() in response.json()["html"]
        assert not CostLineItemInterventionAllocation.objects.filter(
            cli_config__in=[item.config for item in case["selected"]]
        ).exists()
        # A subsequent request gets fresh saved data, with no stale preview cache.
        case["known"][0].config.allocations.filter(intervention_instance=case["interventions"][0]).update(
            allocation=20
        )
        response = client_with_admin.get(case["bulk_url"], {"config_ids": selection(case), "suggestion": "1"})
        assert response.json()["allocation"] == "30.00"

    def test_normal_panel_waits_for_suggest_action(self, program_cost_case, client_with_admin):
        case = program_cost_case
        response = client_with_admin.get(case["bulk_url"], {"config_ids": selection(case)})
        assert response.status_code == 200
        assert not response.context["show_suggestion"]
        assert b"Suggest Allocation" in response.content
        assert b"Suggested Allocation Calculations" not in response.content

    def test_single_item_opens_with_suggestions_without_saving(self, program_cost_case, client_with_admin):
        case = program_cost_case
        response = client_with_admin.get(case["single_url"], {"config_ids": case["selected"][0].config.pk})
        assert response.status_code == 200
        assert response.context["show_suggestion"]
        form = response.context["form"]
        for intervention in case["interventions"]:
            assert form[f"allocation_{intervention.pk}"].value() == "50.00"
        assert "notes" not in form.fields
        assert b"Accept" in response.content and b"Dismiss" in response.content
        assert not case["selected"][0].config.allocations.exists()

    @pytest.mark.parametrize("single", [False, True])
    def test_save_replaces_selected_rows_and_cleared_field_is_zero(
        self, program_cost_case, client_with_admin, single
    ):
        case = program_cost_case
        selected = case["selected"][:1] if single else case["selected"]
        for item in selected:
            for intervention in case["interventions"]:
                CostLineItemInterventionAllocationFactory(
                    cli_config=item.config,
                    intervention_instance=intervention,
                    allocation=40,
                )
        before = list(case["known"][0].config.allocations.values_list("allocation", flat=True))
        response = client_with_admin.post(
            case["single_url"] if single else case["bulk_url"],
            {
                "config_ids": [item.config.pk for item in selected],
                f"allocation_{case['interventions'][0].pk}": "25",
                f"allocation_{case['interventions'][1].pk}": "",
                "suggestion_requested": "True",
            },
        )
        assert response.status_code == 200
        assert not response.context["form"].errors
        assert response.context["panel_commands"]
        for item in selected:
            allocations = dict(item.config.allocations.values_list("intervention_instance_id", "allocation"))
            assert allocations == {
                case["interventions"][0].pk: Decimal(25),
                case["interventions"][1].pk: 0,
            }
        assert list(case["known"][0].config.allocations.values_list("allocation", flat=True)) == before

    def test_invalid_total_preserves_edits_and_saved_allocations(self, program_cost_case, client_with_admin):
        case = program_cost_case
        response = client_with_admin.post(
            case["bulk_url"],
            {
                "config_ids": [item.config.pk for item in case["selected"]],
                **{f"allocation_{intervention.pk}": "60" for intervention in case["interventions"]},
                "suggestion_requested": "True",
            },
        )
        assert response.status_code == 200
        assert b"Total allocation cannot exceed 100%" in response.content
        assert response.context["suggestion"]["allocation"] == "50.00"
        for intervention in case["interventions"]:
            assert response.context["form"][f"allocation_{intervention.pk}"].value() == "60"
        assert not case["selected"][0].config.allocations.exists()

    @pytest.mark.parametrize("invalid_value", [None, "?"])
    def test_missing_or_invalid_fields_do_not_clear_allocations(
        self, program_cost_case, client_with_admin, invalid_value
    ):
        case = program_cost_case
        data = {
            "config_ids": [case["known"][0].config.pk],
            f"allocation_{case['interventions'][0].pk}": "25",
            "suggestion_requested": "False",
        }
        if invalid_value is not None:
            data[f"allocation_{case['interventions'][1].pk}"] = invalid_value
        response = client_with_admin.post(case["bulk_url"], data)
        assert response.status_code == 200
        assert response.context["form"].errors
        assert not response.context["show_suggestion"]
        assert sorted(case["known"][0].config.allocations.values_list("allocation", flat=True)) == [0, 100]

    def test_no_denominator_is_unavailable_but_zero_is_a_valid_suggestion(
        self, program_cost_case, client_with_admin
    ):
        case = program_cost_case
        case["analysis"].cost_line_items.update(total_cost=0)
        response = client_with_admin.get(case["bulk_url"], {"config_ids": selection(case), "suggestion": "1"})
        assert response.json()["allocation"] is None
        assert "Unable to calculate" in response.json()["html"]
        case["analysis"].cost_line_items.update(total_cost=100)
        CostLineItemInterventionAllocation.objects.filter(
            cli_config__cost_line_item__analysis=case["analysis"]
        ).update(allocation=0)
        response = client_with_admin.get(case["bulk_url"], {"config_ids": selection(case), "suggestion": "1"})
        assert response.json()["allocation"] == "0.00"
        assert "Unable to calculate" not in response.json()["html"]

    def test_cross_category_selection_is_rejected(self, program_cost_case, client_with_admin):
        case = program_cost_case
        other = case["make_item"](100, category=CategoryFactory())
        ids = [case["selected"][0].config.pk, other.config.pk]
        response = client_with_admin.get(case["bulk_url"], {"config_ids": ",".join(map(str, ids))})
        assert response.status_code == 404
        response = client_with_admin.post(
            case["bulk_url"],
            {
                "config_ids": ids,
                **{f"allocation_{i.pk}": "10" for i in case["interventions"]},
            },
        )
        assert response.status_code == 404
        assert not other.config.allocations.exists()

    def test_foreign_selection_and_support_suggestions_are_rejected(
        self, program_cost_case, client_with_admin
    ):
        case = program_cost_case
        foreign_config = CostLineItemConfigFactory()
        response = client_with_admin.get(
            case["bulk_url"], {"config_ids": foreign_config.pk, "suggestion": "1"}
        )
        assert response.status_code == 404
        support = CostType.objects.get(type=Support.id)
        case["selected"][0].config.cost_type = support
        case["selected"][0].config.save()
        url = reverse(
            "analysis-allocate-cost_type-grant-bulk",
            kwargs={**case["kwargs"], "cost_type_pk": support.pk},
        )
        response = client_with_admin.get(
            url, {"config_ids": case["selected"][0].config.pk, "suggestion": "1"}
        )
        assert response.status_code == 404
        response = client_with_admin.get(url, {"config_ids": case["selected"][0].config.pk})
        assert b"program-cost-suggest-button" not in response.content

    def test_suggestions_require_analysis_permission(self, program_cost_case, client, a_user):
        case = program_cost_case
        client.force_login(a_user)
        response = client.get(case["bulk_url"], {"config_ids": selection(case), "suggestion": "1"})
        assert response.status_code == 403

    def test_question_mark_no_longer_requests_help_or_deletes_allocations(
        self, program_cost_case, client_with_admin
    ):
        case = program_cost_case
        item = case["known"][0]
        response = client_with_admin.post(
            reverse("analysis-allocate-cost_type-grant", kwargs=case["kwargs"]),
            {
                f"cost_line_item_allocation_{item.pk}_{intervention.pk}": "?"
                for intervention in case["interventions"]
            },
        )
        assert response.status_code == 200
        assert b"Not a number" in response.content
        assert b"accept_allocation_button" not in response.content
        assert b"program-cost-suggest-item" in response.content
        assert sorted(item.config.allocations.values_list("allocation", flat=True)) == [
            0,
            100,
        ]
