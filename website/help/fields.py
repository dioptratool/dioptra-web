from collections import namedtuple

from website.utils import Choices


class HelpItemType(Choices):
    CATEGORY = "category"
    COST_TYPE = "cost_type"
    STEP = "step"
    STEP_FIELD = "step_field"


HelpIdentifier = namedtuple("HelpIdentifier", "title identifier type ")

HELP_FIELDS = (
    HelpIdentifier(
        "Step Guidance / Define Analysis",
        "step_guidance__define_analysis",
        HelpItemType.STEP,
    ),
    HelpIdentifier(
        "Define Analysis / Title field",
        "define_analysis__title",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Define Analysis / Analysis type field",
        "define_analysis__analysis_type",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Define Analysis / Intervention to be analyzed field",
        "define_analysis__intervention_to_be_analyzed",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Define Analysis / Start date field",
        "define_analysis__start_date",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Define Analysis / Grants field",
        "define_analysis__grants",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Define Analysis / Country field",
        "define_analysis__country",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Define Analysis / Output count data source",
        "define_analysis__output_count_data_source",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier("Step Guidance / Load Data", "step_guidance__load_data", HelpItemType.STEP),
    HelpIdentifier(
        "Load Data / Matching transactions number",
        "load_data__matching_transactions",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Load Data / Download template link",
        "load_data__download_template",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Step Guidance / Assign Cost Type & Category",
        "step_guidance__assign_cost_type_category",
        HelpItemType.STEP,
    ),
    HelpIdentifier(
        "Assign Cost Type & Category / Cost Type column header",
        "assign_cost_type_category__cost_type",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Assign Cost Type & Category / Category column header",
        "assign_cost_type_category__category",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Step Guidance / Confirm Categories",
        "step_guidance__confirm_categories",
        HelpItemType.STEP,
    ),
    HelpIdentifier(
        "Confirm Categories / Edit cost type & category column header",
        "confirm_categories__edit_cost_type_category",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Step Guidance / Allocate Costs",
        "step_guidance__allocate_costs",
        HelpItemType.STEP,
    ),
    HelpIdentifier(
        "Allocate Costs / Assign allocation percent column header",
        "allocate_costs__assign_allocation_percent",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Allocate Costs / Apply to all link",
        "allocate_costs__apply_to_all",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Allocate Costs / Shared cost allocation estimate label",
        "allocate_costs__shared_cost_allocation_estimate",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Allocate Costs / ICR allocation estimate label",
        "allocate_costs__ICR_allocation_estimate",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Step Guidance / Identify Output Value",
        "step_guidance__identify_output_value",
        HelpItemType.STEP,
    ),
    HelpIdentifier(
        "Identify Output Value / IOV column header",
        "identify_output_value__IOV_column_header",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Insights / Cost per metric, direct costs only (blue box)",
        "insights__cost_per_metric_direct",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Insights / Cost per metric, including shared costs (green box)",
        "insights__cost_per_metric_shared",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Insights / Cost per metric, including shared costs and in-kind contributions (aqua box)",
        "insights__cost_per_metric_in_kind",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Insights / Comparison to similar programs header",
        "insights__comparison_to_similar_programs",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier("Insights / Strategies header", "insights__strategies", HelpItemType.STEP_FIELD),
    HelpIdentifier(
        "Insights / Top cost categories all other costs label",
        "insights__top_cost_categories_all_other_costs",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Insights / Full cost model download",
        "insights__full_cost_model",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Dashboard / Cost per Output header",
        "dashboard__cost_per_output",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Program Design Lessons / Cost Efficiency Comparison header",
        "program_design_lessons__cost_efficiency_comparison",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Program Design Lessons / Strategies header",
        "program_design_lessons__strategies",
        HelpItemType.STEP_FIELD,
    ),
    HelpIdentifier(
        "Sub-component / Suggested Allocations",
        "analysis-table__allocation_suggestions-heading",
        HelpItemType.STEP_FIELD,
    ),
)


HELP_CATEGORIES = (
    HelpIdentifier(
        "Confirm Categories / {category} category",
        "confirm_categories__{category}_category",
        HelpItemType.CATEGORY,
    ),
    HelpIdentifier(
        "Identify Output Value / {category} category",
        "identify_output_value__{category}_category",
        HelpItemType.CATEGORY,
    ),
    HelpIdentifier(
        "Allocate Costs / {category} category",
        "allocate_costs__{category}_category",
        HelpItemType.CATEGORY,
    ),
)

HELP_COST_TYPES = (
    HelpIdentifier(
        "Confirm Categories / {cost_type} cost type",
        "confirm_categories__{cost_type}_cost_type",
        HelpItemType.COST_TYPE,
    ),
    HelpIdentifier(
        "Identify Output Value / {cost_type} cost type",
        "identify_output_value__{cost_type}_cost_type",
        HelpItemType.COST_TYPE,
    ),
    HelpIdentifier(
        "Allocate Costs / {cost_type} cost type",
        "allocate_costs__{cost_type}_cost_type",
        HelpItemType.COST_TYPE,
    ),
)

HELP_IDENTIFIERS = {
    "field": HELP_FIELDS,
    "category": HELP_CATEGORIES,
    "cost_type": HELP_COST_TYPES,
}


def format_identifier(identifier, **kwargs):
    kwargs = {k: v.lower().replace(" ", "_") for k, v in kwargs.items()}
    identifier = identifier.format(**kwargs)
    return identifier


def format_title(title, **kwargs):
    title = title.format(**kwargs)
    return title


HELP_TOPICS = (
    "General",
    "Analysis",
    "Using Dioptra results",
    "Dioptra in Action",
    "Accounts and Permissions",
)
