from itertools import chain

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import slugify

from ombucore.admin.sites import site
from ombucore.admin.templatetags.panels_extras import jsonattr


###############################################################################
# Form Widgets
###############################################################################


def render_control_dropdown(model_class=None, model_classes=None):
    if model_classes:
        links = [render_control_link(model_class) for model_class in model_classes]
        is_add_only = {site.is_add_only(model_class) for model_class in model_classes} == {True}
        if is_add_only:
            button_text = "Create"
        else:
            button_text = "Select"
        return render_to_string(
            "widgets/panelsrelation-widget-dropdown.html",
            {
                "button_text": button_text,
                "links": links,
            },
        )
    else:
        verbose_name = model_class._meta.verbose_name
        css_class = slugify(verbose_name)
        if site.is_add_only(model_class):
            label = "Add"
            route = site.url_for(model_class, "add")
        else:
            label = "Select"
            route = site.url_for(model_class, "changelist_select")
        return '<a class="{css_class}" href="{href}">{label}</a>'.format(
            label=label, css_class=css_class, href=reverse(route)
        )


def render_control_link(model_class):
    verbose_name = model_class._meta.verbose_name
    css_class = slugify(verbose_name)
    if site.is_add_only(model_class):
        route = site.url_for(model_class, "add")
    else:
        route = site.url_for(model_class, "changelist_select")
    return '<a class="{css_class}" href="{href}">{verbose_name}</a>'.format(
        verbose_name=verbose_name, css_class=css_class, href=reverse(route)
    )


class RelationWidget(forms.TextInput):
    def __init__(self, *args, **kwargs):
        self.model_class = kwargs.pop("model_class", None)
        self.model_classes = kwargs.pop("model_classes", None)
        if not self.model_class:
            raise ImproperlyConfigured("RelationWidget requires a model_class class")
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        if self.model_class and not self.model_classes and not site.is_registered(self.model_class):
            raise ImproperlyConfigured(
                f"RelationWidget requires the model class {self.model_class} to be registered with the panels admin."
            )
        if value == "":
            value = None

        objects = [self.model_class.objects.get(pk=value)] if value else []

        widget_classes = (
            "panels-relation-widget--polymorphic"
            if self.model_classes
            else "panels-relation-widget--multiple"
        )
        if len(objects):
            if site.is_add_only(objects[0].__class__):
                widget_classes += " add-only"

        return render_to_string(
            "widgets/panelsrelation-widget.html",
            {
                "classes": "panels-relation-widget--single",
                "base_widget": self.render_base_widget(name, value, attrs, renderer=renderer),
                "objects_info": [site.related_info_for(obj) for obj in objects],
                "control": render_control_dropdown(self.model_class, self.model_classes),
            },
        )

    def render_base_widget(self, name, value, attrs=None, renderer=None):
        return (
            '<span style="display: none;">'
            + super().render(name, value, attrs, renderer=renderer)
            + "</span>"
        )

    class Media:
        js = ("panels/js/panelsrelation-widget.js",)
        css = {"all": ("panels/css/panels-relation-widget.css",)}


class ModelMultipleChoiceWidget(forms.SelectMultiple):
    def __init__(self, *args, **kwargs):
        try:
            kwargs["choices"] = list(kwargs["choices"])
        except:
            kwargs["choices"] = []
        self.model_class = kwargs.pop("model_class", None)
        self.model_classes = kwargs.pop("model_classes", None)
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        values = value
        if values is None:
            values = []

        objects = [self.model_class.objects.get(pk=value) for value in values]
        widget_classes = (
            "panels-relation-widget--polymorphic"
            if self.model_classes
            else "panels-relation-widget--multiple"
        )
        if len(objects):
            if site.is_add_only(objects[0].__class__):
                widget_classes += " add-only"

        return render_to_string(
            "widgets/panelsrelation-widget.html",
            {
                "classes": widget_classes,
                "base_widget": self.render_base_widget(name, values, attrs, renderer=renderer),
                "objects_info": [site.related_info_for(obj) for obj in objects],
                "control": render_control_dropdown(self.model_class, self.model_classes),
            },
        )

    def render_base_widget(self, name, values, attrs=None, renderer=None, choices=()):
        # Only render the choices that are selected.
        self.choices = [
            (int(str(choice_id)), choice) for choice_id, choice in self.choices
        ]  # convert to work w/ django 3
        self.choices = chain(self.choices, choices)
        # Sort them by values order.
        choice_dict = dict(self.choices)
        self.choices = [(int(value), choice_dict[int(value)]) for value in values]
        return (
            '<div style="display: none;">' + super().render(name, values, attrs, renderer=renderer) + "</div>"
        )

    class Media:
        js = (
            "panels/lib/Sortable.js",
            "panels/js/panelsrelation-widget.js",
        )
        css = {"all": ("panels/css/panels-relation-widget.css",)}


