"""Regression tests for the custom field requirements that were already satisfied
by the code when the 90.x work started (90.3, 90.4, 90.5).

These pin behaviour that is easy to break accidentally -- reordering
CANONICAL_TRANSACTION_FIELDS, adding a field to a cost line item grouping key, or
dropping a canonical_field_sources entry from an org template.
"""

import datetime
import sys
import types
from decimal import Decimal
from io import BytesIO

import pytest
from django.core.exceptions import ImproperlyConfigured

from website.data_loading.transaction_templates import TransactionTemplate
from website.data_loading.transaction_templates.base import CANONICAL_TRANSACTION_FIELDS
from website.data_loading.transaction_templates.registry import get_transaction_template
from website.data_loading.transactions import load_transactions, normalize_uploaded_transaction_file
from website.models import Transaction
from website.tests.factories import AnalysisFactory, CountryFactory, TransactionFactory

CUSTOM_FIELDS = [f"dummy_field_{n}" for n in range(1, 6)]


def _set_active_template(monkeypatch, template_id):
    monkeypatch.setattr(
        "website.data_loading.transaction_templates.registry.get_active_transaction_template_id",
        lambda: template_id,
    )


def _install_template_module(monkeypatch, template_id, template_cls):
    module = types.ModuleType(f"website.data_loading.transaction_templates.{template_id}")
    module.Template = template_cls
    monkeypatch.setitem(sys.modules, module.__name__, module)


# --------------------------------------------------------------------------------------
# 90.3 -- the 5 columns after the standard transaction columns import as
#         Transaction Custom Field 1-5
# --------------------------------------------------------------------------------------


def test_custom_fields_are_the_five_columns_after_the_standard_ones():
    assert CANONICAL_TRANSACTION_FIELDS[-5:] == CUSTOM_FIELDS
    assert CANONICAL_TRANSACTION_FIELDS[-6] == "amount"


def test_default_template_reads_columns_m_to_q_as_custom_fields(monkeypatch):
    _set_active_template(monkeypatch, "dioptra_default")

    succeeded, normalized = normalize_uploaded_transaction_file(
        [
            CANONICAL_TRANSACTION_FIELDS,
            [
                "2015-01-01",  # A transaction_date
                "JO",  # B country_code
                "100",  # C grant_code
                "200",  # D budget_line_code
                "300",  # E account_code
                "400",  # F site_code
                "500",  # G sector_code
                "600",  # H transaction_code
                "A description",  # I transaction_description
                "USD",  # J currency_code
                "Budget line",  # K budget_line_description
                "123.45",  # L amount
                "CC-100",  # M dummy_field_1
                "DFID",  # N dummy_field_2
                "PRJ-7",  # O dummy_field_3
                "Phase 2",  # P dummy_field_4
                "Restricted",  # Q dummy_field_5
            ],
        ],
        analysis=object(),
    )

    assert succeeded
    assert [normalized[0][field] for field in CUSTOM_FIELDS] == [
        "CC-100",
        "DFID",
        "PRJ-7",
        "Phase 2",
        "Restricted",
    ]


@pytest.mark.django_db
def test_uploaded_custom_field_values_are_persisted_on_transactions(monkeypatch):
    """Round trip: fill in the workbook a user actually downloads, upload it, check the rows."""
    _set_active_template(monkeypatch, "dioptra_default")
    analysis = AnalysisFactory(
        start_date=datetime.date(2015, 1, 1),
        end_date=datetime.date(2015, 12, 31),
        grants="100",
    )

    workbook = get_transaction_template().build_download_workbook()
    workbook.active.append(
        [
            datetime.date(2015, 1, 1),
            "JO",
            "100",
            "200",
            "300",
            "400",
            "500",
            "600",
            "A description",
            "USD",
            "Budget line",
            "123.45",
            "CC-100",
            "DFID",
            "PRJ-7",
            "Phase 2",
            "Restricted",
        ]
    )
    upload = BytesIO()
    workbook.save(upload)
    upload.seek(0)
    upload.name = "transactions.xlsx"

    succeeded, result = load_transactions(analysis, f=upload)

    assert succeeded, result.get("errors")
    transaction = analysis.transactions.get()
    assert [getattr(transaction, field) for field in CUSTOM_FIELDS] == [
        "CC-100",
        "DFID",
        "PRJ-7",
        "Phase 2",
        "Restricted",
    ]


# --------------------------------------------------------------------------------------
# 90.4 -- up to 5 custom columns can be designated in a custom template mapping
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "template_id",
    [
        "dioptra_default",
        "save_the_children",
        "catholic_relief_services",
        "accion_contra_el_hambre",
        "cooperative_for_assistance_and_relief_everywhere",
        "danish_refugee_council",
        "mercy_corps",
    ],
)
def test_every_template_designates_all_five_custom_fields(monkeypatch, template_id):
    _set_active_template(monkeypatch, template_id)
    template = get_transaction_template()

    for field in CUSTOM_FIELDS:
        assert field in template.canonical_field_sources


