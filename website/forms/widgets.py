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
        json_value = json.loads(value) or []
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


class AnalysisInterventionDefineWidget(forms.Widget):
    template_name: str = "widgets/analysis-interventions-field.html"


class SortableSelectMultipleAnalysisInterventionsWidget(forms.Widget):
    template_name: str = "widgets/analysis-interventions-table.html"

    def get_context(self, name: str, value: str, attrs: dict | None = None) -> dict:
        context = super().get_context(name, value, attrs)
        json_value = json.loads(value) or []
        context["json"] = json_value
        for idx, intervention in enumerate(json_value):
            intervention["change_url"] = reverse("analysis-define-interventions-edit")
            # {
            #     "id": 21,
            #     "title": "Teacher Development: Face-to-Face Trainings",
            #     "ctype_id": 1,
            #     "verbose_name": "Intervention",
            #     "verbose_name_plural": "Interventions",
            #     "change_url": "/panels/website/intervention/21/change/"
            # }

        context["sortable"] = True
        context["objects_info"] = json_value
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
