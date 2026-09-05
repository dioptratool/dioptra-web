import re
from typing import TYPE_CHECKING

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _l
from django_ckeditor_5.widgets import CKEditor5Widget

from ombucore.admin.forms.base import ModelFormBase
from ombucore.admin.widgets import FlatpickrDateWidget
from website.forms.fields import PositiveFixedDecimalField, SubcomponentLabelField
from website.forms.widgets import TagEditorWidget
from website.models import (
    Analysis,
    InterventionInstance,
    Settings,
    SubcomponentCostAnalysis,
)
from website.models.field_label import FieldLabelOverrides

if TYPE_CHECKING:
    from website.users.models import User


class DefineForm(forms.ModelForm):
    CSS_CLASSES = {
        "inline_checkbox": {
            "help_text": "form__italic",
            "label": "form__inline_checkbox__label form__checkbox_green",
            "value": "margin-y-0",
        }
    }
    start_date = forms.DateField(
        widget=FlatpickrDateWidget(
            options={"dateFormat": settings.DATE_FORMAT},
            format="%d-%b-%Y",
        ),
        input_formats=settings.DATE_INPUT_FORMATS,
    )
    end_date = forms.DateField(
        widget=FlatpickrDateWidget(
            options={"dateFormat": settings.DATE_FORMAT},
            format="%d-%b-%Y",
        ),
        input_formats=settings.DATE_INPUT_FORMATS,
    )

    class Meta:
        model = Analysis
        fields = [
            "title",
            "description",
            "analysis_type",
            "start_date",
            "end_date",
            "country",
            "grants",
            "output_count_source",
            "other_hq_costs",
            "in_kind_contributions",
            "client_time",
        ]
        widgets = {
            "grants": TagEditorWidget(options={"forceLowercase": False}),
            "other_hq_costs": forms.CheckboxInput(
                attrs={"class": "form__checkbox_lg"},
            ),
            "in_kind_contributions": forms.CheckboxInput(
                attrs={"class": "form__checkbox_lg"},
            ),
            "client_time": forms.CheckboxInput(
                attrs={"class": "form__checkbox_lg"},
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user: User | None = kwargs.pop("user", None)
        self.settings = Settings.objects.first()
        self.data_loaded = kwargs.pop("data_loaded", False)

        super().__init__(*args, **kwargs)
        self.fields["analysis_type"].empty_label = settings.EMPTY_LABEL

        self.fields["country"].empty_label = settings.EMPTY_LABEL
        self.fields["grants"].label = FieldLabelOverrides.label_for("ci_grant_code", "Grants")

        # Disable fields in data is already loaded.
        if self.data_loaded:
            self.fields["start_date"].disabled = True
            self.fields["end_date"].disabled = True
            self.fields["grants"].disabled = True
            if self.settings.transaction_country_filter:
                self.fields["country"].disabled = True
            if self.instance.other_hq_costs_cost_line_items.exists():
                self.fields["other_hq_costs"].disabled = True
            if self.instance.in_kind_contributions_cost_line_items.exists():
                self.fields["in_kind_contributions"].disabled = True
            if self.instance.client_time_cost_line_items.exists():
                self.fields["client_time"].disabled = True

        # Only allow countries that the User is associated with to be selectable
        self.fields["country"].queryset = self.user.associated_countries

    def save(self, commit=True):
        analysis = super().save(commit=commit)
        analysis.ensure_cost_type_category_objects()
        return analysis

    def clean(self):
        if self.instance.pk is None:
            self.instance.owner = self.user
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and start_date > end_date:
            self.add_error("start_date", ValidationError("Start date must be before end date."))
        return cleaned_data

    def clean_grants(self) -> str:
        grants = self.cleaned_data["grants"]
        if grants:
            grants = list(map(str.strip, grants.split(",")))
            for grant in grants:
                if not self._grant_is_valid(grant):
                    raise forms.ValidationError(f'Invalid grant format: "{grant}"')
            grants = ",".join(grants)
        return grants

    def _grant_is_valid(self, grant) -> bool:
        return True if re.match(r"^\S+$", grant) else False


class AllocateInterventionBulkForm(forms.Form):
    """
    Bulk "Set Allocation" panel form for the Allocate Intervention Costs step.
    """

    config_ids = forms.TypedMultipleChoiceField(coerce=int, widget=forms.MultipleHiddenInput())

    def __init__(self, *args, analysis, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["config_ids"].choices = (
            (config_id, config_id) for config_id in kwargs["initial"]["config_ids"]
        )
        for intervention_instance in analysis.interventioninstance_set.all():
            self.fields[f"allocation_{intervention_instance.id}"] = PositiveFixedDecimalField(
                label=intervention_instance.display_name(),
                max_value=100,
                min_value=0,
                initial=0,
                allow_zero=True,
                widget=forms.TextInput(attrs={"class": "bulk-allocation-input", "inputmode": "decimal"}),
            )
        self.fields["notes"] = forms.CharField(
            label=_l("Notes"),
            required=False,
            max_length=2048,
            widget=forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": _l("Source of this information and any other important notes"),
                }
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        allocation_sum = sum(
            value
            for name, value in cleaned_data.items()
            if name.startswith("allocation_") and value is not None
        )
        if allocation_sum > 100:
            raise ValidationError(_l("Total allocation cannot exceed 100%"))
        return cleaned_data

    class Media:
        js = ("website/js/bulk-allocate-form.js",)


class AllocateSubcomponentsBulkForm(forms.Form):
    """
    Bulk "Set Allocation" panel form for the Allocate Sub-Component Costs step.
    """

    config_ids = forms.TypedMultipleChoiceField(coerce=int, widget=forms.MultipleHiddenInput())

    def __init__(self, *args, subcomponent_labels, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["config_ids"].choices = (
            (config_id, config_id) for config_id in kwargs["initial"]["config_ids"]
        )
        for idx, label in enumerate(subcomponent_labels):
            self.fields[f"subcomponent_allocation_{idx}"] = PositiveFixedDecimalField(
                label=label,
                max_value=100,
                min_value=0,
                initial=0,
                allow_zero=True,
                widget=forms.TextInput(attrs={"class": "bulk-allocation-input", "inputmode": "decimal"}),
            )

    def clean(self):
        cleaned_data = super().clean()
        allocation_sum = sum(
            value
            for name, value in cleaned_data.items()
            if name.startswith("subcomponent_allocation_") and value is not None
        )
        if allocation_sum != 100:
            raise ValidationError(_l("Allocations must total 100%"))
        return cleaned_data

    class Media:
        js = ("website/js/bulk-allocate-form.js",)


class ReassignOwnerForm(ModelFormBase):
    class Meta:
        model = Analysis
        fields = [
            "owner",
        ]
        help_texts = {
            "owner": _l("Select the user who owns this analysis"),
        }


class SaveSuggestedToAllConfirmForm(forms.Form):
    pass


class AnalysisLessonsEditorForm(forms.Form):
    _help = {
        "breakdown_lesson": [
            "Do the proportion of these cost categories look reasonable? Why are some categories larger than others?  "
            "What do they contain? Do they bring more value to clients?",
            "Are any costs missing or included that may have affected program quality or reach?",
            "Were any costs realigned to provide more benefit to more clients?  Is there potential for cost savings "
            "and cost avoidance to channel back to clients? (Provide some examples)",
        ],
        "efficiency_lesson": [
            "What did we learn about the cost-efficiency of this intervention?",
            "How might a different reach or modality affect this intervention’s cost-efficiency?  What might be "
            "preventing a higher reach or a different modality?",
            "Why might the costs for this intervention be different from other projects – is it because of the program "
            "design or context?  How can we improve reach and impact?",
        ],
    }

    def __init__(self, *args, **kwargs):
        """
        If an instance of Analysis is being injected into this form, we should use its
        value for "channel" as the initial value for the form
        """
        analysis = kwargs.pop("analysis")
        lesson_field = kwargs.pop("lesson_field")

        super().__init__(*args, **kwargs)

        self.fields["lesson"].initial = getattr(analysis, lesson_field)

        # Format help items into an HTML list to be displayed as help text
        help_items = self._help.get(lesson_field)
        if help_items:
            html_items = "".join(
                [f'<li style="list-style-type: initial">{help_item}</li>' for help_item in help_items]
            )
            self.fields["lesson"].help_text = f'<ul style="padding-left: 0.75rem;">{html_items}</ul>'

    lesson = forms.CharField(
        help_text="",
        label="",
        required=False,
        widget=CKEditor5Widget(config_name="help_text_limitless"),
    )


class SubcomponentLabelEditForm(forms.Form):
    label = forms.CharField(label=_l("Label"), max_length=255)


class SubcomponentLabelsForm(forms.Form):
    """
    Edits the sub-component labels of an InterventionInstance, creating or
    deleting its SubcomponentCostAnalysis as needed.
    """

    subcomponent_labels = SubcomponentLabelField(required=False)

    def __init__(self, *args, intervention_instance: InterventionInstance, locked: bool = False, **kwargs):
        self.intervention_instance = intervention_instance
        self.locked = locked
        super().__init__(*args, **kwargs)
        self.fields["subcomponent_labels"].initial = self._initial_labels()
        if locked:
            self.fields["subcomponent_labels"].widget.attrs["prevent_add_remove"] = True

    def _existing_labels(self) -> list[str]:
        if hasattr(self.intervention_instance, "subcomponent_cost_analysis"):
            return self.intervention_instance.subcomponent_cost_analysis.subcomponent_labels or []
        return []

    def _initial_labels(self) -> list[str]:
        labels = self._existing_labels()
        if not labels and not self.locked:
            labels = self.intervention_instance.intervention.subcomponent_labels or []
        return labels

    def clean_subcomponent_labels(self) -> list[str]:
        labels = self.cleaned_data["subcomponent_labels"] or []
        if self.locked and len(labels) != len(self._existing_labels()):
            raise ValidationError(
                _l("Sub-component labels cannot be added or removed after cost data has been loaded.")
            )
        return labels

    def save(self) -> None:
        labels = self.cleaned_data["subcomponent_labels"] or []
        if labels:
            subcomponent_analysis, _ = SubcomponentCostAnalysis.objects.get_or_create(
                intervention_instance=self.intervention_instance
            )
            subcomponent_analysis.subcomponent_labels = labels
            subcomponent_analysis.save()
        elif hasattr(self.intervention_instance, "subcomponent_cost_analysis"):
            self.intervention_instance.subcomponent_cost_analysis.delete()

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


class SubcomponentLabelsDeleteConfirmForm(forms.Form):
    pass
