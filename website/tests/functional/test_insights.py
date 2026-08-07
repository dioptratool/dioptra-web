from datetime import date

from django.test import TestCase
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from website.models import AnalysisCostType
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    CostTypeFactory,
    CountryFactory,
    InsightComparisonDataFactory,
    InterventionFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
)
from website.users.models import User
from website.views.analysis.steps.insights import Insights
from website.views.intervention import InterventionInsights


class InsightsTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()

        owner = User.objects.create(name="Rusty Shackleford")
        country = CountryFactory(name="'Merica", code="USofA")
        intervention = InterventionFactory(
            name="My Test Intervention",
            output_metrics=[
                "ValueOfCashDistributed",
            ],
        )
        self.analysis = AnalysisFactory(
            title="My Test Analysis",
            description="My Test Analysis Description",
            owner=owner,
            country=country,
            currency_code="USD",
            start_date=date(2021, 1, 1),
            end_date=date(2022, 1, 1),
            in_kind_contributions=True,
        )
        self.analysis.add_intervention(intervention, parameters={"value_of_cash_distributed": 10})
        self.insights_view = Insights(analysis=self.analysis)

    def test_get_insights_bar_chart_data_test(self):
        output_cost_all = 700
        output_cost_direct = 600
        output_cost_in_kind = 300

        bar_chart_data = self.insights_view._get_bar_chart_data(
            output_cost_all,
            output_cost_direct,
            output_cost_in_kind=output_cost_in_kind,
        )
        expected_data = {
            "direct": {
                "aggregate": "$600.00",
                "value": "$600.00",
                "percent": 60.0,
                "label": _("Program Costs Only"),
            },
            "total": {
                "aggregate": "$700.00",
                "value": "$100.00",
                "percent": 10.0,
                "label": _(
                    """
                    Including Program Costs ($600.00), Support Costs and Indirect Costs ($100.00)
                    """
                ),
            },
            "in_kind": {
                "aggregate": "$1,000.00",
                "value": "$300.00",
                "percent": 30.0,
                "label": _(
                    """
                    Including Program Costs ($600.00), Support Costs and Indirect Costs ($100.00), In-Kind
                    Contributions ($300.00)
                    """
                ),
            },
        }

        for cost_type in ["direct", "total", "in_kind"]:
            assert bar_chart_data[cost_type]["aggregate"] == expected_data[cost_type]["aggregate"]

            assert bar_chart_data[cost_type]["value"] == expected_data[cost_type]["value"]

            assert bar_chart_data[cost_type]["percent"] == expected_data[cost_type]["percent"]

            # To compare strings, we must split to avoid \n and \t differences
            assert bar_chart_data[cost_type]["label"].split() == expected_data[cost_type]["label"].split()

    def test_get_formatted_parameter_values_formats_cash_as_currency(self):
        intervention_instance = self.analysis.interventioninstance_set.first()

        parameter_values = self.insights_view._get_formatted_parameter_values()

        assert parameter_values[intervention_instance.id]["Value of Cash Distributed"] == "$10.00"

    def test_subcomponent_breakdown_includes_in_kind_chart_data(self):
        intervention_instance = self.analysis.interventioninstance_set.first()
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=intervention_instance,
            subcomponent_labels=["Treatment", "Outreach"],
        )
        program_config = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(
                analysis=self.analysis,
                total_cost=100,
            ),
            cost_type=None,
            category=None,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=program_config,
            intervention_instance=intervention_instance,
            allocation=100,
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=program_config,
            allocations={
                "0": "60",
                "1": "40",
            },
        )
        CostTypeFactory(name="Program Costs", type=10, order=1, default=True)
        support_config = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(
                analysis=self.analysis,
                total_cost=900,
            ),
            cost_type=CostTypeFactory(name="Support Costs", type=20, order=2),
            category=None,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=support_config,
            intervention_instance=intervention_instance,
            allocation=100,
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=support_config,
            allocations={
                "0": "0",
                "1": "100",
            },
        )
        in_kind_config = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(
                analysis=self.analysis,
                total_cost=100,
            ),
            analysis_cost_type=AnalysisCostType.IN_KIND,
            cost_type=None,
            category=None,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=in_kind_config,
            intervention_instance=intervention_instance,
            allocation=50,
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=in_kind_config,
            allocations={
                "0": "25",
                "1": "75",
            },
        )

        breakdown = self.insights_view._get_subcomponent_analysis_breakdown_data(intervention_instance)

        assert breakdown["chart_data"] == {
            "Treatment": 60,
            "Outreach": 40,
        }
        assert breakdown["in_kind_chart_data"] == {
            "Treatment": 25,
            "Outreach": 75,
        }
        rendered = render_to_string(
            "insights/_subcomponent-chart.html",
            {
                "analysis": self.analysis,
                "chart_data": breakdown["chart_data"],
                "total_cost": 100,
                "in_kind_chart_data": breakdown["in_kind_chart_data"],
                "in_kind_total_cost": 20,
            },
        )
        assert "In-Kind Contributions" in rendered


class InterventionInsightsTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.intervention = InterventionFactory(
            name="My Test Intervention",
            output_metrics=[
                "ValueOfCashDistributed",
            ],
        )
        self.insights_view = InterventionInsights(object=self.intervention)

    def test_get_insights_chart_data_test(self):
        """
        Test verifies the null cost lines are correctly displayed as N/A and sorted to the top of the data
        :return:
        """
        country = CountryFactory(name="Jordan", code="JO")
        InsightComparisonDataFactory(
            name="Insight One",
            country=country,
            grants="GRANT123",
            intervention=self.intervention,
            parameters={"value_of_cash_distributed": 543.21},
            output_costs={"ValueOfCashDistributed": {"all": None, "direct_only": None}},
        )
        InsightComparisonDataFactory(
            name="Insight Two",
            country=country,
            grants="GRANT123",
            intervention=self.intervention,
            parameters={"value_of_cash_distributed": 123.45},
            output_costs={"ValueOfCashDistributed": {"all": 0.2, "direct_only": 0.1}},
        )
        InsightComparisonDataFactory(
            name="Insight Three",
            country=country,
            grants="ZGRANT123",
            intervention=self.intervention,
            parameters={"value_of_cash_distributed": 123.45},
            output_costs={"ValueOfCashDistributed": {"all": None, "direct_only": 0.3}},
        )
        InsightComparisonDataFactory(
            name="Insight Four",
            country=country,
            grants="GRANT123",
            intervention=self.intervention,
            parameters={"value_of_cash_distributed": 123.45},
            output_costs={"ValueOfCashDistributed": {"all": 0.3, "direct_only": 0.2}},
        )
        output_metric = self.insights_view.object.output_metric_objects()[0]

        # Run method to test
        insights_chart_data = self.insights_view._get_insights_chart_data(output_metric)

        expected_data = [
            {
                "label": "Jordan",
                "grants": "GRANT123",
                "description": "Cash Distributed: €543.21",
                "tooltip": "Insight One",
                "output_cost_all": "N/A",
                "output_cost_direct_only": "N/A",
                "raw_output_cost_all": None,
                "raw_output_cost_direct_only": None,
            },
            {
                "label": "Jordan",
                "grants": "GRANT123",
                "description": "Cash Distributed: €123.45",
                "tooltip": "Insight Two",
                "output_cost_all": 0.2,
                "output_cost_direct_only": 0.1,
                "raw_output_cost_all": 0.2,
                "raw_output_cost_direct_only": 0.1,
            },
            {
                "label": "Jordan",
                "grants": "GRANT123",
                "description": "Cash Distributed: €123.45",
                "tooltip": "Insight Four",
                "output_cost_all": 0.3,
                "output_cost_direct_only": 0.2,
                "raw_output_cost_all": 0.3,
                "raw_output_cost_direct_only": 0.2,
            },
            {
                "label": "Jordan",
                "grants": "ZGRANT123",
                "description": "Cash Distributed: €123.45",
                "tooltip": "Insight Three",
                "output_cost_all": "N/A",
                "output_cost_direct_only": 0.3,
                "raw_output_cost_all": None,
                "raw_output_cost_direct_only": 0.3,
            },
        ]
        assert insights_chart_data == expected_data
