from django import forms
from django.utils.translation import gettext_lazy as _

from ombucore.admin.forms.base import ModelFormBase
from website.forms.subcomponent import SubcomponentLabelField
from website.models.intervention import OUTPUT_METRIC_CHOICES


class InterventionForm(ModelFormBase):
    output_metric_1 = forms.ChoiceField(
        label=_("Output Metric 1"),
        choices=OUTPUT_METRIC_CHOICES,
    )
    output_metric_2 = forms.ChoiceField(
        label=_("Output Metric 2"),
        choices=[("", _("(Choose)"))] + OUTPUT_METRIC_CHOICES,
        required=False,
    )

    subcomponent_labels = SubcomponentLabelField(required=False)

    def __init__(self, *args, **kwargs):
        if kwargs.get("instance"):
            initial = kwargs.get("initial", {})
            instance = kwargs["instance"]
            if len(instance.output_metrics):
                if len(instance.output_metrics) >= 1:
                    initial["output_metric_1"] = instance.output_metrics[0]
                if len(instance.output_metrics) >= 2:
                    initial["output_metric_2"] = instance.output_metrics[1]
            kwargs["initial"] = initial

        super().__init__(*args, **kwargs)
        self.fields["subcomponent_labels"].widget.form_instance = self

    def clean(self):
        cleaned_data = super().clean()
        output_metrics = []
        output_metric_1 = cleaned_data.pop("output_metric_1")
        if output_metric_1:
            output_metrics.append(output_metric_1)
        output_metric_2 = cleaned_data.pop("output_metric_2")
        if output_metric_2:
            output_metrics.append(output_metric_2)
        self.instance.output_metrics = output_metrics
        return cleaned_data

    class Meta:
        fields = [
            "name",
            "description",
            "icon",
            "group",
            "output_metric_1",
            "output_metric_2",
            "show_in_menu",
            "subcomponent_labels",
        ]
        fieldsets = (
            (
                _("Analysis"),
                {
                    "fields": (
                        "name",
                        "description",
                        "icon",
                        "output_metric_1",
                        "output_metric_2",
                    ),
                },
            ),
            (
                _("Program Design Lessons"),
                {
                    "fields": (
                        "group",
                        "show_in_menu",
                    ),
                },
            ),
            (
                _("Subcomponents"),
                {"fields": ("subcomponent_labels",)},
            ),
        )
        help_texts = {
            "group": _("Select the group for this intervention in the Program Design Lessons menu."),
        }

    class Media:
        js = (
            "panels/lib/Sortable.js",
            "website/js/subcomponent-labels.js",
        )
        css = {"all": ("panels/css/panels-relation-widget.css",)}
