from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from website.models import CostType
from website.models.cost_line_item import CostLineItemInterventionAllocation
from website.models.cost_type import ProgramCost, Support
from website.tests.factories import (
    AnalysisFactory,
    CategoryFactory,
    CostLineItemConfigFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
)

SUGGESTED_CLASS = "bulk-allocation-input--suggested"


def add_intervention(analysis, label=None):
    return analysis.add_intervention(
        InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"]),
        label=label,
        parameters={"number_of_teachers": 10, "number_of_days_of_training": 5},
    )


@pytest.fixture
def program_cost_case(make_program_cost_item, client_with_admin):
    """A Program Cost grant/category with two allocated peers and two unallocated selected items.

    ``preview(items)`` requests the suggestion JSON and ``save(items, percentages)`` posts
    percentages keyed by intervention pk; both accept ``url``/``client`` overrides and extra
    request parameters, and return the response.
    """
    analysis = AnalysisFactory(grants="Grant / A")
    interventions = [
        add_intervention(analysis, label)
        for label in ["Malnutrition Prevention", "Treatments at Stabilization Center"]
    ]
    category = CategoryFactory(name="Travel & Transportation")
    cost_type = CostType.objects.get(type=ProgramCost.id)

    def make_item(amount, allocations=(), **kwargs):
        kwargs.setdefault("category", category)
        return make_program_cost_item(
            analysis, amount, allocations, interventions=interventions, grant="Grant / A", **kwargs
        )

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
    bulk_url = reverse("analysis-allocate-cost_type-grant-bulk", kwargs=url_kwargs)

    def preview(items, *, url=bulk_url, client=client_with_admin, **params):
        config_ids = ",".join(str(item.config.pk) for item in items)
        return client.get(url, {"config_ids": config_ids, "suggestion": "1", **params})

    def save(items, percentages, *, url=bulk_url, client=client_with_admin, **data):
        return client.post(
            url,
            {
                "config_ids": [item.config.pk for item in items],
                "suggestion_requested": "True",
                **{f"allocation_{key}": value for key, value in percentages.items()},
                **data,
            },
        )

    return {
        "analysis": analysis,
        "interventions": interventions,
        "known": known,
        "selected": selected,
        "category": category_grant,
        "make_item": make_item,
        "kwargs": url_kwargs,
        "bulk_url": bulk_url,
        "single_url": reverse("analysis-allocate-cost_type-grant-suggest", kwargs=url_kwargs),
        "preview": preview,
        "save": save,
    }


def suggested_inputs(response):
    """Names of the allocation inputs rendered with the suggestion highlight."""
    html = BeautifulSoup(response.content, "html.parser")
    return [
        field["name"]
        for field in html.select("input.bulk-allocation-input")
        if SUGGESTED_CLASS in field["class"]
    ]


