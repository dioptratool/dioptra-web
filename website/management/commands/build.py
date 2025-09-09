import csv
import datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.validators import get_available_image_extensions

from ombucore.assets.models import ImageAsset
from ombucore.build import BuildCommand
from website import betterdb
from website.help.build import help_build
from website.models import (
    AccountCodeDescription,
    CostEfficiencyStrategy,
    CostLineItemConfig,
)
from website.models import Analysis, AnalysisType
from website.models import Category, CostType, Country, Region
from website.models import CostTypeCategoryMapping, Transaction
from website.models import InsightComparisonData
from website.models import Intervention, InterventionGroup
from website.models import Settings
from .seed_data.default import COST_TYPES
from .seed_data.default.categories import DEFAULT_CATEGORY
from .seed_data.default.cost_types import DEFAULT_COST_TYPE
from .seed_data.default.interventions import INTERVENTIONS
from .utils import (
    BulkCreateManager,
    _check_analysis_status,
    clean_csv_number,
    parse_csv_currency_to_decimal,
)
from ...data_loading.cost_line_items import load_cost_line_items_from_file
from ...models.cost_line_item import CostLineItemInterventionAllocation
from ...models.output_metric import OUTPUT_METRICS_BY_ID
from ...utils.duplicator import clone_analysis

THIS_DIR = Path(__file__).resolve().parent
User = get_user_model()