class GenericManyToManyWidget(forms.SelectMultiple):
    def __init__(self, *args, **kwargs):
        kwargs["choices"] = []
        self.model_classes = kwargs.pop("model_classes", None)
        super().__init__(*args, **kwargs)

    def value_related_info(self, value):
        from django.contrib.contenttypes.models import ContentType

        ctype_id, model_id = list(map(int, value.split("/")))
        model = ContentType.objects.get_for_id(ctype_id).get_object_for_this_type(id=model_id)
        return site.related_info_for(model)

    def optgroups(self, name, value, attrs=None):
        return [
            (
                None,
                [self.create_option(name, option_value, "", True, index, attrs=attrs)],
                index,
            )
            for index, option_value in enumerate(value)
        ]

    def render(self, name, value, attrs=None, renderer=None):
        objects_info = [self.value_related_info(v) for v in value]
        base_widget = super().render(name, value, attrs, renderer=renderer)
        return render_to_string(
            "widgets/generic-many-to-many-widget.html",
            {
                "base_widget": base_widget,
                "objects_info": objects_info,
                "control": render_control_dropdown(None, self.model_classes),
            },
        )

    class Media:
        js = (
            "panels/lib/Sortable.js",
            "panels/js/generic-many-to-many-widget.js",
        )
        css = {"all": ("panels/css/panels-relation-widget.css",)}


class ModelMultipleChoiceTreeWidget(forms.TextInput):
    def __init__(self, *args, **kwargs):
        try:
            kwargs.pop("choices")
        except:
            pass
        self.model_class = kwargs.pop("model_class", None)
        self.model_classes = kwargs.pop("model_classes", None)
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        if not value or isinstance(value, list):
            object_tree = []
        else:
            object_tree = self.model_class.__bases__[0].objects.get(pk=value).get_descendants()

        return render_to_string(
            "widgets/panelsrelation-blocks-widget.html",
            {
                "base_widget": self.render_base_widget(name, value, attrs, renderer=renderer),
                "control": render_control_dropdown(self.model_class, self.model_classes),
                "object_tree": object_tree,
            },
        )

    def render_base_widget(self, name, value, attrs=None, renderer=None, choices=()):
        return (
            '<div class="tree-reorder-input" hidden>'
            + super().render(name, value, attrs, renderer=renderer)
            + "</div>"
        )

    class Media:
        js = (
            "panels/lib/jquery-ui/jquery-ui.sortable.min.js",
            "panels/lib/jquery.mjs.nestedSortable.js",
            "panels/js/panels-blocks-reorder.js",
        )
        css = {"all": ("panels/lib/jquery-ui/jquery-ui.sortable.min.css",)}


class FlatpickrDateWidget(forms.DateInput):
    def __init__(self, *args, **kwargs):
        self.options = kwargs.pop("options", {})
        super().__init__(*args, **kwargs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        attrs["data-flatpickr"] = jsonattr(self.options)
        return attrs

    class Media:
        js = (
            "panels/lib/flatpickr/flatpickr.min.js",
            "panels/js/flatpickr-init.js",
        )
        css = {"all": ("panels/lib/flatpickr/flatpickr.min.css",)}


class FlatpickrDateTimeWidget(forms.DateTimeInput):
    def __init__(self, *args, **kwargs):
        self.options = kwargs.pop("options", {})
        if not "enableTime" in self.options:
            self.options["enableTime"] = True
        super().__init__(*args, **kwargs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        attrs["data-flatpickr"] = jsonattr(self.options)
        return attrs

    class Media:
        js = (
            "panels/lib/flatpickr/flatpickr.min.js",
            "panels/js/flatpickr-init.js",
        )
        css = {"all": ("panels/lib/flatpickr/flatpickr.min.css",)}


class CheckboxSelectMultipleWithDisabledOptions(forms.CheckboxSelectMultiple):
    def __init__(self, *args, **kwargs):
        self.disabled_options = []
        super().__init__(*args, **kwargs)

    def create_option(self, *args, **kwargs):
        options_dict = super().create_option(*args, **kwargs)
        if options_dict["value"] in self.disabled_options:
            options_dict["attrs"]["disabled"] = ""
        return options_dict


class SelectWithDisabledOptions(forms.Select):
    def __init__(self, *args, **kwargs):
        self.disabled_options = []
        super().__init__(*args, **kwargs)

    def create_option(self, *args, **kwargs):
        options_dict = super().create_option(*args, **kwargs)
        if options_dict["value"] in self.disabled_options:
            options_dict["attrs"]["disabled"] = ""
        return options_dict
