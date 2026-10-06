"""
Feature 91 -- edit entry points on the step pages (spec sections 3-4, 13-14).
"""

import re
from decimal import Decimal

import pytest
from django.urls import NoReverseMatch, reverse

from website.models import CostType, Transaction
from website.models.cost_type import Indirect, ProgramCost, Support
from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemFactory,
    SubcomponentCostAnalysisFactory,
)
from .helpers import group, item_defaults, item_for, make_analysis, tx


@pytest.fixture
def analysis(defaults):
    return make_analysis()


@pytest.fixture
def transaction_analysis(analysis):
    """Program item A (S1: t1, t2) and item B (S2: t3), plus a Support item and an Indirect item."""
    tx(analysis)
    tx(analysis)
    tx(analysis, site_code="S2")
    tx(analysis, site_code="S3", account_code="7000")
    tx(analysis, site_code="S4", account_code="9000")
    group(analysis)
    support = CostType.objects.get(type=Support.id)
    indirect = CostType.objects.get(type=Indirect.id)
    for site, cost_type in (("S3", support), ("S4", indirect)):
        config = item_for(analysis, site_code=site).config
        config.cost_type = cost_type
        config.save()
    analysis.ensure_cost_type_category_objects()
    analysis.cost_type_categories.update(confirmed=True)
    return analysis


def allocate_everything(analysis):
    """Complete every Program and Support allocation so the later Allocate sub-steps are reachable."""
    for cost_line_item in analysis.cost_line_items.cost_type_category_items():
        for instance in analysis.interventioninstance_set.all():
            cost_line_item.set_allocation_for_intervention(instance, Decimal("100"))


def categorize_url(analysis, cost_type):
    return reverse("analysis-categorize-cost_type", kwargs={"pk": analysis.pk, "cost_type_pk": cost_type.pk})


def allocate_url(analysis, cost_type, grant="G1"):
    return reverse(
        "analysis-allocate-cost_type-grant",
        kwargs={"pk": analysis.pk, "cost_type_pk": cost_type.pk, "grant": grant},
    )


def transactions_url(analysis, step):
    return reverse("analysis-correct-transactions", kwargs={"pk": analysis.pk, "step": step})


def cost_items_url(analysis, step):
    return reverse("analysis-correct-cost-items", kwargs={"pk": analysis.pk, "step": step})


