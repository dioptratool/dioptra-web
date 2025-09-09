from website.help.fields import (
    HELP_IDENTIFIERS,
    HELP_TOPICS,
    HelpItemType,
    format_identifier,
    format_title,
)
from website.help.models import HelpItem, HelpTopic
from website.models import Category, CostType


def sync_help_item(*identifier_types, reset=False, **kwargs):
    if reset:
        HelpItem.objects.filter(type__in=identifier_types).delete()
    for type in identifier_types:
        for definition in HELP_IDENTIFIERS.get(type):
            title = format_title(definition.title, **kwargs)
            identifier = format_identifier(definition.identifier, **kwargs)

            try:
                HelpItem.objects.get(identifier=identifier)
            except HelpItem.DoesNotExist:
                HelpItem.objects.create(type=definition.type, title=title, identifier=identifier)


def sync_help_topics(reset=False):
    if reset:
        HelpTopic.objects.all().delete()
    for topic_title in HELP_TOPICS:
        topic, _ = HelpTopic.objects.get_or_create(title=topic_title)


def sync_field_help(reset=False):
    sync_help_item("field", reset=reset)


def sync_category_help(reset=False):
    if reset:
        HelpItem.objects.filter(type=HelpItemType.CATEGORY).delete()
    for category in Category.objects.all():
        sync_help_item(HelpItemType.CATEGORY, reset=reset, category=category.name)


def sync_cost_type_help(reset=False):
    if reset:
        HelpItem.objects.filter(type=HelpItemType.COST_TYPE).delete()
    for cost_type in CostType.objects.all():
        sync_help_item(HelpItemType.COST_TYPE, reset=reset, cost_type=cost_type.name)


SYNC_FUNCS = {
    "field": sync_field_help,
    "category": sync_category_help,
    "cost_type": sync_cost_type_help,
    "topic": sync_help_topics,
}


def sync_all(reset=False):
    for fn in SYNC_FUNCS.values():
        fn(reset)
