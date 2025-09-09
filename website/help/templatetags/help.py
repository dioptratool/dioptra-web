from django import template

from website.help.utils import get_helpitems

register = template.Library()


def user_can_edit(user):
    return user.has_perm("website.change_helpitem")


@register.inclusion_tag("help/_help-item.html", takes_context=True, name="help")
def help_item(context, identifier=None):
    if not identifier:
        return {}
    item = get_helpitems().get(identifier)
    if not item:
        return {}
    return {
        "identifier": identifier,
        "help_text": item.help_text,
        "title": item.title,
        "link": item.link,
        "item": item,
        "user_can_edit_help": user_can_edit(context.get("user")),
    }


@register.inclusion_tag("help/_help-item.html", takes_context=True, name="help_category")
def help_category(context, category, identifier):
    identifier = f"{identifier.strip('_')}__{category.lower().replace(' ', '_')}_category"
    item = get_helpitems().get(identifier)
    if not item:
        return {}
    return {
        "identifier": identifier,
        "help_text": item.help_text,
        "title": item.title,
        "link": item.link,
        "item": item,
        "user_can_edit_help": user_can_edit(context.get("user")),
    }


@register.inclusion_tag("help/_help-item.html", takes_context=True, name="help_cost_type")
def help_cost_type(context, cost_type, identifier):
    identifier = f"{identifier.strip('_')}__{cost_type.lower().replace(' ', '_')}_cost_type"
    item = get_helpitems().get(identifier)
    if not item:
        return {}
    return {
        "identifier": identifier,
        "help_text": item.help_text,
        "title": item.title,
        "link": item.link,
        "item": item,
        "user_can_edit_help": user_can_edit(context.get("user")),
    }