@pytest.mark.django_db
class TestProgramCostSuggestions:
    def test_no_fallback_to_other_categories(self, program_cost_case):
        case = program_cost_case
        category = CategoryFactory()
        target = case["make_item"](20, category=category)
        case["analysis"].ensure_cost_type_category_objects()
        target_category = case["analysis"].cost_type_category_grants.get(
            cost_type_category__category=category, grant=target.grant_code
        )
        suggestion = target_category.program_cost_suggestion(excluded_config_ids=[target.config.pk])
        assert suggestion["denominator"] == 0
        assert suggestion["allocations"] is None

    def test_preview_uses_whole_category_and_never_saves(self, program_cost_case):
        case = program_cost_case
        response = case["preview"](case["selected"], site_code="hidden-site")
        assert response.status_code == 200
        assert response["Cache-Control"] == "no-store"
        assert response.json()["allocations"] == {str(i.pk): "50.00" for i in case["interventions"]}
        for intervention in case["interventions"]:
            assert intervention.display_name() in response.json()["html"]
        assert not CostLineItemInterventionAllocation.objects.filter(
            cli_config__in=[item.config for item in case["selected"]]
        ).exists()
        # A subsequent request gets fresh saved data, with no stale preview cache.
        case["known"][0].config.allocations.filter(intervention_instance=case["interventions"][0]).update(
            allocation=20
        )
        assert case["preview"](case["selected"]).json()["allocations"] == {
            str(case["interventions"][0].pk): "10.00",
            str(case["interventions"][1].pk): "50.00",
        }

    def test_preview_queries_do_not_grow_with_unlabelled_interventions(self, program_cost_case):
        case = program_cost_case
        with CaptureQueriesContext(connection) as before:
            case["preview"](case["selected"])
        for _ in range(4):
            add_intervention(case["analysis"])
        with CaptureQueriesContext(connection) as after:
            response = case["preview"](case["selected"])
        assert len(response.json()["allocations"]) == 6
        assert len(after) == len(before)
        assert sum('"website_intervention"' in query["sql"] for query in after) <= 1

    def test_normal_panel_waits_for_suggest_action(self, program_cost_case, client_with_admin):
        case = program_cost_case
        response = client_with_admin.get(case["bulk_url"], {"config_ids": case["selected"][0].config.pk})
        assert response.status_code == 200
        assert not response.context["show_suggestion"]
        assert b"Suggest Allocation" in response.content
        assert b"Suggested Allocation Calculations" not in response.content
        assert suggested_inputs(response) == []

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

    def test_single_item_uses_distinct_percentages_and_calculation_amounts(
        self, program_cost_case, client_with_admin
    ):
        case = program_cost_case
        case["known"][1].total_cost = 1000
        case["known"][1].save()
        target = case["selected"][0]
        CostLineItemInterventionAllocationFactory(
            cli_config=target.config, intervention_instance=case["interventions"][0], allocation=100
        )
        response = client_with_admin.get(case["single_url"], {"config_ids": target.config.pk})
        form = response.context["form"]
        assert [form[f"allocation_{i.pk}"].value() for i in case["interventions"]] == ["9.09", "90.91"]
        html = BeautifulSoup(response.content, "html.parser")
        calculations = html.select(".program-cost-suggestion__calculation")
        assert [c.select_one(".program-cost-suggestion__result strong").text for c in calculations] == [
            "9.09%",
            "90.91%",
        ]
        weighted = [c.select_one(".program-cost-suggestion__cost strong").text for c in calculations]
        assert weighted[0] != weighted[1]
        assert "100" in weighted[0] and "1,000" in weighted[1]
        assert all(
            "1,100" in c.select_one(".program-cost-suggestion__cost--unweighted strong").text
            for c in calculations
        )
        assert suggested_inputs(response) == [f"allocation_{i.pk}" for i in case["interventions"]]
        assert list(target.config.allocations.values_list("allocation", flat=True)) == [100]

    def test_accept_re_renders_saved_values_without_a_new_suggestion(
        self, program_cost_case, client_with_admin
    ):
        case = program_cost_case
        target = case["selected"][0]
        percentages = dict(zip([i.pk for i in case["interventions"]], ["9.09", "90.91"]))
        response = case["save"]([target], percentages, url=case["single_url"])
        assert response.status_code == 200
        assert not response.context["form"].errors
        assert response.context["panel_commands"]
        assert not response.context["show_suggestion"]
        assert "suggestion" not in response.context
        assert suggested_inputs(response) == []
        form = response.context["form"]
        assert [form[f"allocation_{i.pk}"].value() for i in case["interventions"]] == [
            Decimal("9.09"),
            Decimal("90.91"),
        ]
        assert dict(target.config.allocations.values_list("intervention_instance_id", "allocation")) == {
            key: Decimal(value) for key, value in percentages.items()
        }

    @pytest.mark.parametrize("refund", [-20, -100])
    def test_unavailable_single_preview_preserves_existing_values(
        self, program_cost_case, client_with_admin, refund
    ):
        case = program_cost_case
        case["known"][1].total_cost = refund
        case["known"][1].save()
        target = case["selected"][0]
        for intervention, allocation in zip(case["interventions"], [60, 40]):
            CostLineItemInterventionAllocationFactory(
                cli_config=target.config, intervention_instance=intervention, allocation=allocation
            )
        response = client_with_admin.get(case["single_url"], {"config_ids": target.config.pk})
        assert response.context["suggestion"]["allocations"] is None
        form = response.context["form"]
        assert [form[f"allocation_{i.pk}"].value() for i in case["interventions"]] == [60, 40]
        warning = (
            b"Due to the refund allocations the application was unable to produce a suggested allocation"
            if refund == -20
            else b"Unable to calculate"
        )
        assert warning in response.content
        assert suggested_inputs(response) == []
        preview = case["preview"]([target])
        assert preview.json()["allocations"] is None
        assert warning.decode() in preview.json()["html"]

    @pytest.mark.parametrize(
        "first_index, first_expected, second_expected",
        [
            (0, ["0.20", "99.80"], ["0.25", "99.75"]),
            (1, ["99.50", "0.50"], ["97.55", "2.45"]),
        ],
    )
    def test_saved_suggestions_affect_next_request(
        self, program_cost_case, first_index, first_expected, second_expected
    ):
        case = program_cost_case
        case["known"][1].total_cost = 1000
        case["known"][1].save()
        for index, item in enumerate(case["selected"]):
            item.total_cost = [200000, 50000][index]
            item.save()
            for j, intervention in enumerate(case["interventions"]):
                CostLineItemInterventionAllocationFactory(
                    cli_config=item.config,
                    intervention_instance=intervention,
                    allocation=100 if index == j else 0,
                )

        def preview(items):
            return case["preview"](items).json()["allocations"]

        def save(item, percentages):
            response = case["save"]([item], percentages)
            assert not response.context["form"].errors
            assert response.context["panel_commands"]
            assert dict(item.config.allocations.values_list("intervention_instance_id", "allocation")) == {
                int(key): Decimal(value) for key, value in percentages.items()
            }

        assert preview(case["selected"]) == dict(
            zip([str(i.pk) for i in case["interventions"]], ["9.09", "90.91"])
        )
        first, second = case["selected"][first_index], case["selected"][1 - first_index]
        first_preview = preview([first])
        assert list(first_preview.values()) == first_expected
        before_save = preview([second])
        save(first, first_preview)
        second_preview = preview([second])
        assert second_preview != before_save
        assert list(second_preview.values()) == second_expected
        save(second, second_preview)

    def test_rounded_sixths_can_be_saved_to_all_selected_items(self, program_cost_case):
        case = program_cost_case
        for index in range(2, 6):
            case["interventions"].append(add_intervention(case["analysis"]))
            case["make_item"](100, [100 if i == index else 0 for i in range(index + 1)])
        percentages = case["preview"](case["selected"]).json()["allocations"]
        assert list(percentages.values()) == ["16.66"] * 6
        response = case["save"](case["selected"], percentages)
        assert not response.context["form"].errors
        for item in case["selected"]:
            assert (
                list(item.config.allocations.values_list("allocation", flat=True)) == [Decimal("16.66")] * 6
            )

    @pytest.mark.parametrize("single", [False, True])
    def test_save_replaces_selected_rows_and_cleared_field_is_zero(self, program_cost_case, single):
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
        response = case["save"](
            selected,
            {case["interventions"][0].pk: "25", case["interventions"][1].pk: ""},
            url=case["single_url"] if single else case["bulk_url"],
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

    def test_invalid_total_preserves_edits_and_saved_allocations(self, program_cost_case):
        case = program_cost_case
        response = case["save"](case["selected"], {i.pk: "60" for i in case["interventions"]})
        assert response.status_code == 200
        assert b"Total allocation cannot exceed 100%" in response.content
        assert response.context["suggestion"]["allocations"] == {i.pk: "50.00" for i in case["interventions"]}
        for intervention in case["interventions"]:
            assert response.context["form"][f"allocation_{intervention.pk}"].value() == "60"
        assert not case["selected"][0].config.allocations.exists()

    @pytest.mark.parametrize("invalid_value", [None, "?"])
    def test_missing_or_invalid_fields_do_not_clear_allocations(self, program_cost_case, invalid_value):
        case = program_cost_case
        percentages = {case["interventions"][0].pk: "25"}
        if invalid_value is not None:
            percentages[case["interventions"][1].pk] = invalid_value
        response = case["save"]([case["known"][0]], percentages, suggestion_requested="False")
        assert response.status_code == 200
        assert response.context["form"].errors
        assert not response.context["show_suggestion"]
        assert sorted(case["known"][0].config.allocations.values_list("allocation", flat=True)) == [0, 100]

    def test_no_denominator_is_unavailable_but_zero_is_a_valid_suggestion(self, program_cost_case):
        case = program_cost_case
        case["analysis"].cost_line_items.update(total_cost=0)
        response = case["preview"](case["selected"])
        assert response.json()["allocations"] is None
        assert "Unable to calculate" in response.json()["html"]
        case["analysis"].cost_line_items.update(total_cost=100)
        CostLineItemInterventionAllocation.objects.filter(
            cli_config__cost_line_item__analysis=case["analysis"]
        ).update(allocation=0)
        response = case["preview"](case["selected"])
        assert response.json()["allocations"] == {str(i.pk): "0.00" for i in case["interventions"]}
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
        assert case["preview"]([foreign_config.cost_line_item]).status_code == 404
        support = CostType.objects.get(type=Support.id)
        case["selected"][0].config.cost_type = support
        case["selected"][0].config.save()
        url = reverse(
            "analysis-allocate-cost_type-grant-bulk",
            kwargs={**case["kwargs"], "cost_type_pk": support.pk},
        )
        assert case["preview"](case["selected"][:1], url=url).status_code == 404
        response = client_with_admin.get(url, {"config_ids": case["selected"][0].config.pk})
        assert b"program-cost-suggest-button" not in response.content

    def test_suggestions_require_analysis_permission(self, program_cost_case, client, a_user):
        case = program_cost_case
        client.force_login(a_user)
        assert case["preview"](case["selected"], client=client).status_code == 403

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

    def test_question_mark_still_shows_legacy_calculator_for_support_costs(
        self, program_cost_case, client_with_admin
    ):
        # The legacy grant-wide calculator remains the help path for Support and Indirect costs
        # (the Support table hides its markup, so the values are checked on the context).
        case = program_cost_case
        for item in case["selected"]:
            for intervention in case["interventions"]:
                CostLineItemInterventionAllocationFactory(
                    cli_config=item.config, intervention_instance=intervention, allocation=50
                )
        support = CostType.objects.get(type=Support.id)
        case["make_item"](100, [100, 0], cost_type=support)
        case["make_item"](100, [0, 100], cost_type=support)
        case["make_item"](60, cost_type=support)
        case["make_item"](40, cost_type=support)
        helped = case["make_item"](20, cost_type=support, category=CategoryFactory())
        case["analysis"].ensure_cost_type_category_objects()
        case["analysis"].cost_type_categories.update(confirmed=True)
        response = client_with_admin.post(
            reverse(
                "analysis-allocate-cost_type-grant", kwargs={**case["kwargs"], "cost_type_pk": support.pk}
            ),
            {
                f"cost_line_item_allocation_{helped.pk}_{intervention.pk}": "?"
                for intervention in case["interventions"]
            },
        )
        assert response.status_code == 200
        assert round(response.context["item_costs"], 4) == Decimal(200)
        assert response.context["item_totals"] == Decimal(120)
        assert response.context["all_errors_suggest"] == "166.67%"
        assert [
            grant.cost_type_category.category_id
            for grant in response.context["cost_type_category_grants"]
            if grant.show_allocation_calculator
        ] == [helped.config.category_id]
