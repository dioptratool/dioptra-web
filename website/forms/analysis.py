import json
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
from website.subcomponent_labels import (
    STALE_MESSAGE,
    Component,
    is_stale,
    update_subcomponent_labels,
    validate_sources,
)

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
    suggestion_requested = forms.BooleanField(required=False, widget=forms.HiddenInput())

    def __init__(
        self,
        *args,
        interventions,
        include_notes=True,
        allow_empty_allocations=False,
        suggested_intervention_ids=(),
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.fields["config_ids"].choices = (
            (config_id, config_id) for config_id in kwargs["initial"]["config_ids"]
        )
        for intervention_instance in interventions:
            css_class = "bulk-allocation-input"
            if intervention_instance.id in suggested_intervention_ids:
                # Highlight fields pre-filled with a suggestion; the JS removes it on edit.
                css_class += " bulk-allocation-input--suggested"
            self.fields[f"allocation_{intervention_instance.id}"] = PositiveFixedDecimalField(
                label=intervention_instance.display_name(),
                max_value=100,
                min_value=0,
                initial=0,
                allow_zero=True,
                widget=forms.TextInput(attrs={"class": css_class, "inputmode": "decimal"}),
            )
        self.fields["notes"] = forms.CharField(
            label=_l("Notes"),
            required=False,
            max_length=2048,
            widget=forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": _l("Source of this information and any other important notes"),
                    "rows": 4,
                }
            ),
        )
        if not include_notes:
            del self.fields["notes"]
        if self.is_bound and allow_empty_allocations:
            self.data = self.data.copy()
            for name in self.fields:
                value = self.data.get(name)
                if name.startswith("allocation_") and isinstance(value, str) and not value.strip():
                    self.data[name] = "0"

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
    # The sub-component analysis revision the panel was opened on (see SubcomponentCostAnalysis).
    subcomponent_revision = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, subcomponent_labels, expected_revision=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_revision = expected_revision
        self.fields["subcomponent_revision"].initial = expected_revision
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
        if "subcomponent_revision" in self.data and self.expected_revision is not None:
            if str(self.data.get("subcomponent_revision")) != str(self.expected_revision):
                raise ValidationError(STALE_MESSAGE)
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

    Percentages are stored by label position, so the editor posts, alongside each
    label, the position it came from (``subcomponent_sources``: an int per label,
    or null for a new one). Saving remaps every allocation row to match; see
    ``website.subcomponent_labels``. A post without sources is treated as a
    rename in place. Components can be added and removed before and after cost
    data is loaded (86.5); surviving percentages are kept.
    """

    # ``subcomponent_sources`` is deliberately not a form field: the label widget renders that
    # input itself (the editor script maintains it), and a form field would render a second
    # input of the same name, which the browser would also submit and Django would prefer.
    subcomponent_labels = SubcomponentLabelField(required=False)
    # Identity of the sub-component analysis the form was opened on; a post that no longer
    # matches (components changed, or the analysis was deleted/recreated) is rejected.
    subcomponent_analysis_id = forms.CharField(required=False, widget=forms.HiddenInput)
    subcomponent_revision = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, intervention_instance: InterventionInstance, **kwargs):
        self.intervention_instance = intervention_instance
        super().__init__(*args, **kwargs)
        self.fields["subcomponent_labels"].initial = self._initial_labels()
        self.fields["subcomponent_labels"].widget.sources = self._widget_sources()
        existing = self._existing_analysis()
        if existing is not None:
            self.fields["subcomponent_analysis_id"].initial = existing.id
            self.fields["subcomponent_revision"].initial = existing.revision

    def _posted_json(self, name):
        """A posted JSON value, or None when absent/blank. Raises ValueError when malformed."""
        raw = self.data.get(name) if self.is_bound else None
        if raw in (None, ""):
            return None
        return json.loads(raw)

    def _positional_sources(self, count: int) -> list[int | None]:
        """Labels keep the position they are shown at; positions past the saved list are new."""
        existing_count = len(self._existing_labels())
        return [idx if idx < existing_count else None for idx in range(count)]

    def _widget_sources(self) -> list[int | None]:
        """
        The position list the widget renders next to its labels: the posted mapping when the
        form re-displays after an error, identity for saved labels, and null for intervention
        defaults (they are not saved labels, so they have no position).
        """
        if self.is_bound:
            try:
                labels = self._posted_json("subcomponent_labels") or []
                sources = self._posted_json("subcomponent_sources")
            except ValueError:
                labels, sources = [], None
            if isinstance(sources, list) and len(sources) == len(labels):
                return sources
            return self._positional_sources(len(labels) if isinstance(labels, list) else 0)
        return self._positional_sources(len(self.fields["subcomponent_labels"].initial or []))

    def _existing_analysis(self) -> SubcomponentCostAnalysis | None:
        return getattr(self.intervention_instance, "subcomponent_cost_analysis", None)

    def _existing_labels(self) -> list[str]:
        subcomponent_analysis = self._existing_analysis()
        if subcomponent_analysis is not None:
            return subcomponent_analysis.subcomponent_labels or []
        return []

    def _initial_labels(self) -> list[str]:
        return self._existing_labels() or self.intervention_instance.intervention.subcomponent_labels or []

    def clean(self):
        cleaned_data = super().clean()
        labels = cleaned_data.get("subcomponent_labels")
        if labels is None:
            return cleaned_data
        labels = labels or []
        existing = self._existing_analysis()
        existing_count = len(self._existing_labels())

        if not labels and existing is not None:
            # Removing every component deletes percentages and skip flags; that needs the
            # Delete panel's confirmation, not a quietly emptied list.
            self.add_error(
                "subcomponent_labels",
                _l("To remove the sub-component analysis, use Delete on the Define Interventions step."),
            )
            return cleaned_data

        if "subcomponent_analysis_id" in self.data or "subcomponent_revision" in self.data:
            if is_stale(
                existing, self.data.get("subcomponent_analysis_id"), self.data.get("subcomponent_revision")
            ):
                self.add_error(None, STALE_MESSAGE)
                return cleaned_data

        try:
            sources = self._posted_json("subcomponent_sources")
            if sources is None:
                # Rename in place: labels keep the position they are posted at.
                sources = self._positional_sources(len(labels))
            if not isinstance(sources, list) or len(sources) != len(labels):
                raise ValidationError(_l("Invalid sub-component reference."), code="invalid")
            validate_sources(sources, existing_count)
        except (ValueError, ValidationError) as error:
            # The sources input is hidden, so its errors would never be shown; report them
            # on the form instead.
            if not isinstance(error, ValidationError):
                error = ValidationError(_l("Invalid sub-component reference."), code="invalid")
            self.add_error(None, error)
            return cleaned_data

        cleaned_data["components"] = [
            Component(label=label, source=source) for label, source in zip(labels, sources)
        ]
        return cleaned_data

    def save(self) -> None:
        components = self.cleaned_data["components"]
        if components:
            update_subcomponent_labels(
                self._existing_analysis(), components, intervention_instance=self.intervention_instance
            )

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