class Command(BuildCommand):
    def handle(self, *args, **options):
        super().handle(*args, **options)
        self.add_settings()
        self.add_countries_and_regions()
        self.add_assets()

        ngo = options.get("ngo")

        print(f"Loading data for NGO: '{ngo}'")
        if ngo == "default":
            from .seed_data.default import MAPPINGS, CATEGORIES
        elif ngo == "mercy-corp":
            from .seed_data.mercy_corp import MAPPINGS, CATEGORIES
        elif ngo == "irc":
            from .seed_data.irc import MAPPINGS, CATEGORIES
        elif ngo == "save-the-children":
            from .seed_data.save_the_children import MAPPINGS, CATEGORIES
        else:
            raise ValueError(f"Invalid NGO selection: '{ngo}'")
        self.add_categories(CATEGORIES)
        self.add_cost_types(COST_TYPES)
        self.add_cost_type_category_mappings(mappings=MAPPINGS)
        self.add_interventions()
        self.add_analysis_types()
        self.add_cost_efficiency_strategies()
        self.add_account_code_descriptions()
        self.add_users()
        self.add_analyses()
        self.add_insight_comparison_data()

        help_build()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.countries = {}
        self.cost_types = {}
        self.categories = {}
        self.analysis_types = {}
        self.groups = {}
        self.interventions = {}

    def add_arguments(self, parser):
        parser.add_argument(
            "--ngo",
            const="default",
            nargs="?",
            default="default",
            choices=["default", "save-the-children", "irc", "mercy-corp"],
            help="Populate the database with data for this particular NGO",
        )

        super().add_arguments(parser)

    def add_users(self):
        users_to_create = [
            {
                "name": "Administrator",
                "primary_country": "DR Congo",
                "secondary_countries": [],
                "role": User.ADMIN,
            },
            {
                "name": "Caitlin Tulloch",
                "primary_country": "Jordan",
                "secondary_countries": ["Niger", "Yemen", "Philippines", "Iraq"],
                "role": User.BASIC_USER,
            },
            {
                "name": "Akmal Shah",
                "primary_country": "Iraq",
                "secondary_countries": ["Jordan", "Yemen"],
                "role": User.BASIC_USER,
            },
            {
                "name": "Takhani Kromah",
                "primary_country": "Liberia",
                "secondary_countries": ["Jordan"],
                "role": User.BASIC_USER,
            },
            {
                "name": "Jane Doe",
                "primary_country": "Philippines",
                "secondary_countries": [],
                "role": User.BASIC_USER,
            },
            {
                "name": "John Doe",
                "primary_country": "Iraq",
                "secondary_countries": [],
                "role": User.BASIC_USER,
            },
            {
                "name": "Dioptra Test User",
                "primary_country": "Iraq",
                "secondary_countries": [],
                "email": "analytics@dioptratool.org",
                "role": User.ADMIN,
            },
        ]

        for each_user in users_to_create:
            new_user = User.objects.create(
                name=each_user["name"],
                primary_country=self.countries[each_user["primary_country"]],
                role=each_user["role"],
            )
            for each_country in each_user["secondary_countries"]:
                new_user.secondary_countries.add(self.countries[each_country])

            if "email" in each_user:
                new_user.email = each_user["email"]
            else:
                suffix = new_user.name.lower().replace(" ", "")
                new_user.email = f"dioptra_{settings.INSTANCE_NAME}+{suffix}@dioptratool.org"
            new_user.set_password("password")
            new_user.save()

    @staticmethod
    def add_settings():
        site_settings = Settings.objects.create()

        path = THIS_DIR / "build_content" / "Budget Upload Template.xls"
        with open(path, "rb") as f:
            site_settings.budget_upload_template.save(
                "Budget Upload Template.xls",
                File(f, name="Budget Upload Template.xls"),
                save=True,
            )

        site_settings.save()

    def add_countries_and_regions(self):
        west_africa = Region.objects.create(name="West Africa", region_code="WA")
        east_africa = Region.objects.create(name="East Africa", region_code="EA")
        asia = Region.objects.create(name="Asia", region_code="AS")
        middle_east = Region.objects.create(name="Middle East", region_code="ME")
        self.countries = {
            "Bangladesh": Country.objects.create(name="Bangladesh", code="BD", region=asia),
            "Jordan": Country.objects.create(name="Jordan", code="JO", region=middle_east),
            "Niger": Country.objects.create(name="Niger", code="NE", region=west_africa),
            "Yemen": Country.objects.create(name="Yemen", code="YE", region=east_africa),
            "Iraq": Country.objects.create(name="Iraq", code="IQ", region=middle_east),
            "Lebanon": Country.objects.create(name="Lebanon", code="LB", region=middle_east),
            "Liberia": Country.objects.create(name="Liberia", code="LR", region=west_africa),
            "Somalia": Country.objects.create(name="Somalia", code="SO", region=east_africa),
            "Ethiopia": Country.objects.create(name="Ethiopia", code="ET", region=east_africa),
            "Mali": Country.objects.create(name="Mali", code="ML", region=west_africa),
            "Burundi": Country.objects.create(name="Burundi", code="BI", region=west_africa),
            "Tanzania": Country.objects.create(name="Tanzania", code="TZ", region=east_africa),
            "Kenya": Country.objects.create(name="Kenya", code="KE", region=east_africa),
            "Myanmar": Country.objects.create(name="Myanmar", code="MM", region=asia),
            "DR Congo": Country.objects.create(
                name="Democratic Republic of Congo", code="CD", region=west_africa
            ),
            "Pakistan": Country.objects.create(name="Pakistan", code="PK", region=asia),
            "Afghanistan": Country.objects.create(name="Afghanistan", code="AF", region=asia),
            "Chad": Country.objects.create(name="Chad", code="TD", region=west_africa),
            "Philippines": Country.objects.create(name="Philippines", code="PH", region=asia),
        }

    def add_categories(self, categories):
        self.categories[DEFAULT_CATEGORY["name"]] = Category.objects.create(order=0, **DEFAULT_CATEGORY)
        for i, category in enumerate(categories, start=1):
            self.categories[category["name"]] = Category.objects.create(order=i, **category)

    def add_cost_types(self, cost_types):
        self.cost_types[DEFAULT_COST_TYPE["name"]] = CostType.objects.create(order=0, **DEFAULT_COST_TYPE)

        for i, cost_type in enumerate(cost_types, start=1):
            self.cost_types[cost_type["name"]] = CostType.objects.create(order=i, **cost_type)

    def add_cost_type_category_mappings(self, mappings):
        for sector_code, account_code, category_name, cost_type_name in mappings:
            data = {}
            if sector_code:
                data["sector_code"] = sector_code
            if account_code:
                data["account_code"] = account_code
            if category_name:
                data["category"] = self.categories[category_name]
            if cost_type_name:
                data["cost_type"] = self.cost_types[cost_type_name]

            CostTypeCategoryMapping.objects.create(**data)

    def add_analysis_types(self):
        self.analysis_types = {
            "Actual spending data": AnalysisType.objects.create(title="Actual spending data"),
            "Budget projection data": AnalysisType.objects.create(title="Budget projection data"),
        }

    def add_interventions(self):
        groups = [
            "Cash",
            "Community",
            "Economic",
            "Education",
            "Environment",
            "Health",
            "Protection",
        ]
        for group_name in groups:
            self.groups[group_name] = InterventionGroup.objects.create(name=group_name)

        for each in INTERVENTIONS:
            if each.get("group"):
                each["group"] = self.groups[each["group"]]

            # Some checks to make sure we are creating valid interventions
            for each_output_metric in each["output_metrics"]:
                assert (
                    each_output_metric in OUTPUT_METRICS_BY_ID
                ), f"{each_output_metric} is not defined as an OutputMetric in Intervention: {each['name']}"

            self.interventions[each["name"]] = Intervention.objects.create(**each)

    @staticmethod
    def add_cost_efficiency_strategies():
        columns = [
            "intervention_name",
            "title",
            "efficiency_driver_description",
            "strategy_to_improve_description",
        ]

        path = THIS_DIR / "build_content" / "cost_efficiency_strategies.csv"
        with open(path) as csv_file:
            next(csv_file)  # Skip header.
            next(csv_file)  # Skip header.
            reader = csv.DictReader(csv_file, fieldnames=columns)
            row: dict
            for row in reader:
                intervention_name = row.pop("intervention_name")
                try:
                    intervention = Intervention.objects.get(name=intervention_name)
                except Intervention.DoesNotExist as e:
                    print(
                        f'Intervention Not Found: "{intervention_name}" while loading Cost Efficiency Strategies'
                    )
                    raise e

                row["efficiency_driver_description"] = f"<p>{row['efficiency_driver_description']}</p>"
                row["strategy_to_improve_description"] = f"<p>{row['strategy_to_improve_description']}</p>"
                strategy = CostEfficiencyStrategy.objects.create(**row)
                strategy.interventions.add(intervention)
                strategy.save()

    def add_analyses(self):
        bangladesh_fund = Analysis.objects.create(
            title="DF119 WPE CM Jordan (April 2015)",
            analysis_type=self.analysis_types["Actual spending data"],
            description="Insight into the cost of operating individual WPE CM in Women's Centres in Jordan",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=self.countries["Jordan"],
            grants="DF119",
            owner=User.objects.get(name="Caitlin Tulloch"),
        )
        bangladesh_fund.add_intervention(
            self.interventions["GBV Case Management"],
            parameters={
                "number_of_people": 2992,
            },
        )
        self._import_sample_transactions_and_clis_to_analysis(
            bangladesh_fund,
            "transaction_max_3k_sorted.csv",
            only_grant_codes=["DF119"],
        )

        jordan_fund = Analysis.objects.create(
            title="DF168 Cash Transfer Program for Syrian Refugees in Iraq - (Q3-Q4 2017)",
            analysis_type=self.analysis_types["Actual spending data"],
            description="Delivering Humanitarian Assistance and Building Resilience for "
            "Conflict-Affected Populations in Syria",
            start_date=datetime.date(2017, 7, 1),
            end_date=datetime.date(2017, 12, 31),
            country=self.countries["Iraq"],
            grants="DF168",
            owner=User.objects.get(name="Akmal Shah"),
        )
        jordan_fund.add_intervention(
            self.interventions["Unconditional Cash Transfer"],
            parameters={
                "number_of_households": 10,
                "value_of_cash_distributed": 10_000,
            },
        )
        self._import_sample_transactions_and_clis_to_analysis(
            jordan_fund,
            "transaction_max_3k_sorted.csv",
            only_grant_codes=["DF168"],
        )

        yemen_fund = Analysis.objects.create(
            title="USAID Liberia PACS Model-GT (2015)",
            analysis_type=self.analysis_types["Actual spending data"],
            description="PACS Model-GT",
            start_date=datetime.date(2015, 2, 1),
            end_date=datetime.date(2016, 7, 27),
            country=self.countries["Liberia"],
            grants="GA298",
            owner=User.objects.get(name="Takhani Kromah"),
        )
        yemen_fund.add_intervention(
            self.interventions["General Program"],
            parameters={
                "number_of_outputs": 10000,
            },
        )
        self._import_sample_transactions_and_clis_to_analysis(
            yemen_fund,
            "transaction_max_3k_sorted.csv",
            only_grant_codes=["GA298"],
        )

        ydp_philippines = Analysis.objects.create(
            title="DFID CCI IRC Legal Aid (September 2017)",
            analysis_type=self.analysis_types["Budget projection data"],
            description="CCI IRC legal aid analysis",
            start_date=datetime.date(2017, 9, 1),
            end_date=datetime.date(2018, 6, 30),
            country=self.countries["Iraq"],
            grants="Unknown",
            owner=User.objects.get(name="Akmal Shah"),
        )
        ydp_philippines.add_intervention(
            self.interventions["Legal Aid Case Management"],
            parameters={
                "number_of_people": 890,
            },
        )
        self._import_cost_line_items_from_file(ydp_philippines, "DF186 Budget Upload.csv")
        ydp_philippines.auto_categorize_cost_line_items()
        ydp_philippines.ensure_cost_type_category_objects()

        cash_iraq = Analysis.objects.create(
            title="DFID CCI IRC Cash Transfer Program (September 2017)",
            analysis_type=self.analysis_types["Budget projection data"],
            description="CCI IRC Cash Transfer Program",
            start_date=datetime.date(2017, 9, 1),
            end_date=datetime.date(2018, 6, 30),
            country=self.countries["Iraq"],
            grants="Unknown",
            owner=User.objects.get(name="Akmal Shah"),
        )
        cash_iraq.add_intervention(
            self.interventions["Unconditional Cash Transfer"],
            parameters={
                "number_of_households": 10,
                "value_of_cash_distributed": 10_000,
            },
        )
        self._import_cost_line_items_from_file(cash_iraq, "DF186 Budget Upload.csv")
        cash_iraq.auto_categorize_cost_line_items()
        cash_iraq.ensure_cost_type_category_objects()

        small_analysis = Analysis.objects.create(
            title="A Small Test Analysis",
            analysis_type=self.analysis_types["Budget projection data"],
            description="A much smaller test analysis for debugging",
            start_date=datetime.date(2023, 1, 15),
            end_date=datetime.date(2023, 6, 30),
            country=self.countries["Mali"],
            grants="Unknown",
            owner=User.objects.get(name="Akmal Shah"),
        )
        small_analysis.add_intervention(
            self.interventions["Unconditional Cash Transfer"],
            parameters={
                "number_of_households": 10,
                "value_of_cash_distributed": 10_000,
            },
        )
        self._import_cost_line_items_from_file(small_analysis, "Small Analysis Sample Budget Upload.xlsx")
        small_analysis.auto_categorize_cost_line_items()
        small_analysis.ensure_cost_type_category_objects()

        CostLineItemConfig.objects.filter(cost_line_item__analysis_id=small_analysis.id).filter(
            id__in=small_analysis.cost_line_items.values_list("id", flat=True)
        ).update(
            cost_type=self.cost_types["Program Costs"],
            category=self.categories["National Staff"],
        )
        small_analysis.ensure_cost_type_category_objects()
        self.add_debug_analyses()

    def add_debug_analyses(self):
        # Step 1
        analysis_step1 = Analysis.objects.create(
            title="Sample Analysis - Step 1 (Define) Complete",
            analysis_type=self.analysis_types["Budget projection data"],
            description="Lorem ipsum dolor sit amet, consectetur "
            "adipiscing elit, sed do eiusmod tempor "
            "incididunt ut labore et dolore magna aliqua."
            " Ut enim ad minim veniam, quis nostrud "
            "exercitation ullamco laboris nisi ut aliquip "
            "ex ea commodo consequat. Duis aute irure dolor "
            "in reprehenderit in voluptate velit esse cillum "
            "dolore eu fugiat nulla pariatur. Excepteur sint "
            "occaecat cupidatat non proident, sunt in culpa "
            "qui officia deserunt mollit anim id est laborum.",
            start_date=datetime.date(2023, 1, 15),
            end_date=datetime.date(2023, 6, 30),
            country=self.countries["Mali"],
            grants="Unknown",
            owner=User.objects.get(name="Akmal Shah"),
        )
        analysis_step1.add_intervention(
            self.interventions["Unconditional Cash Transfer"],
            parameters={
                "number_of_households": 10,
                "value_of_cash_distributed": 10_000,
            },
        )
        _check_analysis_status(analysis_step1, "define")

        # Step 1 - Multi
        analysis_step1_multi = clone_analysis(analysis_step1.pk, User.objects.get(name="Akmal Shah"))
        analysis_step1_multi.title = analysis_step1.title + " (Multiple Interventions)"
        analysis_step1_multi.add_intervention(
            self.interventions["GBV Case Management"],
            parameters={
                "number_of_people": 2992,
            },
        )
        analysis_step1_multi.save()
        _check_analysis_status(analysis_step1_multi, "define")

        # ##########################
        # Step 2
        analysis_step2 = clone_analysis(analysis_step1.pk, User.objects.get(name="Akmal Shah"))
        analysis_step2.title = "Sample Analysis - Step 2 (Load Data) Complete"

        self._import_cost_line_items_from_file(
            analysis_step2,
            "10 Item Sample Analysis Budget Upload_simple.xlsx",
        )

        # This call is here to make sure that every cost line item has a config.
        analysis_step2.auto_categorize_cost_line_items()
        analysis_step2.save()
        analysis_step2.ensure_cost_type_category_objects()

        _check_analysis_status(analysis_step2, "load-data")

        # Step 2 - Multi
        analysis_step2_multi = clone_analysis(analysis_step2.pk, User.objects.get(name="Akmal Shah"))
        analysis_step2_multi.title = analysis_step2.title + " (Multiple Interventions)"
        analysis_step2_multi.add_intervention(
            self.interventions["GBV Case Management"],
            parameters={
                "number_of_people": 2992,
            },
        )
        analysis_step2_multi.save()
        _check_analysis_status(analysis_step2_multi, "load-data")

        # ##########################
        # Step 3
        analysis_step3 = clone_analysis(analysis_step2.pk, User.objects.get(name="Akmal Shah"))
        analysis_step3.title = "Sample Analysis - Step 3 (Confirm Categories) Complete"

        for cost_type_category in analysis_step3.cost_type_categories.all():
            cost_type_category.confirmed = True
            cost_type_category.save()
        analysis_step3.ensure_cost_type_category_objects()
        analysis_step3.save()
        _check_analysis_status(analysis_step3, "categorize")

        # Step 3 - Multi
        analysis_step3_multi = clone_analysis(analysis_step3.pk, User.objects.get(name="Akmal Shah"))
        analysis_step3_multi.title = analysis_step3.title + " (Multiple Interventions)"
        analysis_step3_multi.add_intervention(
            self.interventions["GBV Case Management"],
            parameters={
                "number_of_people": 2992,
            },
        )
        analysis_step3_multi.save()
        _check_analysis_status(analysis_step3_multi, "categorize")

        # ##########################
        # Step 4
        analysis_step4 = clone_analysis(analysis_step3.pk, User.objects.get(name="Akmal Shah"))
        analysis_step4.title = "Sample Analysis - Step 4 (Allocate) Complete - Main Flow Complete"

        for cost_line_item in analysis_step4.cost_line_items.all():
            for each_intervention_instance in analysis_step4.interventioninstance_set.all():
                allocation = CostLineItemInterventionAllocation(
                    intervention_instance=each_intervention_instance,
                    allocation=Decimal("4"),
                    cli_config=cost_line_item.config,
                )
                allocation.save()

        analysis_step4.save()
        _check_analysis_status(analysis_step4, "insights")

        # Step 4 - Multi
        analysis_step4_multi = clone_analysis(analysis_step3_multi.pk, User.objects.get(name="Akmal Shah"))
        analysis_step4_multi.title = analysis_step4.title + " (Multiple Interventions)"

        for cost_line_item in analysis_step4_multi.cost_line_items.all():
            for scg in analysis_step4_multi.cost_type_category_grants.all():
                for each_intervention in analysis_step4_multi.interventioninstance_set.all():
                    if (
                        cost_line_item.config.cost_type == scg.cost_type_category.cost_type
                        and cost_line_item.config.category == scg.cost_type_category.category
                    ):
                        allocation = CostLineItemInterventionAllocation(
                            intervention_instance=each_intervention,
                            allocation=Decimal("4"),
                            cli_config=cost_line_item.config,
                        )
                        allocation.save()
        analysis_step4_multi.save()
        _check_analysis_status(analysis_step4_multi, "insights")

        self.add_debug_analysis_completed_with_transactions()
        self.add_debug_analysis_completed_with_multiple_grants()
        self.add_debug_analysis_with_shared_costs()
        self.add_debug_analyses_with_multiple_intervention()
        self.add_client_provided_multiintervention_analysis()
        self.add_client_provided_multiintervention_analysis_more_complete()

        ###########################
        # Add Other Cost Line Items step

        analysis_step4a = clone_analysis(analysis_step4_multi.id, User.objects.get(name="Akmal Shah"))
        analysis_step4a.title = (
            "Sample Analysis - Step 4a (Add Other Cost Line Items) (Multiple Interventions)"
        )
        analysis_step4a.other_hq_costs = True
        analysis_step4a.in_kind_contributions = True
        analysis_step4a.client_time = True
        analysis_step4a.save()

    def add_debug_analysis_completed_with_transactions(self):
        analysis_with_transactions = Analysis.objects.create(
            title="Sample Analysis - Main Flow Complete - With Transactions",
            analysis_type=self.analysis_types["Budget projection data"],
            description="Lorem ipsum dolor sit amet, consectetur "
            "adipiscing elit, sed do eiusmod tempor "
            "incididunt ut labore et dolore magna aliqua."
            " Ut enim ad minim veniam, quis nostrud "
            "exercitation ullamco laboris nisi ut aliquip "
            "ex ea commodo consequat. Duis aute irure dolor "
            "in reprehenderit in voluptate velit esse cillum "
            "dolore eu fugiat nulla pariatur. Excepteur sint "
            "occaecat cupidatat non proident, sunt in culpa "
            "qui officia deserunt mollit anim id est laborum.",
            start_date=datetime.date(2023, 1, 15),
            end_date=datetime.date(2023, 6, 30),
            country=self.countries["Mali"],
            grants="Unknown",
            owner=User.objects.get(name="Akmal Shah"),
        )

        analysis_with_transactions.add_intervention(
            self.interventions["Unconditional Cash Transfer"],
            parameters={
                "number_of_households": 10,
                "value_of_cash_distributed": 10_000,
            },
        )

        self._import_sample_transactions_and_clis_to_analysis(
            analysis_with_transactions,
            "transactions_10_entries.csv",
            only_grant_codes=["ER342"],
        )

        analysis_with_transactions.auto_categorize_cost_line_items()
        analysis_with_transactions.ensure_cost_type_category_objects()
        analysis_with_transactions.save()

        for cost_type_category in analysis_with_transactions.cost_type_categories.all():
            cost_type_category.confirmed = True
            cost_type_category.save()

        for cost_line_item in analysis_with_transactions.cost_line_items.all():
            for each_intervention_instance in analysis_with_transactions.interventioninstance_set.all():
                allocation = CostLineItemInterventionAllocation(
                    intervention_instance=each_intervention_instance,
                    allocation=Decimal("4"),
                    cli_config=cost_line_item.config,
                )
                allocation.save()

        _check_analysis_status(analysis_with_transactions, "insights")

    def add_debug_analysis_completed_with_multiple_grants(self):
        analysis = Analysis.objects.create(
            title="Sample Analysis - Main Flow Complete - With Transactions and Multiple Grants",
            analysis_type=self.analysis_types["Budget projection data"],
            description="Lorem ipsum",
            start_date=datetime.date(2023, 1, 15),
            end_date=datetime.date(2023, 6, 30),
            country=self.countries["Mali"],
            grants=["GA298", "FFFFF"],
            owner=User.objects.get(name="Akmal Shah"),
        )

        analysis.add_intervention(
            self.interventions["Unconditional Cash Transfer"],
            parameters={
                "number_of_households": 10,
                "value_of_cash_distributed": 10_000,
            },
        )

        self._import_sample_transactions_and_clis_to_analysis(
            analysis,
            "transactions_10_entries_multi_grant.csv",
        )

        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()
        analysis.save()

        for cost_type_category in analysis.cost_type_categories.all():
            cost_type_category.confirmed = True
            cost_type_category.save()

        for cost_line_item in analysis.cost_line_items.all():
            for each_intervention_instance in analysis.interventioninstance_set.all():
                allocation = CostLineItemInterventionAllocation(
                    intervention_instance=each_intervention_instance,
                    allocation=Decimal("4"),
                    cli_config=cost_line_item.config,
                )
                allocation.save()

        _check_analysis_status(analysis, "insights")

    def add_debug_analysis_with_shared_costs(self):
        analysis = Analysis.objects.create(
            title="Sample Analysis - Main Flow Complete - With Shared Costs",
            analysis_type=self.analysis_types["Budget projection data"],
            description="Lorem ipsum dolor sit amet, consectetur "
            "adipiscing elit, sed do eiusmod tempor "
            "incididunt ut labore et dolore magna aliqua."
            " Ut enim ad minim veniam, quis nostrud "
            "exercitation ullamco laboris nisi ut aliquip "
            "ex ea commodo consequat. Duis aute irure dolor "
            "in reprehenderit in voluptate velit esse cillum "
            "dolore eu fugiat nulla pariatur. Excepteur sint "
            "occaecat cupidatat non proident, sunt in culpa "
            "qui officia deserunt mollit anim id est laborum.",
            start_date=datetime.date(2023, 1, 15),
            end_date=datetime.date(2023, 6, 30),
            country=self.countries["Mali"],
            grants="Unknown",
            owner=User.objects.get(name="Akmal Shah"),
        )
        analysis.add_intervention(
            self.interventions["Unconditional Cash Transfer"],
            parameters={
                "number_of_households": 10,
                "value_of_cash_distributed": 10_000,
            },
        )

        self._import_cost_line_items_from_file(
            analysis,
            "10 Item Sample Analysis Budget Upload_simple.xlsx",
        )

        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()
        analysis.save()

        for cost_type_category in analysis.cost_type_categories.all():
            cost_type_category.confirmed = True
            cost_type_category.save()

        for cost_line_item in analysis.cost_line_items.all():
            for each_intervention_instance in analysis.interventioninstance_set.all():
                allocation = CostLineItemInterventionAllocation(
                    intervention_instance=each_intervention_instance,
                    allocation=Decimal("4"),
                    cli_config=cost_line_item.config,
                )
                allocation.save()

    def add_debug_analyses_with_multiple_intervention(self):
        analysis = Analysis.objects.create(
            title="Sample Analysis - Main Flow Complete - Multiple Interventions With Transactions",
            analysis_type=self.analysis_types["Budget projection data"],
            description="Lorem ipsum dolor sit amet, consectetur "
            "adipiscing elit, sed do eiusmod tempor "
            "incididunt ut labore et dolore magna aliqua.",
            start_date=datetime.date(2023, 1, 15),
            end_date=datetime.date(2023, 6, 30),
            country=self.countries["Mali"],
            grants="Unknown",
            owner=User.objects.get(name="Akmal Shah"),
        )

        analysis.add_intervention(
            self.interventions["Unconditional Cash Transfer"],
            parameters={
                "number_of_households": 10,
                "value_of_cash_distributed": 10_000,
            },
        )
        analysis.add_intervention(
            self.interventions["GBV Case Management"],
            parameters={
                "number_of_people": 2992,
            },
        )

        self._import_sample_transactions_and_clis_to_analysis(
            analysis,
            "transactions_10_entries.csv",
            only_grant_codes=["GA298"],
        )

        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()
        analysis.save()
        for cost_type_category in analysis.cost_type_categories.all():
            cost_type_category.confirmed = True
            cost_type_category.save()

        for cost_line_item in analysis.cost_line_items.all():
            for each_intervention_instance in analysis.interventioninstance_set.all():
                allocation = CostLineItemInterventionAllocation(
                    intervention_instance=each_intervention_instance,
                    allocation=Decimal("4"),
                    cli_config=cost_line_item.config,
                )
                allocation.save()

    def add_client_provided_multiintervention_analysis(self):
        analysis = Analysis.objects.create(
            title="Multi-Intervention Analysis Spreadsheet (#44200) @ Beginning",
            analysis_type=self.analysis_types["Budget projection data"],
            description="Sample Multi-Intervention Analysis",
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 6, 30),
            country=self.countries["Niger"],
            grants="EC485",
            owner=User.objects.get(name="Akmal Shah"),
            currency_code="USD",
            in_kind_contributions=True,
            client_time=True,
        )

        analysis.add_intervention(
            self.interventions["General Program"],
            label="Learning Model",
            parameters={
                "number_of_outputs": 800,
            },
        )
        analysis.add_intervention(
            self.interventions["General Program"],
            label="Tutoring",
            parameters={
                "number_of_outputs": 500,
            },
        )
        analysis.add_intervention(
            self.interventions["Teacher Professional Development"],
            label="Teacher Professional Development",
            parameters={
                "number_of_teachers": 200,
                "number_of_years_of_support": 2,
            },
        )
        self._import_cost_line_items_from_file(
            analysis,
            "multiple_intervention_demo_clis.csv",
        )
        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()
        analysis.save()
        _check_analysis_status(analysis, "load-data")

    def add_client_provided_multiintervention_analysis_more_complete(self):
        analysis = Analysis.objects.create(
            title="Multi-Intervention Analysis Spreadsheet (#44200) More Complete",
            analysis_type=self.analysis_types["Budget projection data"],
            description="Sample Multi-Intervention Analysis",
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 6, 30),
            country=self.countries["Niger"],
            grants="EC485",
            owner=User.objects.get(name="Akmal Shah"),
            currency_code="USD",
            in_kind_contributions=True,
            client_time=True,
        )

        analysis.add_intervention(
            self.interventions["General Program"],
            label="Learning Model",
            parameters={
                "number_of_outputs": 800,
            },
        )
        analysis.add_intervention(
            self.interventions["General Program"],
            label="Tutoring",
            parameters={
                "number_of_outputs": 500,
            },
        )
        analysis.add_intervention(
            self.interventions["Teacher Professional Development"],
            label="Teacher Professional Development",
            parameters={
                "number_of_teachers": 200,
                "number_of_years_of_support": 2,
            },
        )
        self._import_cost_line_items_from_file(
            analysis,
            "multiple_intervention_demo_clis.csv",
        )

        # The key is the sector_code and the description
        cost_line_item_info = {
            ("EGNB", "Education Coordinator"): {
                "cost_type": "Program Costs",
                "category": "National Staff",
                "allocations": {
                    "Learning Model": "20",
                    "Tutoring": "20",
                    "Teacher Professional Development": "20",
                },
            },
            ("EGNB", "Education Manager"): {
                "cost_type": "Program Costs",
                "category": "National Staff",
                "allocations": {
                    "Learning Model": "30",
                    "Tutoring": "15",
                    "Teacher Professional Development": "25",
                },
            },
            ("EGNB", "M&E Manager"): {
                "cost_type": "Program Costs",
                "category": "National Staff",
                "allocations": {
                    "Learning Model": "10",
                    "Tutoring": "10",
                    "Teacher Professional Development": "25",
                },
            },
            ("CYGE", "Child Protection Manager"): {
                "cost_type": "Program Costs",
                "category": "National Staff",
                "allocations": {
                    "Learning Model": "40",
                    "Tutoring": "0",
                    "Teacher Professional Development": "20",
                },
            },
            ("CYGE", "Child Protection Officer"): {
                "cost_type": "Program Costs",
                "category": "National Staff",
                "allocations": {
                    "Learning Model": "50",
                    "Tutoring": "0",
                    "Teacher Professional Development": "25",
                },
            },
            ("EGNB", "Teacher Stipends"): {
                "cost_type": "Program Costs",
                "category": "Materials & Activities",
                "allocations": {
                    "Learning Model": "0",
                    "Tutoring": "70",
                    "Teacher Professional Development": "0",
                },
            },
            ("EGNB", "Student identification and enrollment "): {
                "cost_type": "Program Costs",
                "category": "Materials & Activities",
                "allocations": {
                    "Learning Model": "60",
                    "Tutoring": "40",
                    "Teacher Professional Development": "0",
                },
            },
            ("EGNB", "Training/Refresher Tutors and Reservists"): {
                "cost_type": "Program Costs",
                "category": "Materials & Activities",
                "allocations": {
                    "Learning Model": "20",
                    "Tutoring": "50",
                    "Teacher Professional Development": "30",
                },
            },
            ("EGNB", "Teacher Learning Circles"): {
                "cost_type": "Program Costs",
                "category": "Materials & Activities",
                "allocations": {
                    "Learning Model": "0",
                    "Tutoring": "0",
                    "Teacher Professional Development": "100",
                },
            },
            ("EGNB", "M&E cost"): {
                "cost_type": "Program Costs",
                "category": "Materials & Activities",
                "allocations": {
                    "Learning Model": "10",
                    "Tutoring": "10",
                    "Teacher Professional Development": "25",
                },
            },
            ("CYGE", "Incentive for SHLS facilitators"): {
                "cost_type": "Program Costs",
                "category": "Materials & Activities",
                "allocations": {
                    "Learning Model": "100",
                    "Tutoring": "0",
                    "Teacher Professional Development": "0",
                },
            },
            ("CYGE", "SHLS infrastructure Rehabilitation"): {
                "cost_type": "Program Costs",
                "category": "Materials & Activities",
                "allocations": {
                    "Learning Model": "100",
                    "Tutoring": "0",
                    "Teacher Professional Development": "0",
                },
            },
            ("CYGE", "Establishment of referral pathways"): {
                "cost_type": "Program Costs",
                "category": "Materials & Activities",
                "allocations": {
                    "Learning Model": "40",
                    "Tutoring": "60",
                    "Teacher Professional Development": "0",
                },
            },
            ("EGNB", "Travel"): {
                "cost_type": "Program Costs",
                "category": "Travel & Transport",
                "allocations": {
                    "Learning Model": "10",
                    "Tutoring": "0",
                    "Teacher Professional Development": "25",
                },
            },
            ("CYGE", "Travel"): {
                "cost_type": "Program Costs",
                "category": "Travel & Transport",
                "allocations": {
                    "Learning Model": "50",
                    "Tutoring": "20",
                    "Teacher Professional Development": "0",
                },
            },
            ("OADF", "Country Director"): {
                "cost_type": "Support Costs",
                "category": "International Staff",
            },
            ("OADF", "Deputy Director of Programs"): {
                "cost_type": "Support Costs",
                "category": "National Staff",
            },
            ("OADF", "Finance Controller"): {
                "cost_type": "Support Costs",
                "category": "National Staff",
            },
            ("OADF", "Grants Coordinator"): {
                "cost_type": "Support Costs",
                "category": "National Staff",
            },
            ("OADF", "Vehicles"): {
                "cost_type": "Support Costs",
                "category": "Travel & Transport",
            },
            ("OADF", "Office and warehouse rent"): {
                "cost_type": "Support Costs",
                "category": "Office Expenses",
            },
            ("OADF", "Office utilities and maintenance"): {
                "cost_type": "Support Costs",
                "category": "Office Expenses",
            },
            ("", "Indirect costs (7%)"): {
                "cost_type": "Indirect Costs",
                "category": "Indirect Costs",
            },
        }

        for cost_line_item in analysis.cost_line_items.all():
            CostLineItemConfig.objects.get_or_create(cost_line_item=cost_line_item)
            cost_type_and_category = cost_line_item_info[
                (cost_line_item.sector_code, cost_line_item.budget_line_description)
            ]
            cost_line_item.config.cost_type = self.cost_types[cost_type_and_category["cost_type"]]
            cost_line_item.config.category = self.categories[cost_type_and_category["category"]]
            cost_line_item.config.save()
        analysis.ensure_cost_type_category_objects()

        for cost_type_category in analysis.cost_type_categories.all():
            cost_type_category.confirmed = True
            cost_type_category.save()

        for cost_line_item in analysis.cost_line_items.all():
            allocation_percents = cost_line_item_info[
                (cost_line_item.sector_code, cost_line_item.budget_line_description)
            ].get("allocations", {})

            for each_intervention_instance in analysis.interventioninstance_set.all():
                if each_intervention_instance.label in allocation_percents:
                    allocation = CostLineItemInterventionAllocation(
                        intervention_instance=each_intervention_instance,
                        allocation=allocation_percents[each_intervention_instance.label],
                        cli_config=cost_line_item.config,
                    )
                    allocation.save()

        analysis.save()

    @betterdb.transaction()
    def _import_sample_transactions_and_clis_to_analysis(
        self,
        analysis: Analysis,
        filename: str,
        only_grant_codes: list[str] | None = None,
    ):
        columns = [
            "date",
            "country_code",
            "grant_code",
            "budget_line_code",
            "account_code",
            "site_code",
            "sector_code",
            "transaction_code",
            "transaction_description",
            "currency_code",
            "budget_line_description",
            "amount_in_source_currency",
            "dummy_field_1",
            "dummy_field_2",
            "dummy_field_3",
            "dummy_field_4",
            "dummy_field_5",
        ]

        path = THIS_DIR / "build_content" / filename
        with open(path) as csv_file:
            bulk = BulkCreateManager()
            next(csv_file)  # Skip header.
            reader = csv.DictReader(csv_file, fieldnames=columns)
            row: dict
            for row in reader:
                if only_grant_codes and row["grant_code"] not in only_grant_codes:
                    continue

                # Add analysis.
                row["analysis"] = analysis

                # Remove extra whitespace.
                for field, value in row.items():
                    if isinstance(value, str):
                        row[field] = value.strip()
                    elif value is None:
                        row[field] = ""  # Columns are non-nullable

                # Cast currency to Decimal, take absolute value until incoming transactions are no longer negative.
                row["amount_in_source_currency"] = abs(Decimal(row["amount_in_source_currency"]))
                row["amount_in_instance_currency"] = row["amount_in_source_currency"]

                bulk.add(Transaction(**row))
            bulk.done()
        analysis.source = Analysis.DATA_STORE_NAME
        analysis.save()

        analysis.create_cost_line_items_from_transactions()
        analysis.auto_categorize_cost_line_items()
        analysis.ensure_cost_type_category_objects()

    @staticmethod
    def _import_cost_line_items_from_file(analysis, filename):
        with open(THIS_DIR / "build_content" / filename, "rb") as f:
            load_cost_line_items_from_file(analysis, f)

    @staticmethod
    def add_account_code_descriptions():
        columns = [
            "account_code",
            "account_description",
        ]

        path = THIS_DIR / "build_content" / "account_code_descriptions.csv"
        with open(path) as csv_file:
            next(csv_file)  # Skip header.
            reader = csv.DictReader(csv_file, fieldnames=columns)
            row: dict
            for row in reader:
                AccountCodeDescription.objects.create(**row)

    @staticmethod
    def add_insight_comparison_data():
        columns = [
            "name",
            "country",
            "grants",
            "intervention",
            "output_count",
            "cost_direct_only",
            "cost_all",
        ]

        path = THIS_DIR / "build_content" / "insight_comparison_data.csv"
        with open(path) as csv_file:
            next(csv_file)  # Skip first row
            reader = csv.DictReader(csv_file, fieldnames=columns)
            row: dict
            for row in reader:
                try:
                    row["country"] = Country.objects.get(name=row["country"])

                    try:
                        intervention = Intervention.objects.get(name=row["intervention"])
                        row["intervention"] = intervention
                    except Intervention.DoesNotExist as e:
                        print(
                            f"Intervention Not Found: \"{row['intervention']}\" while loading Insight Comparison Data"
                        )
                        raise e

                    output_count = row.pop("output_count")
                    output_count = output_count.split(";")

                    row["parameters"] = {}
                    row["output_costs"] = {}

                    for output_metric in intervention.output_metric_objects():
                        try:
                            for i, parameter_key in enumerate(output_metric.parameters):
                                row["parameters"][parameter_key] = int(clean_csv_number(output_count[i]))
                        except IndexError:
                            print(
                                f"Not enough parameters for: {output_metric}.  Expected: {list(output_metric.parameters.keys())} got: {output_count}"
                            )
                            raise
                        row["output_costs"][output_metric.id] = {
                            "direct_only": float(parse_csv_currency_to_decimal(row["cost_direct_only"])),
                            "all": float(parse_csv_currency_to_decimal(row["cost_all"])),
                        }
                    row.pop("cost_direct_only")
                    row.pop("cost_all")

                except Exception as e:
                    print(row)
                    raise e

                InsightComparisonData.objects.create(**row)

    def add_assets(self):
        asset_captions = {
            "help-page-rte-image.png": "Ship of the imagination in a cosmic arena "
            "courage of our questions vastness is bearable "
            "only through love with pretty stories for "
            "which there's little good evidence "
            "inconspicuous motes of rock and gas"
        }

        asset_files = THIS_DIR / "build_content" / "assets"

        images = asset_files / "images"
        ext_types = get_available_image_extensions()
        for i in images.iterdir():
            if i.suffix.lstrip(".") in ext_types:
                img_asset = ImageAsset(
                    title=i.name.replace(i.suffix, ""),
                    caption=asset_captions.get(i.name, ""),
                )
                with open(str(i), "rb") as f:
                    img_asset.image = File(f, name=i.name)
                    img_asset.save()
                self.log(f": Imported {i.name} to image assets")

    def log(self, msg: str, level: str = "NOTICE") -> None:
        if hasattr(self.style, level):
            msg = getattr(self.style, level)(msg)
        self.stdout.write(msg)
