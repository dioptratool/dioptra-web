"""
The build command's "Sample Analysis - Filters Demo" sample: a transaction analysis with enough
variety (sites, sectors, account descriptions, dates, amounts, custom fields) to demonstrate the
Feature 98 filters on all three step pages.
"""

import pytest

from website.filterset import (
    AllocateSubcomponentsFilterSet,
    CategorizeCostTypeFilterSet,
)
from website.management.commands.build import Command
from website.management.commands.seed_data.default import CATEGORIES, COST_TYPES, MAPPINGS
from website.models import AccountCodeDescription, Analysis, AnalysisStatus, FieldLabelOverrides
from website.workflows import AnalysisWorkflow

SAMPLE_TITLE = "Sample Analysis - Filters Demo"


def build_sample():
    """Seed the reference data the sample needs, then the sample itself (no flush, no media clean)."""
    command = Command()
    command.add_settings()
    command.add_countries_and_regions()
    command.add_categories(CATEGORIES)
    command.add_cost_types(COST_TYPES)
    command.add_cost_type_category_mappings(mappings=MAPPINGS)
    command.add_interventions()
    command.add_analysis_types()
    command.add_account_code_descriptions()
    command.add_users()
    command.add_debug_analysis_for_filters()
    return Analysis.objects.get(title=SAMPLE_TITLE)


@pytest.fixture
def sample(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return build_sample()


def filterset(filterset_class, analysis):
    return filterset_class(None, queryset=analysis.cost_line_items.all(), analysis=analysis)


@pytest.mark.django_db(databases=["default", "transaction_store"])
class TestFiltersDemoSample:
    def test_every_step_page_is_reachable(self, sample):
        workflow = AnalysisWorkflow(sample)

        assert sample.analysis_status == AnalysisStatus.IN_PROGRESS
        assert workflow.all_steps_complete
        assert workflow.get_step("insights").dependencies_met
        assert sample.interventioninstance_set.count() == 1
        assert len(sample.interventioninstance_set.get().subcomponent_cost_analysis.subcomponent_labels) == 3

    def test_has_the_grant_gh012_transactions_grouped_into_cost_items(self, sample):
        assert sample.grants == "GH012"
        assert sample.transactions.count() == 3487
        assert sample.cost_line_items.count() == 285
        assert sample.cost_line_items.exclude(site_code="").values("site_code").distinct().count() == 12
        assert sample.cost_line_items.values("sector_code").distinct().count() == 4
        assert sample.transactions.values("date").distinct().count() >= 80  # April 2015 to January 2017

    def test_custom_fields_are_populated_and_named(self, sample):
        assert [c["field"] for c in sample.cost_item_custom_fields] == ["dummy_field_1"]
        assert [c["field"] for c in sample.transaction_custom_fields] == ["dummy_field_1", "dummy_field_2"]
        assert sample.transactions.filter(dummy_field_1__startswith="PRJ-").count() == 3487
        assert set(sample.transactions.values_list("dummy_field_2", flat=True)) == {
            "FY2015",
            "FY2016",
            "FY2017",
        }
        assert sample.cost_line_items.exclude(dummy_field_1__startswith="PRJ-").count() == 0

        overrides = FieldLabelOverrides.get()
        assert (overrides.ci_dummy_field_1, overrides.ci_dummy_field_1_overridden) == ("Project Code", True)
        assert (overrides.tr_dummy_field_1, overrides.tr_dummy_field_1_overridden) == ("Project Code", True)
        assert (overrides.tr_dummy_field_2, overrides.tr_dummy_field_2_overridden) == ("Fiscal Year", True)

    def test_account_descriptions_cover_the_common_codes_with_one_sensitive(self, sample):
        descriptions = AccountCodeDescription.as_map()
        codes = set(sample.cost_line_items.values_list("account_code", flat=True))

        described = {code for code in codes if code in descriptions}
        assert len(described) == 8
        assert len(codes - described) >= 10  # the rest show as raw codes
        assert descriptions["71100"].account_description == "Salaries - National Staff"
        assert descriptions["70050"].account_description == descriptions["70020"].account_description
        sensitive = [code for code in codes if descriptions.get(code) and descriptions[code].sensitive_data]
        assert sensitive == ["71000"]

    def test_filters_offered_on_the_pages(self, sample):
        categorize = filterset(CategorizeCostTypeFilterSet, sample)
        subcomponents = filterset(AllocateSubcomponentsFilterSet, sample)

        headings = [heading for heading, _facets in categorize.facet_groups()]
        assert headings == ["Cost item", "Transaction"]
        names = [facet.field.name for _h, facets in categorize.facet_groups() for facet in facets]
        assert names == [
            "budget_line_description",
            "grant_code",
            "site_code",
            "sector_code",
            "account_description",
            "total_cost",
            "ci_dummy_field_1",
            "transaction_description",
            "transaction_date",
            "transaction_amount",
            "tr_dummy_field_1",
            "tr_dummy_field_2",
        ]
        assert categorize.form.fields["ci_dummy_field_1"].label == "Project Code"
        assert categorize.form.fields["tr_dummy_field_2"].label == "Fiscal Year"
        account_options = [value for value, _label in categorize.form.fields["account_description"].choices]
        assert "Salaries - National Staff" in account_options
        assert "71311" in account_options  # a code without a description
        assert not any(name.endswith("dummy_field_1") for name in subcomponents.form.fields)
