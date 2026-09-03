"""
Feature 91 -- application log entries and field labels (spec section 15).
"""

import pytest
from app_log.models import AppLogEntry

from website.corrections import (
    COST_ITEM,
    TRANSACTION,
    CorrectionResult,
    correction_log_message,
    field_labels,
    log_correction,
)
from website.corrections.labels import (
    BUDGET_CUSTOM_FIELDS,
    TRANSACTION_CUSTOM_FIELDS,
)
from website.models import FieldLabelOverrides
from website.tests.factories import AnalysisFactory, UserFactory


def result(**overrides):
    values = dict(
        record_count=1,
        changed_fields=[],
        created_count=0,
        existing_count=0,
        removed_count=0,
        cleared_count=0,
        structural=False,
    )
    values.update(overrides)
    return CorrectionResult(**values)


@pytest.mark.django_db
class TestMessage:
    def test_structural_transaction_correction_matches_the_spec_example(self):
        analysis = AnalysisFactory(title="Malnutrition Treatment in Iraq")
        labels = field_labels(TRANSACTION, TRANSACTION_CUSTOM_FIELDS)

        message = correction_log_message(
            analysis,
            result(
                record_count=12,
                changed_fields=["site_code", "sector_code"],
                created_count=1,
                existing_count=1,
                removed_count=1,
                cleared_count=2,
                structural=True,
            ),
            "categorize",
            TRANSACTION,
            labels,
        )

        assert message == (
            "Corrected 12 transactions in Malnutrition Treatment in Iraq from Confirm Categories "
            "(Site, Sector Code); regrouped into 2 cost items (1 created, 1 existing), "
            "1 cost item removed; cleared allocations on 2 cost items."
        )

    def test_plain_cost_item_correction_matches_the_spec_example(self):
        analysis = AnalysisFactory(title="Malnutrition Treatment in Iraq")
        labels = field_labels(COST_ITEM, BUDGET_CUSTOM_FIELDS)

        message = correction_log_message(
            analysis,
            result(record_count=3, changed_fields=["grant_code"]),
            "allocate",
            COST_ITEM,
            labels,
        )

        assert message == (
            "Corrected 3 cost items in Malnutrition Treatment in Iraq from "
            "Allocate Intervention Costs (Grant)."
        )

    def test_singular_forms_and_no_field_clause_when_nothing_changed(self):
        analysis = AnalysisFactory(title="A")

        message = correction_log_message(
            analysis,
            result(record_count=1, existing_count=1, cleared_count=1, structural=True),
            "allocate",
            TRANSACTION,
            field_labels(TRANSACTION, TRANSACTION_CUSTOM_FIELDS),
        )

        assert message == (
            "Corrected 1 transaction in A from Allocate Intervention Costs; "
            "regrouped into 1 cost item (0 created, 1 existing); cleared allocations on 1 cost item."
        )

    def test_labels_honour_overrides_and_custom_field_family(self):
        overrides = FieldLabelOverrides.get()
        overrides.ci_grant_code = "Award"
        overrides.ci_grant_code_overridden = True
        overrides.tr_site_code = "Location"
        overrides.tr_site_code_overridden = True
        overrides.tr_dummy_field_2 = "Project Code"
        overrides.tr_dummy_field_2_overridden = True
        overrides.ci_dummy_field_2 = "Cost Centre"
        overrides.ci_dummy_field_2_overridden = True
        overrides.save()

        transaction_labels = field_labels(TRANSACTION, TRANSACTION_CUSTOM_FIELDS)
        assert transaction_labels["grant_code"] == "Award"
        assert transaction_labels["site_code"] == "Location"
        assert transaction_labels["dummy_field_2"] == "Project Code"
        assert transaction_labels["dummy_field_1"] == "Transaction Custom Field 1"

        # A transaction-based cost-item panel: cost-item Site label, transaction custom fields.
        batch_labels = field_labels(COST_ITEM, TRANSACTION_CUSTOM_FIELDS)
        assert batch_labels["site_code"] == "Site"
        assert batch_labels["dummy_field_2"] == "Project Code"

        budget_labels = field_labels(COST_ITEM, BUDGET_CUSTOM_FIELDS)
        assert budget_labels["dummy_field_2"] == "Cost Centre"
        assert budget_labels["dummy_field_3"] == "Budget Custom Field 3"


@pytest.mark.django_db
class TestLogEntries:
    def test_transaction_correction_writes_one_entry_against_the_analysis(self):
        analysis = AnalysisFactory(title="A")
        user = UserFactory()

        log_correction(
            analysis,
            result(record_count=2, changed_fields=["amount"]),
            "categorize",
            TRANSACTION,
            field_labels(TRANSACTION, TRANSACTION_CUSTOM_FIELDS),
            user,
        )

        entry = AppLogEntry.objects.get()
        assert entry.action == "Transactions Corrected"
        assert entry.actor_user == user
        assert entry.obj == analysis
        assert entry.message == "Corrected 2 transactions in A from Confirm Categories (Amount)."

    def test_cost_item_correction_uses_its_own_action(self):
        analysis = AnalysisFactory(title="A")

        log_correction(
            analysis,
            result(record_count=1, changed_fields=["site_code"]),
            "allocate",
            COST_ITEM,
            field_labels(COST_ITEM, BUDGET_CUSTOM_FIELDS),
            UserFactory(),
        )

        entry = AppLogEntry.objects.get()
        assert entry.action == "Cost Items Corrected"
        assert entry.message == "Corrected 1 cost item in A from Allocate Intervention Costs (Site)."