def test_a_template_may_map_custom_fields_to_differently_named_source_columns(monkeypatch):
    """A developer designates custom columns via canonical_field_sources."""

    class Template(TransactionTemplate):
        id = "designating_template"
        label = "Designating template"
        download_headers = ["Date", "Cost Centre", "Donor"]
        source_date_formats = {"date": ("%Y-%m-%d",)}
        canonical_field_sources = dict.fromkeys(CANONICAL_TRANSACTION_FIELDS)
        canonical_field_sources.update(
            {
                "transaction_date": "date",
                "dummy_field_1": "cost_centre",
                "dummy_field_2": "donor",
            }
        )

        def normalize_rows(self, rows, analysis):
            return [
                {
                    "transaction_date": row.get("date", ""),
                    "dummy_field_1": row.get("cost_centre", ""),
                    "dummy_field_2": row.get("donor", ""),
                }
                for row in rows
            ]

    _install_template_module(monkeypatch, "designating_template", Template)
    _set_active_template(monkeypatch, "designating_template")

    succeeded, normalized = normalize_uploaded_transaction_file(
        [["Date", "Cost Centre", "Donor"], ["2015-01-01", "CC-100", "DFID"]],
        analysis=object(),
    )

    assert succeeded
    assert normalized[0]["dummy_field_1"] == "CC-100"
    assert normalized[0]["dummy_field_2"] == "DFID"
    # Undesignated custom fields simply stay empty.
    assert normalized[0]["dummy_field_5"] == ""


def test_a_template_omitting_a_custom_field_source_is_rejected(monkeypatch):
    class Template(TransactionTemplate):
        id = "incomplete_template"
        label = "Incomplete template"
        download_headers = list(CANONICAL_TRANSACTION_FIELDS)
        canonical_field_sources = {
            field: field for field in CANONICAL_TRANSACTION_FIELDS if field != "dummy_field_5"
        }

    _install_template_module(monkeypatch, "incomplete_template", Template)
    _set_active_template(monkeypatch, "incomplete_template")
    template = get_transaction_template()

    with pytest.raises(ImproperlyConfigured, match="dummy_field_5"):
        template.get_validation_field_labels([template.get_download_headers()])


# --------------------------------------------------------------------------------------
# 90.5 -- transactions coalesce into one cost item regardless of custom field values
# --------------------------------------------------------------------------------------


def _matching_transaction(analysis, **custom_fields):
    return TransactionFactory(
        analysis=analysis,
        country_code="JO",
        grant_code="AB234",
        budget_line_code="BL1",
        account_code="9012",
        site_code="KL89",
        sector_code="SEC1",
        budget_line_description="Salaries",
        amount_in_instance_currency=Decimal("100.00"),
        amount_in_source_currency=Decimal("100.00"),
        **custom_fields,
    )


@pytest.fixture
def _analysis_for_coalescing():
    return AnalysisFactory(country=CountryFactory(name="Jordan", code="JO"), grants="AB234")


@pytest.mark.django_db
class TestCustomFieldsDoNotAffectCoalescing:
    def test_differing_custom_fields_still_coalesce_into_one_cost_item(self, _analysis_for_coalescing):
        analysis = _analysis_for_coalescing
        _matching_transaction(analysis, dummy_field_1="CC-100", dummy_field_3="PRJ-7")
        _matching_transaction(analysis, dummy_field_1="CC-999", dummy_field_3="PRJ-8")
        _matching_transaction(analysis, dummy_field_5="Restricted")

        analysis.create_cost_line_items_from_transactions()

        cost_line_item = analysis.cost_line_items.get()
        assert cost_line_item.total_cost == Decimal("300.0000")
        assert cost_line_item.transactions.count() == 3

    def test_custom_field_values_do_not_roll_up_onto_the_cost_item(self, _analysis_for_coalescing):
        analysis = _analysis_for_coalescing
        _matching_transaction(analysis, dummy_field_1="CC-100")

        analysis.create_cost_line_items_from_transactions()

        cost_line_item = analysis.cost_line_items.get()
        assert [getattr(cost_line_item, field) for field in CUSTOM_FIELDS] == [""] * 5

    def test_a_differing_grouping_field_still_splits_the_cost_item(self, _analysis_for_coalescing):
        """Guards the test above: coalescing is driven by the code fields, not by luck."""
        analysis = _analysis_for_coalescing
        _matching_transaction(analysis, dummy_field_1="CC-100")
        transaction = _matching_transaction(analysis, dummy_field_1="CC-100")
        transaction.site_code = "OTHER"
        transaction.save()

        analysis.create_cost_line_items_from_transactions()

        assert analysis.cost_line_items.count() == 2

    def test_resync_also_ignores_custom_fields_when_grouping(self, _analysis_for_coalescing):
        analysis = _analysis_for_coalescing
        _matching_transaction(analysis, dummy_field_2="DFID")
        _matching_transaction(analysis, dummy_field_2="ECHO")

        analysis.create_cost_line_items_from_transactions()
        assert analysis.cost_line_items.count() == 1

        # A third transaction arrives on resync, again with its own custom field values.
        _matching_transaction(analysis, dummy_field_2="USAID")
        analysis.sync_cost_line_items(Transaction.objects.filter(analysis=analysis))

        cost_line_item = analysis.cost_line_items.get()
        assert cost_line_item.total_cost == Decimal("300.0000")
        assert cost_line_item.transactions.count() == 3
