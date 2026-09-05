"""
Feature 91 -- edit panels, selection transport and the two-phase save (spec sections 3-5, 8-10).
"""

import datetime
import html
import json
import re
from decimal import Decimal

import pytest
from app_log.models import AppLogEntry
from django.contrib.auth import get_user_model
from django.urls import reverse

from website.models import CostLineItem, CostType, FieldLabelOverrides, Transaction
from website.models.cost_type import Support
from website.tests.factories import (
    AccountCodeDescriptionFactory,
    CostLineItemFactory,
    UserFactory,
)
from .helpers import allocate, allocations_of, group, item_defaults, item_for, make_analysis, tx

User = get_user_model()


def transactions_url(analysis, step="categorize", **query):
    url = reverse("analysis-correct-transactions", kwargs={"pk": analysis.pk, "step": step})
    return _with_query(url, query)


def cost_items_url(analysis, step="categorize", **query):
    url = reverse("analysis-correct-cost-items", kwargs={"pk": analysis.pk, "step": step})
    return _with_query(url, query)


def selection_url(analysis):
    return reverse("analysis-correction-selection", kwargs={"pk": analysis.pk})


def _with_query(url, query):
    if not query:
        return url
    return url + "?" + "&".join(f"{key}={value}" for key, value in query.items())


def select(client, analysis, kind, ids, step="categorize", **extra):
    """Create a server-side selection the way the bulk Edit button does; returns the panel URL."""
    data = {"kind": kind, "step": step, "ids": [str(i) for i in ids], **extra}
    response = client.post(selection_url(analysis), data=data)
    assert response.status_code == 200, response.content
    return response.json()["url"]


def correction_entries():
    """Only the entries a correction writes; creating fixtures logs entries of its own."""
    return AppLogEntry.objects.filter(action__in=["Transactions Corrected", "Cost Items Corrected"])


def fingerprint_in(content):
    match = re.search(r'name="confirm_fingerprint" value="([0-9a-f]+)"', content)
    return match.group(1) if match else None


def field_value(content, name):
    match = re.search(rf'name="{name}"[^>]*\svalue="([^"]*)"', content)
    return match.group(1) if match else None


def tageditor_options(content, name):
    """The `data-tageditor` options JSON of the Tagify select rendered for ``name``."""
    match = re.search(rf'<input[^>]*name="{name}"[^>]*data-tageditor="([^"]*)"', content)
    assert match, f"no Tagify input named {name}"
    return json.loads(html.unescape(match.group(1)))


def selected_option(content, name):
    select = re.search(rf'<select[^>]*name="{name}"[^>]*>(.*?)</select>', content, re.S)
    assert select, f"no select named {name}"
    match = re.search(r'<option value="([^"]*)" selected', select.group(1))
    return match.group(1) if match else None


@pytest.fixture
def analysis(defaults):
    return make_analysis()


@pytest.fixture
def transaction_analysis(analysis):
    """Item A (site S1) with t1 + t2, item B (site S2) with t3."""
    tx(analysis, date=datetime.date(2016, 3, 1))
    tx(analysis, date=datetime.date(2016, 3, 1))
    tx(analysis, site_code="S2", budget_line_description="Wages", date=datetime.date(2016, 4, 1))
    analysis.start_date = datetime.date(2016, 1, 1)
    analysis.end_date = datetime.date(2016, 12, 31)
    analysis.save()
    group(analysis)
    return analysis


def items(analysis):
    a = item_for(analysis, site_code="S1")
    b = item_for(analysis, site_code="S2")
    t1, t2 = list(a.transactions.order_by("id"))
    (t3,) = list(b.transactions.all())
    return a, b, t1, t2, t3


