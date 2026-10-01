import json

from django import forms
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from ombucore.admin.forms.base import ModelFormBase
from website.forms.fields import SubcomponentLabelField
from website.forms.intervention_metadata import MetadataDraftField
from website.forms.widgets import MetadataEditorWidget
from website.intervention_metadata import build_draft, save_draft, validate_draft
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

    # The Metadata tab: the whole definition tree as one staged draft, committed with the parent.
    metadata_draft = MetadataDraftField(label=_("Metadata"), widget=MetadataEditorWidget)

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", {})
        if kwargs.get("instance"):
            instance = kwargs["instance"]
            if len(instance.output_metrics):
                if len(instance.output_metrics) >= 1:
                    initial["output_metric_1"] = instance.output_metrics[0]
                if len(instance.output_metrics) >= 2:
                    initial["output_metric_2"] = instance.output_metrics[1]
        # A JSON string, as the browser posts it, so the form's initial values round-trip as is.
        initial.setdefault("metadata_draft", json.dumps(build_draft(kwargs.get("instance"))))
        kwargs["initial"] = initial

        super().__init__(*args, **kwargs)
        self.fields["subcomponent_labels"].widget.form_instance = self
        self.fields["metadata_draft"].widget.form_instance = self
        self.metadata_rows = []

    def clean_metadata_draft(self):
        draft = self.cleaned_data["metadata_draft"]
        # Every problem is listed on the Metadata tab, naming the field; the draft itself survives.
        self.metadata_rows = validate_draft(self.instance if self.instance.pk else None, draft)
        return draft

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

    def save(self, commit=True):
        # The intervention and its definitions commit together; with commit=False the definitions
        # are staged and written by save_m2m(), as Django does for many-to-many data.
        if not commit:
            return super().save(commit=False)
        with transaction.atomic():
            return super().save(commit=True)

    def _save_m2m(self):
        super()._save_m2m()
        save_draft(self.instance, self.metadata_rows)

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
            "metadata_draft",
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
            (
                _("Metadata"),
                {"fields": ("metadata_draft",)},
            ),
        )
        help_texts = {
            "group": _("Select the group for this intervention in the Program Design Lessons menu."),
        }

    class Media:
        js = (
            "panels/lib/Sortable.js",
            "website/js/subcomponent-labels.js",
            "website/js/intervention-metadata-editor.js",
        )
        css = {"all": ("panels/css/panels-relation-widget.css",)}
