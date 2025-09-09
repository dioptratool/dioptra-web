from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from website.app_log.loggers import log_help_item_created
from website.help.fields import (
    HELP_CATEGORIES,
    HELP_COST_TYPES,
    format_identifier,
    format_title,
)
from website.help.models import HelpItem
from website.models import Category, CostType
from .utils import get_helpitems

User = get_user_model()


@receiver(post_save, sender=Category)
def save_category_help_items(sender, instance, created, **kwargs):
    for definition in HELP_CATEGORIES:
        identifier = format_identifier(definition.identifier, category=instance.name)
        try:
            HelpItem.objects.get(identifier=identifier)
        except HelpItem.DoesNotExist:
            hi = HelpItem.objects.create(
                type=definition.type,
                title=format_title(definition.title, category=instance.name),
                identifier=identifier,
            )
            log_help_item_created(hi)


@receiver(post_save, sender=CostType)
def save_cost_type_help_items(sender, instance, created, **kwargs):
    for definition in HELP_COST_TYPES:
        identifier = format_identifier(definition.identifier, cost_type=instance.name)
        try:
            HelpItem.objects.get(identifier=identifier)
        except HelpItem.DoesNotExist:
            hi = HelpItem.objects.create(
                type=definition.type,
                title=format_title(definition.title, cost_type=instance.name),
                identifier=identifier,
            )
            log_help_item_created(hi)


@receiver(post_delete, sender=Category)
def delete_category_help_items(sender, instance, *args, **kwargs):
    HelpItem.objects.filter(
        identifier__in=[
            format_identifier(category.identifier, category=instance.name) for category in HELP_CATEGORIES
        ]
    ).delete()


@receiver(post_delete, sender=CostType)
def delete_cost_type_help_items(sender, instance, *args, **kwargs):
    HelpItem.objects.filter(
        identifier__in=[
            format_identifier(cost_type.identifier, cost_type=instance.name) for cost_type in HELP_COST_TYPES
        ]
    ).delete()


@receiver([post_save, post_delete], sender=HelpItem)
def clear_tooltip_cache(sender, **kwargs):
    """
    Invalidate the cached {key: HelpTooltip} mapping whenever
    a tooltip is added, changed, or removed.
    """
    get_helpitems.cache_clear()