@pytest.mark.django_db
class TestTransactionPanelForm:
    def test_single_transaction_prefills_current_values_on_confirm_categories(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.get(transactions_url(analysis, transaction_id=t1.id))
        content = response.content.decode()

        assert response.status_code == 200
        assert "Edit Transaction" in content
        assert field_value(content, "site_code") == "S1"
        assert field_value(content, "sector_code") == "SEC"
        assert field_value(content, "account_code") == "4100"
        assert field_value(content, "description") == "Salaries"  # the parent item's description
        assert "Budget Line Description" in content
        assert "Applies to the cost item these transactions belong to" in content
        assert field_value(content, "transaction_description") == "Payroll"
        assert field_value(content, "date") == "01-Mar-2016"
        assert field_value(content, "amount") == "100.0000"
        assert field_value(content, "grant_code") == "G1"
        assert selected_option(content, "cost_type") == str(a.config.cost_type_id)
        assert selected_option(content, "category") == str(a.config.category_id)
        # No custom field is populated, so none is offered.
        assert "dummy_field" not in content
        assert tageditor_options(content, "site_code")["mode"] == "select"
        assert tageditor_options(content, "site_code")["enforceWhitelist"] is True
        assert "tagify.js" in content

    def test_calendar_limits_cover_the_analysis_range(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        analysis.end_date = datetime.date(2017, 12, 31)
        analysis.save()
        a, b, t1, t2, t3 = items(analysis)

        content = client_with_admin.get(transactions_url(analysis, transaction_id=t1.id)).content.decode()
        match = re.search(r'name="date"[^>]*data-flatpickr="([^"]*)"', content)
        assert match
        options = json.loads(html.unescape(match.group(1)))

        assert options["dateFormat"] == "d-M-Y"
        assert options["allowInput"] is True
        assert datetime.date.fromisoformat(options["minDate"]) == analysis.start_date
        assert datetime.date.fromisoformat(options["maxDate"]) == analysis.end_date

    def test_allocate_panel_offers_no_cost_type_or_category(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        content = client_with_admin.get(
            transactions_url(analysis, "allocate", transaction_id=t1.id)
        ).content.decode()

        assert 'name="cost_type"' not in content
        assert 'name="category"' not in content
        assert 'name="grant_code"' in content
        assert 'name="date"' in content

    def test_bulk_prefills_uniform_fields_and_marks_the_rest_multiple(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        t3.transaction_description = "Payroll"  # uniform with t1
        t3.save()

        url = select(client_with_admin, analysis, "transactions", [t1.id, t3.id])
        content = client_with_admin.get(url).content.decode()

        assert "Edit Transactions" in content
        assert field_value(content, "grant_code") == "G1"
        assert field_value(content, "transaction_description") == "Payroll"
        assert field_value(content, "sector_code") == "SEC"
        # Site, description and date differ: blank with the grey <multiple values> marker.
        assert field_value(content, "site_code") in (None, "")
        assert tageditor_options(content, "site_code")["placeholder"] == "<multiple values>"
        assert tageditor_options(content, "sector_code")["placeholder"] == ""
        assert re.search(r'name="description"[^>]*placeholder="&lt;multiple values&gt;"', content)
        assert re.search(r'name="date"[^>]*placeholder="&lt;multiple values&gt;"', content)

    def test_bulk_marks_a_tagify_select_multiple_through_its_placeholder(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        t3.grant_code = "G2"
        t3.save()

        url = select(client_with_admin, analysis, "transactions", [t1.id, t3.id])
        content = client_with_admin.get(url).content.decode()

        assert field_value(content, "grant_code") in (None, "")
        assert tageditor_options(content, "grant_code")["placeholder"] == "<multiple values>"

    def test_custom_field_shown_when_populated_or_label_overridden(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        t3.dummy_field_2 = "PRJ-1"
        t3.save()
        overrides = FieldLabelOverrides.get()
        overrides.tr_dummy_field_4 = "Donor"
        overrides.tr_dummy_field_4_overridden = True
        overrides.save()

        content = client_with_admin.get(transactions_url(analysis, transaction_id=t1.id)).content.decode()

        assert 'name="dummy_field_2"' in content
        assert "Transaction Custom Field 2" in content
        assert 'name="dummy_field_4"' in content
        assert "Donor" in content
        assert 'name="dummy_field_1"' not in content
        # Custom fields come last, after Amount.
        assert content.index('name="amount"') < content.index('name="dummy_field_2"')

    def test_account_code_options_come_from_the_data_and_the_lookup(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        AccountCodeDescriptionFactory(account_code="4100", account_description="Salaries")
        AccountCodeDescriptionFactory(
            account_code="9999", account_description="Consultants"
        )  # not in the data
        url = transactions_url(analysis, transaction_id=t1.id)

        content = client_with_admin.get(url).content.decode()

        options = tageditor_options(content, "account_code")
        whitelist = {item["value"]: item["label"] for item in options["whitelist"]}
        assert whitelist["4100"] == "4100 — Salaries"
        assert whitelist["9999"] == "9999 — Consultants"
        assert options["tagTextProp"] == "label"
        assert field_value(content, "account_code") == "4100"

        response = client_with_admin.post(url, data={"account_code": "9999"})

        assert '"operation": "saved"' in response.content.decode()
        t1.refresh_from_db()
        assert t1.account_code == "9999"

    def test_grant_options_are_the_data_and_the_defined_grants(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        analysis.grants = "g1,G2,G3"  # a case variant of a data grant, and grants with no rows yet
        analysis.save()
        t3.grant_code = "G9"  # a data grant the analysis was not defined with (budget-style drift)
        t3.save()
        url = transactions_url(analysis, transaction_id=t1.id)

        content = client_with_admin.get(url).content.decode()

        whitelist = [item["value"] for item in tageditor_options(content, "grant_code")["whitelist"]]
        assert whitelist == ["G1", "G2", "G3", "G9"]

        response = client_with_admin.post(url, data={"grant_code": "G9"})

        assert '"operation": "saved"' in response.content.decode()
        t1.refresh_from_db()
        assert t1.grant_code == "G9"


@pytest.mark.django_db
class TestTransactionPanelSave:
    def test_blank_fields_make_no_change_and_the_save_is_logged(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t1.id),
            data={"site_code": "S2", "sector_code": "", "transaction_description": "", "amount": ""},
        )

        assert response.status_code == 200
        assert '"operation": "saved"' in response.content.decode()
        t1.refresh_from_db()
        assert t1.site_code == "S2"
        assert t1.cost_line_item_id == b.id
        assert t1.sector_code == "SEC"
        assert t1.transaction_description == "Payroll"
        assert t1.amount_in_instance_currency == Decimal("100")
        entry = correction_entries().get()
        assert entry.action == "Transactions Corrected"
        assert entry.obj == analysis
        assert "from Confirm Categories (Site)" in entry.message
        assert "1 existing" in entry.message

    def test_bulk_amount_sets_every_selected_transaction(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        url = select(client_with_admin, analysis, "transactions", [t1.id, t2.id], step="allocate")

        response = client_with_admin.post(url, data={"amount": "12.5"})

        assert response.status_code == 200
        for each in (t1, t2):
            each.refresh_from_db()
            assert each.amount_in_instance_currency == Decimal("12.5")
            assert each.amount_in_source_currency == Decimal("12.5")
        a.refresh_from_db()
        assert a.total_cost == Decimal("25")
        assert "from Allocate Intervention Costs (Amount)" in correction_entries().get().message

    def test_date_outside_the_analysis_range_is_rejected(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t1.id), data={"date": "01-Jan-2017"}
        )

        content = response.content.decode()
        assert response.status_code == 200
        assert "between 01-Jan-2016 and 31-Dec-2016" in content
        assert '"operation": "saved"' not in content
        t1.refresh_from_db()
        assert t1.date == datetime.date(2016, 3, 1)
        assert not correction_entries().exists()

    @pytest.mark.parametrize("value", ["01-Jan-2016", "15-Jun-2016", "31-Dec-2016", "2016-06-15"])
    def test_valid_dates_can_be_saved(self, transaction_analysis, client_with_admin, value):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t1.id), data={"date": value}
        )

        assert '"operation": "saved"' in response.content.decode()
        t1.refresh_from_db()
        date_format = "%Y-%m-%d" if value[4] == "-" else "%d-%b-%Y"
        assert t1.date == datetime.datetime.strptime(value, date_format).date()

    def test_amount_with_more_than_four_decimals_is_rejected(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t1.id), data={"amount": "1.23456"}
        )

        assert "no more than 4 decimal places" in response.content.decode()
        t1.refresh_from_db()
        assert t1.amount_in_instance_currency == Decimal("100")

    def test_grant_outside_the_data_and_the_defined_list_is_rejected(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t1.id), data={"grant_code": "NOPE"}
        )

        assert "Select a valid choice" in response.content.decode()
        t1.refresh_from_db()
        assert t1.grant_code == "G1"

    def test_site_outside_the_data_is_rejected(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t1.id), data={"site_code": "BRAND-NEW"}
        )

        assert "Select a valid choice" in response.content.decode()
        t1.refresh_from_db()
        assert t1.site_code == "S1"
        assert not correction_entries().exists()

    def test_description_from_a_transaction_panel_renames_the_whole_item(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t1.id), data={"description": "Staff pay"}
        )

        assert '"operation": "saved"' in response.content.decode()
        a.refresh_from_db()
        assert a.budget_line_description == "Staff pay"
        assert set(a.transactions.values_list("budget_line_description", flat=True)) == {"Staff pay"}
        t3.refresh_from_db()
        assert t3.budget_line_description == "Wages"
        assert "(Budget Line Description)" in correction_entries().get().message

    def test_cost_type_change_from_confirm_categories_moves_and_unconfirms(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        analysis.cost_type_categories.update(confirmed=True)
        support = CostType.objects.get(type=Support.id)
        url = select(client_with_admin, analysis, "transactions", [t1.id, t2.id])

        response = client_with_admin.post(url, data={"cost_type": str(support.pk)})

        assert '"operation": "saved"' in response.content.decode()
        a.refresh_from_db()
        assert a.config.cost_type == support
        assert allocations_of(a) == []
        assert analysis.cost_type_categories.get(cost_type=support).confirmed is False


@pytest.mark.django_db
class TestConfirmationStep:
    def test_allocation_warning_blocks_until_confirmed(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        allocate(a, "40")
        allocate(b, "60")
        url = transactions_url(analysis, transaction_id=t2.id)

        response = client_with_admin.post(url, data={"site_code": "S2"})
        content = response.content.decode()

        assert response.status_code == 200
        assert "This change will clear allocations" in content
        assert "Continue and clear allocations" in content
        assert 'name="site_code"' in content  # carried as a hidden field
        fingerprint = fingerprint_in(content)
        assert fingerprint
        t2.refresh_from_db()
        assert t2.cost_line_item_id == a.id
        assert allocations_of(a) == [Decimal("40")]
        assert not correction_entries().exists()

        response = client_with_admin.post(
            url, data={"site_code": "S2", "confirm_fingerprint": fingerprint, "stage": "confirm"}
        )

        assert '"operation": "saved"' in response.content.decode()
        t2.refresh_from_db()
        assert t2.cost_line_item_id == b.id
        assert allocations_of(a) == []
        assert allocations_of(b) == []
        assert "cleared allocations on 2 cost items" in correction_entries().get().message

    def test_no_confirmation_when_nothing_would_be_cleared(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t2.id), data={"site_code": "S2"}
        )

        assert '"operation": "saved"' in response.content.decode()
        t2.refresh_from_db()
        assert t2.cost_line_item_id == b.id

    def test_a_stale_fingerprint_reshows_the_confirmation(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        url = transactions_url(analysis, transaction_id=t2.id)
        preview = client_with_admin.post(url, data={"site_code": "S2"})
        assert '"operation": "saved"' in preview.content.decode()  # no allocations yet: applied

        # Undo, then add allocations so the preview the client holds is out of date.
        Transaction.objects.filter(id=t2.id).update(cost_line_item=a, site_code="S1")
        allocate(a, "40")
        response = client_with_admin.post(
            url, data={"site_code": "S2", "confirm_fingerprint": "0000", "stage": "confirm"}
        )
        content = response.content.decode()

        assert "changed since this change was previewed" in content
        assert "This change will clear allocations" in content
        assert '"operation": "saved"' not in content
        t2.refresh_from_db()
        assert t2.cost_line_item_id == a.id

    def test_back_returns_to_the_form_with_the_entered_values(self, transaction_analysis, client_with_admin):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        allocate(a, "40")

        response = client_with_admin.post(
            transactions_url(analysis, transaction_id=t2.id),
            data={"site_code": "S2", "stage": "edit", "confirm_fingerprint": "x"},
        )
        content = response.content.decode()

        assert field_value(content, "site_code") == "S2"
        assert "This change will clear allocations" not in content
        t2.refresh_from_db()
        assert t2.site_code == "S1"


@pytest.mark.django_db
class TestCostItemPanel:
    def test_transaction_based_item_is_a_batch_edit_with_derived_amount(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        t1.dummy_field_3 = "X"
        t1.save()
        url = cost_items_url(analysis, cost_line_item_id=a.id)

        content = client_with_admin.get(url).content.decode()

        assert "Edit Cost Item" in content
        assert "Cost Item Description" in content
        assert field_value(content, "description") == "Salaries"
        assert field_value(content, "site_code") == "S1"
        assert re.search(r'name="amount"[^>]*disabled', content)
        assert "This amount is calculated from the underlying transactions" in content
        assert "Transaction Custom Field 3" in content
        assert 'name="transaction_description"' not in content
        assert 'name="date"' not in content

        response = client_with_admin.post(url, data={"description": "Staff pay", "site_code": "S2"})

        # Every transaction of the item moved into the existing S2 item; the explicit description
        # renamed that item and all of its transactions.
        assert '"operation": "saved"' in response.content.decode()
        assert not CostLineItem.objects.filter(id=a.id).exists()
        b.refresh_from_db()
        assert b.transactions.count() == 3
        assert b.budget_line_description == "Staff pay"
        assert set(b.transactions.values_list("budget_line_description", flat=True)) == {"Staff pay"}
        entry = correction_entries().get()
        assert entry.action == "Transactions Corrected"
        assert entry.message.startswith("Corrected 2 transactions in")
        assert "(Cost Item Description, Site)" in entry.message
        assert "1 cost item removed" in entry.message

    def test_budget_item_is_edited_directly(self, analysis, client_with_admin):
        r1 = CostLineItemFactory(analysis=analysis, total_cost=Decimal("100"), **item_defaults())
        r2 = CostLineItemFactory(analysis=analysis, total_cost=Decimal("50"), **item_defaults(site_code="S2"))
        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()
        r1.dummy_field_1 = "CC-1"
        r1.save()
        url = cost_items_url(analysis, "allocate", cost_line_item_id=r1.id)

        content = client_with_admin.get(url).content.decode()

        assert re.search(r'name="amount"[^>]*disabled', content) is None
        assert field_value(content, "amount") == "100.0000"
        assert "Budget Custom Field 1" in content
        assert 'name="cost_type"' not in content  # Allocate panel

        response = client_with_admin.post(
            url, data={"amount": "250", "grant_code": "G2", "dummy_field_1": "CC-2"}
        )

        assert '"operation": "saved"' in response.content.decode()
        r1.refresh_from_db()
        assert r1.total_cost == Decimal("250")
        assert r1.grant_code == "G2"
        assert r1.dummy_field_1 == "CC-2"
        r2.refresh_from_db()
        assert r2.total_cost == Decimal("50")
        entry = correction_entries().get()
        assert entry.action == "Cost Items Corrected"
        assert entry.message == (
            f"Corrected 1 cost item in {analysis.title} from Allocate Intervention Costs "
            "(Grant, Amount, Budget Custom Field 1)."
        )

    def test_bulk_budget_items_through_a_selection(self, analysis, client_with_admin):
        r1 = CostLineItemFactory(analysis=analysis, total_cost=Decimal("100"), **item_defaults())
        r2 = CostLineItemFactory(analysis=analysis, total_cost=Decimal("50"), **item_defaults(site_code="S2"))
        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()
        url = select(client_with_admin, analysis, "cost_items", [r1.id, r2.id])

        content = client_with_admin.get(url).content.decode()
        assert "Edit Cost Items" in content
        assert tageditor_options(content, "site_code")["placeholder"] == "<multiple values>"
        assert re.search(r'name="amount"[^>]*placeholder="&lt;multiple values&gt;"', content)

        client_with_admin.post(url, data={"site_code": "S2"})

        # Budget rows never merge: both keep their own row.
        for each in (r1, r2):
            each.refresh_from_db()
            assert each.site_code == "S2"
        assert analysis.cost_line_items.count() == 2

    def test_emptied_confirm_categories_table_redirects_to_the_destination(self, analysis, client_with_admin):
        r1 = CostLineItemFactory(analysis=analysis, total_cost=Decimal("100"), **item_defaults())
        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()
        program = r1.config.cost_type
        support = CostType.objects.get(type=Support.id)
        url = cost_items_url(analysis, cost_line_item_id=r1.id, cost_type=program.pk)

        response = client_with_admin.post(url, data={"cost_type": str(support.pk)})
        content = response.content.decode()

        destination = reverse(
            "analysis-categorize-cost_type", kwargs={"pk": analysis.pk, "cost_type_pk": support.pk}
        )
        assert '"redirect_to"' in content
        assert destination in content
        assert '"operation": "saved"' not in content
        assert not analysis.cost_type_categories.filter(cost_type=program).exists()

    def test_table_not_emptied_reloads(self, analysis, client_with_admin):
        r1 = CostLineItemFactory(analysis=analysis, total_cost=Decimal("100"), **item_defaults())
        r2 = CostLineItemFactory(
            analysis=analysis, total_cost=Decimal("100"), **item_defaults(site_code="S2")
        )
        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()
        program = r1.config.cost_type
        support = CostType.objects.get(type=Support.id)

        response = client_with_admin.post(
            cost_items_url(analysis, cost_line_item_id=r1.id, cost_type=program.pk),
            data={"cost_type": str(support.pk)},
        )

        assert '"operation": "saved"' in response.content.decode()


@pytest.mark.django_db
class TestSelectionAndAccess:
    def test_selection_endpoint_requires_post_ids_and_known_kind(
        self, transaction_analysis, client_with_admin
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        url = selection_url(analysis)

        assert client_with_admin.get(url).status_code == 405
        assert (
            client_with_admin.post(url, data={"kind": "transactions", "step": "categorize"}).status_code
            == 400
        )
        assert (
            client_with_admin.post(
                url, data={"kind": "widgets", "step": "categorize", "ids": ["1"]}
            ).status_code
            == 400
        )
        assert (
            client_with_admin.post(
                url, data={"kind": "transactions", "step": "nope", "ids": ["1"]}
            ).status_code
            == 400
        )

        response = client_with_admin.post(
            url,
            data={
                "kind": "transactions",
                "step": "allocate",
                "ids": [f"{t1.id},{t2.id}", str(t3.id)],
                "cost_type": "7",
            },
        )

        payload = response.json()
        assert payload["count"] == 3
        assert payload["url"].startswith(transactions_url(analysis, "allocate") + "?selection=")
        assert payload["url"].endswith("&cost_type=7")
        assert client_with_admin.get(payload["url"]).status_code == 200

    def test_a_selection_is_bound_to_its_analysis_and_kind(
        self, transaction_analysis, client_with_admin, defaults
    ):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        other = make_analysis()
        url = select(client_with_admin, analysis, "transactions", [t1.id])
        token = url.split("selection=")[1]

        assert client_with_admin.get(transactions_url(other, selection=token)).status_code == 404
        assert client_with_admin.get(cost_items_url(analysis, selection=token)).status_code == 404
        assert client_with_admin.get(transactions_url(analysis, selection="unknown")).status_code == 404

    def test_ids_outside_the_analysis_are_not_editable(
        self, transaction_analysis, client_with_admin, defaults
    ):
        analysis = transaction_analysis
        other = make_analysis()
        foreign = tx(other)
        group(other)

        assert client_with_admin.get(transactions_url(analysis, transaction_id=foreign.id)).status_code == 404
        assert client_with_admin.get(transactions_url(analysis)).status_code == 404
        assert (
            client_with_admin.get(
                transactions_url(analysis, "elsewhere", transaction_id=foreign.id)
            ).status_code
            == 404
        )

    def test_a_user_without_change_permission_is_refused(self, transaction_analysis, client):
        analysis = transaction_analysis
        a, b, t1, t2, t3 = items(analysis)
        client.force_login(UserFactory(role=User.BASIC_USER))

        assert client.get(transactions_url(analysis, transaction_id=t1.id)).status_code == 403
        assert (
            client.post(
                selection_url(analysis), data={"kind": "transactions", "step": "categorize", "ids": ["1"]}
            ).status_code
            == 403
        )
        assert client.get(cost_items_url(analysis, cost_line_item_id=a.id)).status_code == 403
