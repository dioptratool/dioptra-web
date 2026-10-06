import json

from django import forms
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html

from ombucore.admin.templatetags.panels_extras import jsonattr


class CurrencyWidget(forms.Widget):
    template_name = "django/forms/widgets/currency.html"


class PercentWidget(forms.Widget):
    template_name = "django/forms/widgets/percent.html"


class TagEditorWidget(forms.TextInput):
    def __init__(self, options=None, attrs=None):
        attrs = attrs if attrs else {}
        options = options if options else {}
        attrs["data-tageditor"] = jsonattr(options)
        super().__init__(attrs=attrs)

    class Media:
        js = (
            "lib/tagify/tagify.js",
            "lib/tagify/tagify.init.js",
        )
        css = {"all": ("lib/tagify/tagify.css",)}


class FilterableChoiceWidget(forms.Select):
    """
    A single-select dropdown whose options can be narrowed by typing.

    At rest the field shows the selected option's label. Focusing it starts a blank
    search (the selection stays visible as the placeholder), and leaving the field
    keeps whichever option is highlighted, so a search that is abandoned still ends
    on a listed value. Escape leaves the previous selection untouched, and a clear
    button appears whenever something is selected.

    Only listed values can be chosen, so the posted value is always a choice or blank.
    Labels may differ from values, e.g. "4100 — Salaries" for the value "4100".
    """

    template_name = "widgets/filterable-choice.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        selected_value, selected_label = "", ""
        for _group_name, group_choices, _group_index in widget["optgroups"]:
            for option in group_choices:
                if option["selected"] and option["value"] != "":
                    selected_value = option["value"]
                    selected_label = option["label"]
                    break
            if selected_value:
                break
        widget["selected_value"] = selected_value
        widget["selected_label"] = selected_label
        # Rendered on the visible input, where the bulk "<multiple values>" marker belongs.
        widget["placeholder"] = widget["attrs"].pop("placeholder", "")
        return context

    class Media:
        js = ("website/js/filterable-choice.js",)


class ArraySelectMultiple(forms.SelectMultiple):
    def value_omitted_from_data(self, data, files, name):
        return False


class ArrayCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    def value_omitted_from_data(self, data, files, name):
        return False


class SortableSelectMultipleSubcomponentLabelsWidget(forms.Select):
    template_name: str = "widgets/select-labels.html"
    instance_pk: int | None = None

    def get_context(self, name: str, value: str, attrs: dict | None = None) -> dict:
        context = super().get_context(name, value, attrs)
        json_value = json.loads(value) if isinstance(value, str) else value
        json_value = json_value or []
        choices = []
        for idx, label in enumerate(json_value):
            choices.append(
                {
                    "id": self.instance_pk,
                    "label": label,
                    "label_idx": idx,
                    "change_url": reverse(
                        "subcomponent-label-edit-label",
                        kwargs={
                            "label": label,
                            "label_idx": idx,
                        },
                    ),
                }
            )

        context[name] = [c["label"] for c in choices]
        context["sortable"] = True
        context["choices"] = choices
        return context


class TemplateDownloadWidget(forms.Widget):
    def __init__(self, template_path: str, *args, **kwargs):
        self.template_path = template_path
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        url = static(self.template_path)
        return format_html(f'<a href="{url}" download>Download Template</a>')


class TemplateDownloadField(forms.Field):
    def __init__(self, template_path: str, *args, **kwargs):
        kwargs["required"] = False
        kwargs["widget"] = TemplateDownloadWidget(template_path)
        super().__init__(*args, **kwargs)
