from django import forms
from django import template
from django.urls import reverse

from ombucore.admin.buttons import CancelButton, LinkButton, SubmitButton

register = template.Library()


@register.filter
def fieldset_has_errors(form, fieldset):
    if not form.errors:
        return False
    for field_name in list(form.errors.keys()):
        if field_name in fieldset[1]["fields"]:
            return True
    return False


@register.filter
def get_field(form, field_name):
    return form[field_name]


@register.filter
def is_checkbox(field):
    return isinstance(field.field.widget, forms.CheckboxInput)


@register.filter
def is_select(field):
    return isinstance(field.field.widget, forms.Select)


@register.filter
def is_select_multiple(field):
    return isinstance(field.field.widget, forms.SelectMultiple)


@register.filter
def is_multiple_checkbox(field):
    return isinstance(field.field.widget, forms.CheckboxSelectMultiple)


@register.filter
def is_radio(field):
    return isinstance(field.field.widget, forms.RadioSelect)


@register.filter
def is_file(field):
    return isinstance(field.field.widget, forms.FileInput)


@register.filter
def is_multiwidget(field):
    return isinstance(field.field.widget, forms.MultiWidget)


@register.filter
def add_input_classes(field):
    if is_multiwidget(field):
        for i, widget in enumerate(field.field.widget.widgets):
            field.field.widget.widgets[i] = add_widget_classes(widget)
    else:
        field.field.widget = add_widget_classes(field.field.widget)
    return field


def add_widget_classes(widget):
    widget_classes = widget.attrs.get("class", "")
    if isinstance(
        widget,
        (
            forms.widgets.TextInput,
            forms.widgets.Textarea,
            forms.widgets.NumberInput,
            forms.widgets.EmailInput,
            forms.widgets.URLInput,
            forms.widgets.PasswordInput,
            forms.widgets.Select,
        ),
    ):
        widget_classes += " form-control"
    widget.attrs["class"] = widget_classes
    return widget


def should_use_form_control_class(widget):
    return isinstance(
        widget,
        (
            forms.widgets.TextInput,
            forms.widgets.EmailInput,
            forms.widgets.Select,
        ),
    )


@register.filter
def has_changed(field):
    if field.form.is_bound and field.name in field.form.changed_data:
        return True
    return False


@register.filter
def get_menu_item_name(pk):
    return "menuItem_" + str(pk)


@register.filter
def get_form_model_name(form):
    return form._meta.model.__name__.lower()


@register.filter
def get_default_buttons(view):
    buttons = [
        SubmitButton(
            text="Save",
            style="primary",
            disable_when_form_unchanged=True,
            align="left",
        ),
        CancelButton(
            align="left",
        ),
    ]

    if getattr(view, "delete_route", None):
        buttons.append(
            LinkButton(
                text="Delete",
                style="danger",
                align="right",
                href=reverse(view.delete_route, args=[view.object.id]),
                panels_trigger=False,  # Delete is handled in js via the `.panels-delete-btn` class.
                attrs={
                    "class": "panels-delete-btn",
                },
            )
        )

    return buttons


@register.filter
def filter_field_should_use_button(field):
    if is_select(field) and not is_select_multiple(field):
        return False
    elif is_checkbox(field):
        return False
    elif is_radio(field):
        return False
    return True
