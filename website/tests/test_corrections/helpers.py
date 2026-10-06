"""
Shared builders for the Feature 91 tests.

Transaction-based analyses are built the way Load Data builds them: transactions are inserted and
grouped into cost items by ``create_cost_line_items_from_transactions``, then auto-categorised and
given their Cost Type / Category bookkeeping objects.
"""

from decimal import Decimal

from website.models import CostLineItemInterventionAllocation, Country
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemInterventionAllocationFactory,
    CountryFactory,
    InterventionFactory,
    TransactionFactory,
)

TX_DEFAULTS = dict(
    country_code="JO",
    grant_code="G1",
    budget_line_code="BL1",
    account_code="4100",
    site_code="S1",
    sector_code="SEC",
    budget_line_description="Salaries",
    transaction_description="Payroll",
)


def make_analysis():
    """An analysis with two defined grants and one intervention; needs the ``defaults`` fixture."""
    country = Country.objects.filter(code="JO").first() or CountryFactory(name="Jordan", code="JO")
    analysis = AnalysisFactory(country=country, grants="G1,G2")
    analysis.add_intervention(
        InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"]),
        parameters={"number_of_teachers": 1, "number_of_days_of_training": 1},
    )
    return analysis


def tx(analysis, amount="100", **overrides):
    values = {**TX_DEFAULTS, **overrides}
    return TransactionFactory(
        analysis=analysis,
        amount_in_instance_currency=Decimal(amount),
        amount_in_source_currency=Decimal(amount),
        **values,
    )


def item_defaults(**overrides):
    """CostLineItem column values matching TX_DEFAULTS (which has no transaction_description)."""
    values = {k: v for k, v in TX_DEFAULTS.items() if k != "transaction_description"}
    values.update(overrides)
    return values


def group(analysis):
    """Run the real Load Data grouping and bookkeeping over the analysis' transactions."""
    analysis.create_cost_line_items_from_transactions()
    analysis.auto_categorize_cost_line_items()
    analysis.ensure_cost_type_category_objects()


def item_for(analysis, **key):
    return analysis.cost_line_items.select_related("config").get(**key)


def allocate(cost_line_item, percent):
    for instance in cost_line_item.analysis.interventioninstance_set.all():
        CostLineItemInterventionAllocationFactory(
            cli_config=cost_line_item.config,
            intervention_instance=instance,
            allocation=Decimal(percent),
        )


def allocations_of(cost_line_item):
    return list(
        CostLineItemInterventionAllocation.objects.filter(cli_config=cost_line_item.config).values_list(
            "allocation", flat=True
        )
    )
