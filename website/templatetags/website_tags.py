import json
from decimal import Decimal
from functools import lru_cache

import imagekit.templatetags.imagekit
import structlog
from babel.numbers import format_currency
from django import template
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from website.currency import (
    currency_name as get_currency_name,
    currency_symbol as get_currency_symbol,
    get_currency_locale,
)
from website.models import CostLineItem, InterventionGroup, InterventionInstance
from website.models.query_utils import require_prefetch
from website.models.utils import load_field_label_override

logger = structlog.get_logger(__name__)

register = template.Library()


@register.filter
def dict_to_json(dic):
    return json.dumps(dic)


@register.filter(name="chunks")
def chunks(iterable, chunk_size):
    iterable = iter(iterable)
    while True:
        chunk = []
        try:
            for _ in range(chunk_size):
                chunk.append(next(iterable))
            yield chunk
        except StopIteration:
            if chunk:
                yield chunk
            break


@register.filter
def exclude_field(form, exclude_field_name=None):
    """
    Provides an iterator over form fields that excludes the given field name.
    """
    for field in form:
        if field.name != exclude_field_name:
            yield field


@register.simple_tag
def get_intervention_groups():
    return InterventionGroup.objects.prefetch_related("interventions").all()


@register.filter
def label_override(default_label, field_name):
    return _(load_field_label_override(field_name, default_label))


@register.filter
def object_getattr(obj, attr_path, default=None):
    attributes = attr_path.split(".")
    for attr in attributes:
        obj = getattr(obj, attr, default)
        if obj is default:
            break
    return obj


@register.filter(name="format_currency")
def format_currency_filter(value, currency_override=settings.ISO_CURRENCY_CODE):
    if not isinstance(value, (int, float, Decimal)):
        return value
    if not currency_override:
        currency_override = settings.ISO_CURRENCY_CODE
    if value is not None:
        return format_html(
            "{}",
            format_currency(
                value,
                currency_override,
                locale=get_currency_locale(currency_override),
            ),
        )
    return None


@register.simple_tag
def currency_symbol():
    return get_currency_symbol()


@register.simple_tag
def currency_name():
    return get_currency_name()


@register.simple_tag
def get_base_url():
    return settings.BASE_URL


@lru_cache(maxsize=128)
def do_render_icon(name):
    svg = render_to_string(f"icons/{name}.svg")
    return format_html("{}", svg)


@register.simple_tag
def render_icon(name):
    return do_render_icon(name)


def generateimagesafe(*args, **kwargs):
    """Like imagekit's generateimage, but will not raise an error in debug mode
    (will just log instead). Imagekit does not silence errors if the file is missing;
    it will re-raise Django's error loading from storage.

    This is an issue with DB restores because the filename is stored in the database,
    and the filename is not part of the DB restore.

    This ends up crashing the entire page,
    which is awful, so this is the way to bypass it.
    """
    result = imagekit.templatetags.imagekit.generateimage(*args, **kwargs)
    if not settings.DEBUG:
        return result
    orig_render = result.render

    def safe_render(*iargs, **ikwargs):
        try:
            return orig_render(*iargs, **ikwargs)
        except FileNotFoundError as ex:
            logger.bind(tag="generateimagesafe", missing_filename=ex.filename).error(
                "generateimage_file_not_found"
            )
            return ""

    result.render = safe_render
    return result


generateimagesafe = register.tag(generateimagesafe)


@register.simple_tag
def calculate_subcomponent_cost(total_cost, percentage, currency_code):
    cost = Decimal(total_cost) * (Decimal(percentage) / 100)
    return format_currency_filter(cost, currency_code)


@register.simple_tag
def get_allocation_by_intervention_instance_for_cost_line_item(
    cli: CostLineItem,
    intervention_instance: InterventionInstance,
) -> str:
    allocation_item = None
    for each_allocation in require_prefetch(cli.config, "allocations"):
        if each_allocation.intervention_instance == intervention_instance:
            allocation_item = each_allocation
            break
    if allocation_item and allocation_item.allocation:
        return f"{allocation_item.allocation:.2f}%"
    else:
        return "-"
