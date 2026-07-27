import json
from decimal import Decimal
from decimal import DecimalException
from html import unescape

from django import forms
from django import template
from django.db.models import Q

from ombucore.admin.widgets import FlatpickrDateWidget
from website.models import AccountCodeDescription, CostLineItem
from website.models.cost_line_item import CostLineItemInterventionAllocation
from website.models.query_utils import require_prefetch

register = template.Library()


@register.filter
def sum_cost_line_items(cost_line_items):
    return sum(cost_line_item.total_cost for cost_line_item in cost_line_items)


@register.filter
def contains_sensitive_data(cost_line_items):
    return AccountCodeDescription.objects.filter(
        account_code__in=(cost_line_item.account_code for cost_line_item in cost_line_items),
        sensitive_data=True,
    ).exists()


@register.filter
def dict_get(d, key):
    if d:
        return d.get(key)
    return None


@register.filter
def dict_get_as_str(d, key):
    key = str(key)
    if d:
        return d.get(key)
    return None


@register.filter
def attr(obj, attr_name):
    if obj:
        return getattr(obj, attr_name)
    return None


@register.filter
def is_flatpickr(field):
    return isinstance(field.field.widget, FlatpickrDateWidget)


@register.filter
def is_number_input(field):
    return isinstance(field.field.widget, forms.NumberInput)


@register.filter
def is_file_input(field):
    return isinstance(field.field.widget, forms.FileInput)


@register.filter
def is_hidden_input(field):
    return isinstance(field.field.widget, forms.HiddenInput)


@register.filter
def subtract(first, second):
    return first - second


@register.filter
def insights_chart_height(num_items):
    return (40 * num_items) + 52


@register.filter
def get_class_name(value):
    return type(value).__name__


@register.filter
def cost_line_items_by_category(qs, category):
    return [cli for cli in qs if cli.config.category == category]


@register.filter
def cost_line_items_by_category_for_subcomponent_analysis(qs, category):
    """
    Excludes cost items:
        – Other costs (Client Time, In-Kind Contributions, Other HQ Costs)
        – Support costs
        – Cost items that were set to 0% contribution in the Allocate Costs step
        – Identified as an Output Value
    """
    return (
        qs.filter(config__category=category)
        .exclude(config__analysis_cost_type__isnull=False)
        .exclude(Q(config__allocations__allocation=0) | Q(config__allocations__allocation__isnull=True))
    )


@register.filter
def error_in_category(errors, category):
    if not errors:
        return False
    return CostLineItem.objects.filter(id__in=list(errors.keys()), config__category=category).exists()


@register.filter
def lines_allocation_complete(cost_line_items):
    return cost_line_items.filter(config__allocations__allocation__isnull=True).count() == 0


@register.filter
def error_in_lump_sums(errors):
    if not errors:
        return False
    return CostLineItem.objects.filter(id__in=list(errors.keys())).exists()


@register.filter
def get_allocation_by_intervention_id(
    cost_line_item: CostLineItem,
    intervention_instance_id: int,
) -> CostLineItemInterventionAllocation:
    return cost_line_item.config.allocations.filter(intervention_instance_id=intervention_instance_id).first()


@register.filter
def subcomponent_allocation_for_intervention(cost_line_item: CostLineItem, intervention_instance):
    if not hasattr(intervention_instance, "subcomponent_cost_analysis"):
        return None

    subcomponent_analysis = intervention_instance.subcomponent_cost_analysis
    allocation_row = None
    for allocation in require_prefetch(cost_line_item.config, "subcomponent_cost_allocations"):
        if allocation.subcomponent_analysis_id == subcomponent_analysis.id:
            allocation_row = allocation
            break

    allocations = allocation_row.allocations if allocation_row else {}
    allocation_total = None
    if allocation_row and not allocation_row.skipped:
        allocation_total = sum(Decimal(value) for value in allocations.values())

    return {
        "analysis": subcomponent_analysis,
        "labels": [
            {
                "idx": idx,
                "label": label,
                "value": allocations.get(str(idx), ""),
            }
            for idx, label in enumerate(subcomponent_analysis.subcomponent_labels or [])
        ],
        "skipped": allocation_row.skipped if allocation_row else False,
        "total": allocation_total,
    }


@register.filter
def allocated_cost_for_percentage(cost_line_item: CostLineItem, percentage):
    if percentage is None:
        return Decimal(0)
    try:
        return cost_line_item.total_cost * (Decimal(percentage) / Decimal(100))
    except (DecimalException, TypeError, ValueError):
        return Decimal(0)


@register.filter(name="get_json")
def get_json(value):
    return json.loads(unescape(value))
