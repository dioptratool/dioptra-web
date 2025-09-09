from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from ombucore.admin.forms.base import ModelFormBase
from website.models import SubcomponentCostAnalysis
from .fields import SubcomponentLabelField


class ConfirmSubcomponentCostAnalysisForm(ModelFormBase):
    subcomponent_labels_confirmed = forms.BooleanField(
        widget=forms.HiddenInput(),
        initial="true",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = self.instance.subcomponent_cost_analysis

    class Meta:
        model = SubcomponentCostAnalysis
        fields = ["subcomponent_labels_confirmed"]


class EditSubcomponentCostAnalysisLabelsForm(ModelFormBase):
    subcomponent_labels = SubcomponentLabelField()

    def __init__(self, *args, prevent_add_remove=False, **kwargs):
        super().__init__(*args, **kwargs)
        if prevent_add_remove:
            self.fields["subcomponent_labels"].widget.attrs["prevent_add_remove"] = prevent_add_remove

    class Meta:
        model = SubcomponentCostAnalysis
        fields = ["subcomponent_labels"]

    class Media:
        js = (
            "panels/lib/Sortable.js",
            "website/js/subcomponent-labels.js",
        )
        css = {
            "all": (
                "panels/css/panels-relation-widget.css",
                "website/css/subcomponent-confirm-labels.css",
            )
        }


class EditSubcomponentLabelForm(forms.Form):
    label = forms.CharField(required=True)


class BulkSubcomponentAnalysisAllocationForm(forms.Form):
    config_ids = forms.TypedMultipleChoiceField(
        coerce=int,
        widget=forms.MultipleHiddenInput(),
    )

    def __init__(self, *args, **kwargs):
        new_fields = kwargs.pop("extra_label_fields")
        super().__init__(*args, **kwargs)
        self.fields["config_ids"].choices = (
            (config_id, config_id) for config_id in kwargs["initial"]["config_ids"]
        )
        for i, each_label in enumerate(new_fields):
            self.fields[f"subcomponent_allocation_{i}"] = forms.FloatField(
                label=each_label,
                max_value=100,
                min_value=0,
                initial=0,
                widget=forms.NumberInput(attrs={"class": "bulk-subcomponent-allocation-input"}),
            )

    def clean(self):
        cleaned_data = super().clean()
        allocation_sum = 0
        for k, v in cleaned_data.items():
            if k.startswith("subcomponent_allocation_"):
                allocation_sum += v

        if allocation_sum != 100:
            raise ValidationError("Allocations must total 100%")

        return cleaned_data

    class Media:
        js = ("website/js/subcomponent-bulk-form.js",)
        css = {"all": ("website/css/subcomponent-bulk-form.css",)}