@pytest.mark.django_db
class TestConfirmCategories:
    def test_row_edit_opens_the_cost_item_panel_with_the_item_id_and_page_cost_type(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        program = CostType.objects.get(type=ProgramCost.id)
        a = item_for(analysis, site_code="S1")

        content = client_with_admin.get(categorize_url(analysis, program)).content.decode()

        expected = (
            f'{cost_items_url(analysis, "categorize")}?cost_type={program.pk}&amp;cost_line_item_id={a.pk}'
        )
        assert expected in content
        assert 'data-panels-reload-on="saved"' in content
        # The old placeholder passed the cost item pk as a config id (K-05); it is gone.
        assert "config_ids=" not in content
        assert "Assign Selected Items" not in content

    def test_bulk_edit_button_carries_the_selection_settings(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        program = CostType.objects.get(type=ProgramCost.id)

        content = client_with_admin.get(categorize_url(analysis, program)).content.decode()

        button = re.search(r'<button[^>]*class="correction-bulk-edit[^"]*"[^>]*>', content).group(0)
        assert (
            f'data-selection-url="{reverse("analysis-correction-selection", kwargs={"pk": analysis.pk})}"'
            in button
        )
        assert 'data-selection-kind="transactions"' in button
        assert 'data-selection-step="categorize"' in button
        assert f'data-cost-type="{program.pk}"' in button
        assert ">Edit<" in content
        assert f'data-cost-line-item-id="{item_for(analysis, site_code="S1").pk}"' in content

    def test_budget_analysis_selects_cost_items(self, analysis, client_with_admin):
        row = CostLineItemFactory(analysis=analysis, total_cost=Decimal("100"), **item_defaults())
        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()

        content = client_with_admin.get(categorize_url(analysis, row.config.cost_type)).content.decode()

        assert 'data-selection-kind="cost_items"' in content

    def test_transaction_rows_link_to_the_transaction_panel(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        program = CostType.objects.get(type=ProgramCost.id)
        a = item_for(analysis, site_code="S1")
        page = client_with_admin.get(categorize_url(analysis, program)).content.decode()
        href = re.search(r'data-transactions-href="([^"]+)"', page).group(1).replace("&amp;", "&")
        assert "bulk_select=1" in href

        content = client_with_admin.get(href).content.decode()

        t1 = a.transactions.order_by("id").first()
        expected = (
            f'{transactions_url(analysis, "categorize")}?cost_type={program.pk}&amp;transaction_id={t1.pk}'
        )
        assert expected in content
        assert 'data-panels-reload-on="saved"' in content
        assert 'class="transaction-checkbox"' in content

    def test_old_bulk_panel_is_gone(self, transaction_analysis):
        analysis = transaction_analysis
        with pytest.raises(NoReverseMatch):
            reverse("analysis-categorize-cost_type-bulk", kwargs={"pk": analysis.pk, "cost_type_pk": 1})


@pytest.mark.django_db
class TestAllocate:
    def test_program_table_has_set_allocation_and_edit_and_the_actions_menu(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        program = CostType.objects.get(type=ProgramCost.id)
        a = item_for(analysis, site_code="S1")

        content = client_with_admin.get(allocate_url(analysis, program)).content.decode()

        assert "Set Allocation" in content
        assert 'class="correction-bulk-edit' in content
        assert 'data-selection-step="allocate"' in content
        assert f'{cost_items_url(analysis, "allocate")}?cost_line_item_id={a.pk}' in content
        assert "Edit Cost Item" in content
        assert "Add note" in content
        assert "transaction_edit_url=" in content

    def test_indirect_table_gets_the_same_entry_points_without_set_allocation(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        allocate_everything(analysis)
        indirect = CostType.objects.get(type=Indirect.id)
        row = item_for(analysis, site_code="S4")

        response = client_with_admin.get(allocate_url(analysis, indirect))
        content = response.content.decode()

        assert response.status_code == 200

        assert "Set Allocation" not in content
        assert "Select All" in content
        assert 'class="correction-bulk-edit' in content
        assert 'class="bulk-checkbox"' in content
        assert ">Actions<" in content
        assert f'{cost_items_url(analysis, "allocate")}?cost_line_item_id={row.pk}' in content
        assert "Add note" in content
        assert 'name="note"' in content  # the note edit row is no longer gated
        assert "transaction_edit_url=" in content

    def test_lump_sum_rows_have_no_edit_actions(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        lump = CostLineItemFactory(
            analysis=analysis,
            is_special_lump_sum=True,
            grant_code="G1",
            budget_line_description="Somewhere else",
            total_cost=Decimal("5"),
        )
        CostLineItemConfigFactory(cost_line_item=lump, cost_type=None, category=None)
        allocate_everything(analysis)
        url = reverse("analysis-allocate-supporting-costs", kwargs={"pk": analysis.pk, "grant": "G1"})

        response = client_with_admin.get(url)
        content = response.content.decode()

        assert response.status_code == 200

        assert "Somewhere else" in content
        assert "Add note" in content
        assert "Edit Cost Item" not in content
        assert "cost_line_item_id=" not in content
        assert "transaction_edit_url=" not in content
        assert "correction-bulk-edit" not in content

    def test_unsaved_allocation_prompt_is_a_confirmation_panel(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        program = CostType.objects.get(type=ProgramCost.id)
        prompt_url = reverse("analysis-correction-unsaved-prompt", kwargs={"pk": analysis.pk})

        content = client_with_admin.get(allocate_url(analysis, program)).content.decode()

        assert f'data-unsaved-prompt-url="{prompt_url}"' in content
        assert "<dialog" not in content

        panel = client_with_admin.get(prompt_url)
        panel_content = panel.content.decode()

        assert panel.status_code == 200
        assert "Save or discard your allocation changes before editing" in panel_content
        assert 'data-correction-choice="save"' in panel_content
        assert 'data-correction-choice="discard"' in panel_content
        assert 'data-panels-action="reject-close"' in panel_content

    def test_confirm_categories_has_no_unsaved_prompt(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        program = CostType.objects.get(type=ProgramCost.id)

        content = client_with_admin.get(categorize_url(analysis, program)).content.decode()

        assert "data-unsaved-prompt-url" not in content

    def test_sub_component_table_has_no_correction_entry_points(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        program = CostType.objects.get(type=ProgramCost.id)
        SubcomponentCostAnalysisFactory(analysis=analysis)
        for cost_line_item in analysis.cost_line_items.all():
            for instance in analysis.interventioninstance_set.all():
                cost_line_item.set_allocation_for_intervention(instance, Decimal("100"))
        instance = analysis.interventioninstance_set.first()
        url = reverse(
            "analysis-allocate-subcomponents-intervention-grant",
            kwargs={"pk": analysis.pk, "intervention_instance_pk": instance.pk, "grant": "G1"},
        )

        response = client_with_admin.get(url, follow=True)
        content = response.content.decode()

        assert response.status_code == 200
        assert "Sub-Component" in content
        assert "cost_line_item_id=" not in content
        assert "transaction_edit_url=" not in content
        assert "bulk_select=1" not in content
        assert "correction-bulk-edit" not in content
        assert "Edit Cost Item" not in content
        # The Actions column on this table carries the note button and nothing else.
        assert "Add note" in content
        assert 'class="bulk-checkbox"' in content  # Set Allocation's own selection stays


@pytest.mark.django_db
class TestSelectionExpansion:
    def test_whole_cost_items_expand_to_every_transaction_they_contain(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a = item_for(analysis, site_code="S1")
        b = item_for(analysis, site_code="S2")
        (t3,) = list(b.transactions.all())

        response = client_with_admin.post(
            reverse("analysis-correction-selection", kwargs={"pk": analysis.pk}),
            data={
                "kind": "transactions",
                "step": "categorize",
                "cost_line_item_ids": [str(a.pk)],
                "ids": [str(t3.pk)],
            },
        )

        assert response.status_code == 200
        assert response.json()["count"] == 3
        panel = client_with_admin.get(response.json()["url"])
        assert panel.status_code == 200
        assert "Edit Transactions" in panel.content.decode()

    def test_cost_items_of_another_analysis_expand_to_nothing(
        self, transaction_analysis, client_with_admin, defaults
    ):
        analysis = transaction_analysis
        other = make_analysis()
        foreign = tx(other)
        group(other)

        response = client_with_admin.post(
            reverse("analysis-correction-selection", kwargs={"pk": analysis.pk}),
            data={
                "kind": "transactions",
                "step": "categorize",
                "cost_line_item_ids": [str(foreign.cost_line_item_id)],
            },
        )

        assert response.status_code == 400
        assert Transaction.objects.filter(id=foreign.id, site_code="S1").exists()
