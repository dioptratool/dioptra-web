from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.conf import settings as django_settings
from django.urls import reverse

from website.models import Analysis
from website.templatetags.analysis import allocation_error_messages
from website.tests.factories import InterventionFactory
from website.views.mixins import AllocateMixin


@pytest.mark.django_db
class TestAllocateCostFormSubmissions:
    def test_all_good_data(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        a_user,
        client_with_admin,
    ):
        # Categories must be confirmed or `Allocate.dependencies_met` is False and
        # `AnalysisStepMixin.dispatch` redirects away without saving anything.
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        intervention_count = analysis.interventioninstance_set.count()
        data = {}
        for cli in analysis.cost_line_items.all():
            for intervention_instance in analysis.interventioninstance_set.all():
                data[f"cost_line_item_allocation_{cli.id}_{intervention_instance.id}"] = "2.00"

        assert data, "fixture produced no cost line items to allocate"

        cost_type_category_grant = analysis.cost_type_category_grants.first()
        grant = cost_type_category_grant.grant
        cost_type = cost_type_category_grant.cost_type_category.cost_type
        url = reverse(
            "analysis-allocate-cost_type-grant",
            kwargs={
                "pk": analysis.pk,
                "cost_type_pk": cost_type.pk,
                "grant": grant,
            },
        )

        response = client_with_admin.post(url, data=data)

        # A successful save redirects back to the same page; the step guard would
        # redirect to the analysis overview instead.
        assert response.status_code == 302
        assert response.url == url

        updated_analysis = Analysis.objects.get(pk=analysis.pk)
        for cli in updated_analysis.cost_line_items.all():
            allocations = cli.config.allocations.all()
            assert allocations.count() == intervention_count
            for allocation in allocations:
                assert allocation.allocation == Decimal("2.00")

    def test_partial_save_renders_saved_allocations_and_preserves_them_on_retry(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        valid_item, invalid_item = analysis.cost_line_items.order_by("pk")
        # Keep both rows in the same category form, as in a real submission.
        invalid_item.config.category = valid_item.config.category
        invalid_item.config.save()
        analysis.ensure_cost_type_category_objects()
        interventions = list(analysis.interventioninstance_set.all())
        data = {}
        for item in (valid_item, invalid_item):
            for intervention in interventions:
                item.set_allocation_for_intervention(intervention, Decimal("10.00"))
                data[f"cost_line_item_allocation_{item.pk}_{intervention.pk}"] = (
                    "25.00" if item == valid_item else "invalid"
                )

        url = reverse(
            "analysis-allocate-cost_type-grant",
            kwargs={
                "pk": analysis.pk,
                "cost_type_pk": valid_item.config.cost_type.pk,
                "grant": valid_item.grant_code,
            },
        )
        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        assert set(response.context["errors"]) == {invalid_item.pk}
        assert response.context["cost_line_items_count"] == 2
        html = BeautifulSoup(response.content, "html.parser")
        retry_data = {}
        for intervention in interventions:
            saved = valid_item.config.allocations.get(intervention_instance=intervention)
            assert saved.allocation == Decimal("25.00")
            field_name = f"cost_line_item_allocation_{valid_item.pk}_{intervention.pk}"
            field = html.find("input", attrs={"name": field_name})
            assert field is not None
            assert Decimal(field["value"]) == saved.allocation
            retry_data[field_name] = field["value"]
            retry_data[f"cost_line_item_allocation_{invalid_item.pk}_{intervention.pk}"] = "30.00"

        response = client_with_admin.post(url, data=retry_data)

        assert response.status_code == 302
        assert response.url == url
        for item, expected in ((valid_item, "25.00"), (invalid_item, "30.00")):
            for intervention in interventions:
                saved = item.config.allocations.get(intervention_instance=intervention)
                assert saved.allocation == Decimal(expected)

    def test_all_good_data_with_maximum_interventions(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        a_user,
        client_with_admin,
    ):
        analysis_wf = analysis_workflow_with_confirmed_categories_cost_line_item
        analysis = analysis_wf.analysis

        while analysis.interventioninstance_set.count() < django_settings.MAX_ANALYSIS_INTERVENTIONS:
            analysis.add_intervention(
                InterventionFactory(
                    output_metrics=[
                        "NumberOfTeacherDaysOfTraining",
                    ],
                ),
                parameters={
                    "number_of_teachers": 1,
                    "number_of_days_of_training": 1,
                },
            )
        analysis.ensure_cost_type_category_objects()

        data = {}
        for cli in analysis.cost_line_items.all():
            for intervention_instance in analysis.interventioninstance_set.all():
                data[f"cost_line_item_allocation_{cli.id}_{intervention_instance.id}"] = "2.00"

        cost_type_category_grant = analysis.cost_type_category_grants.first()
        grant = cost_type_category_grant.grant
        cost_type = cost_type_category_grant.cost_type_category.cost_type

        response = client_with_admin.post(
            reverse(
                "analysis-allocate-cost_type-grant",
                kwargs={
                    "pk": analysis.pk,
                    "cost_type_pk": cost_type.pk,
                    "grant": grant,
                },
            ),
            data=data,
            follow=True,
        )

        assert response.status_code == 200

        updated_analysis = Analysis.objects.get(pk=analysis.pk)
        for cli in updated_analysis.cost_line_items.all():
            allocations = cli.config.allocations.all()
            assert allocations.count() == django_settings.MAX_ANALYSIS_INTERVENTIONS
            for allocation in allocations:
                assert allocation.allocation == Decimal("2.00")


class TestAllocationErrorMessages:
    """
    `_validate_data` records both a per-intervention message and an "all" row-total
    message for an out-of-range allocation. The template must render a message, not
    the raw error dict.
    """

    def test_negative_allocation_shows_only_the_field_message(self):
        errors = {
            7: {
                4: "Invalid allocation (0-100)",
                "all": "Invalid allocation total. Cost line item Allocation must be between 0 and 100",
            }
        }
        assert allocation_error_messages(errors, 7) == ["Invalid allocation (0-100)"]

    def test_row_total_message_shows_when_it_is_the_only_error(self):
        errors = {7: {"all": "Invalid allocation total."}}
        assert allocation_error_messages(errors, 7) == ["Invalid allocation total."]

    def test_repeated_message_across_interventions_is_shown_once(self):
        errors = {7: {4: "Not a number", 5: "Not a number"}}
        assert allocation_error_messages(errors, 7) == ["Not a number"]

    def test_distinct_messages_are_all_kept(self):
        errors = {7: {4: "Not a number", 5: "Invalid allocation (0-100)"}}
        assert allocation_error_messages(errors, 7) == [
            "Not a number",
            "Invalid allocation (0-100)",
        ]

    def test_row_without_errors_renders_nothing(self):
        assert allocation_error_messages({7: {4: "Not a number"}}, 99) == []
        assert allocation_error_messages(None, 7) == []

    def test_plain_string_errors_still_render(self):
        # The sub-component step stores one string per row rather than a dict.
        assert allocation_error_messages({7: "Not a number"}, 7) == ["Not a number"]


@pytest.mark.django_db
class TestAllocateNegativeAllocationRendering:
    def test_negative_allocation_renders_message_not_dict(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        a_user,
        client_with_admin,
    ):
        # Categories must be confirmed or `Allocate.dependencies_met` is False and
        # `AnalysisStepMixin.dispatch` redirects away before the page renders.
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        cost_type_category_grant = analysis.cost_type_category_grants.first()
        grant = cost_type_category_grant.grant
        cost_type = cost_type_category_grant.cost_type_category.cost_type

        data = {}
        for cli in analysis.cost_line_items.all():
            for intervention_instance in analysis.interventioninstance_set.all():
                data[f"cost_line_item_allocation_{cli.id}_{intervention_instance.id}"] = "-5"

        assert data, "fixture produced no cost line items to allocate"

        response = client_with_admin.post(
            reverse(
                "analysis-allocate-cost_type-grant",
                kwargs={
                    "pk": analysis.pk,
                    "cost_type_pk": cost_type.pk,
                    "grant": grant,
                },
            ),
            data=data,
        )

        # Not `follow=True`: the error path re-renders in place, so a redirect here
        # would mean the step guard bounced us and the assertions below are vacuous.
        assert response.status_code == 200
        content = response.content.decode()
        assert "Invalid allocation (0-100)" in content
        # The raw dict repr leaked through before this was fixed.
        assert "&#x27;all&#x27;:" not in content
        assert "'all':" not in content
        assert "Invalid allocation total." not in content


class TestValidateAllocationTotal:
    """
    The row-total check must use the final total, not a running total taken
    after each intervention.
    """

    def validate(self, *allocations):
        data = {7: {intervention_id: value for intervention_id, value in enumerate(allocations)}}
        return AllocateMixin()._validate_data(data)[1]

    def test_valid_row_has_no_errors(self):
        assert self.validate("60", "40") == {}

    def test_total_over_100_is_a_row_error(self):
        assert self.validate("60", "60")[7] == {
            "all": "Invalid allocation total. Cost line item Allocation must be between 0 and 100"
        }

    def test_out_of_range_values_that_net_to_a_valid_total_are_not_a_row_error(self):
        # A running total passes 100 after the first value; the final total is 100.
        errors = self.validate("120", "-20")
        assert errors[7] == {0: "Invalid allocation (0-100)", 1: "Invalid allocation (0-100)"}

    def test_blank_values_do_not_count_toward_the_total(self):
        assert self.validate("60", None, "40") == {}
