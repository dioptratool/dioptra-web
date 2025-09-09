import html
import json
import re
from typing import TYPE_CHECKING

from ckeditor.widgets import CKEditorWidget
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.handlers.wsgi import WSGIRequest
from django.utils.translation import gettext_lazy as _l

from ombucore.admin.forms.base import ModelFormBase
from ombucore.admin.templatetags.panels_extras import jsonattr
from ombucore.admin.widgets import FlatpickrDateWidget
from website.currency import currency_code
from website.forms.fields import AnalysisInterventionManageField
from website.forms.widgets import AnalysisInterventionDefineWidget, TagEditorWidget
from website.models import Analysis, Category, CostType, Intervention, InterventionInstance, Settings
from website.models.field_label import FieldLabelOverrides
from website.models.utils import (
    get_all_intervention_parameter_fields,
    get_intervention_parameter_mapping,
    get_valid_intervention_parameter,
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

    intervention_data = forms.JSONField(
        label=_l("Interventions Being Analyzed"),
        widget=AnalysisInterventionDefineWidget(),
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
            "intervention_data",
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

    class Media:
        js = ("website/steps/define-form.js",)

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

        # Prepare data for intervention manage panel
        if self.instance.pk:
            intervention_instances = self.instance.interventioninstance_set.all()
        else:
            intervention_instances = []

        self.initial["intervention_data"] = []
        for intervention_instance in intervention_instances:
            self.initial["intervention_data"].append(self._get_intervention_json(intervention_instance))

        # Only allow countries that the User is associated with to be selectable
        self.fields["country"].queryset = self.user.associated_countries

    def save(self, commit=True):
        analysis = super().save(commit=commit)

        intervention_data = self.cleaned_data.get("intervention_data")
        created_intervention_instances_ids = []
        for i, each_intervention_entry in enumerate(intervention_data):
            intervention = Intervention.objects.get(pk=each_intervention_entry["id"])

            # Get Parameters
            parameters = {}
            for each_param in each_intervention_entry.get("params", []):
                parameters[each_param["name"]] = float(each_param["value"])

            # Get Label
            label = each_intervention_entry.get("intervention_label")

            # Get Order
            order = i

            # Handle removed Intervention Instances
            current_intervention_instances_ids = InterventionInstance.objects.filter(
                analysis=analysis
            ).values_list("id", flat=True)

            updated_intervention_instances_ids = [
                e.get("instance_pk") for e in intervention_data if e.get("instance_pk", -1) > 0
            ]
            for each_id in current_intervention_instances_ids:
                if (
                    each_id not in updated_intervention_instances_ids
                    and each_id not in created_intervention_instances_ids
                ):
                    InterventionInstance.objects.get(pk=each_id).delete()

            if each_intervention_entry.get("instance_pk") is not None:
                # Handle new Intervention Instances
                if each_intervention_entry.get("instance_pk") <= 0:
                    new_intervention_instance = analysis.add_intervention(
                        intervention=intervention,
                        label=label,
                        parameters=parameters,
                    )
                    created_intervention_instances_ids.append(new_intervention_instance.id)

                # Handle changed Intervention Instances
                else:
                    existing_intervention_instance = InterventionInstance.objects.get(
                        pk=each_intervention_entry["instance_pk"]
                    )
                    if intervention.id != existing_intervention_instance.intervention.id:
                        # Handle scenario where the Intervention Type has changed
                        existing_intervention_instance.delete()
                        new_intervention_instance = analysis.add_intervention(
                            intervention=intervention,
                            label=label,
                            parameters=parameters,
                        )
                        created_intervention_instances_ids.append(new_intervention_instance.id)
                    else:
                        existing_intervention_instance.label = label
                        existing_intervention_instance.parameters = parameters
                        existing_intervention_instance.order = order
                        existing_intervention_instance.save()

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

    def _get_intervention_json(
        self,
        intervention_instance: InterventionInstance,
    ) -> dict[str : int | str | list[dict[str:str]]]:
        params = []
        fields = get_all_intervention_parameter_fields()
        for valid_param in get_valid_intervention_parameter(intervention_instance):
            parameter = fields.get(valid_param)
            if valid_param in intervention_instance.parameters:
                if parameter is None:
                    raise ValueError(
                        f'Parameter "{valid_param}" not found for Intervention: "{intervention_instance.display_name()}"'
                    )
                entry = {
                    "label": str(parameter.label),
                    "name": str(valid_param),
                    "value": intervention_instance.parameters[valid_param],
                }
            else:
                entry = {
                    "label": str(parameter.label),
                    "name": str(valid_param),
                    "value": "",
                }

            params.append(entry)

        return {
            "id": intervention_instance.intervention.pk,
            "instance_pk": intervention_instance.pk,
            "title": intervention_instance.display_name(),
            "intervention_name": intervention_instance.intervention.name,
            "intervention_label": intervention_instance.label,
            "order": intervention_instance.order,
            "params": params,
            "currency": currency_code(analysis=intervention_instance.analysis),
        }

    def _parameter_field_name(self, field_name) -> str:
        return f"parameter__{field_name}"

    def parameter_fields(self):
        """
        Serves the parameter fields up dynamically for the template to render.
        """
        for field_name in self.fields:
            if "parameter__" in field_name:
                yield self[field_name]

    def clean_grants(self) -> str:
        grants = self.cleaned_data["grants"]
        if grants:
            grants = list(map(str.strip, grants.split(",")))
            for grant in grants:
                if not self._grant_is_valid(grant):
                    raise forms.ValidationError(f'Invalid grant format: "{grant}"')
            grants = ",".join(grants)
        return grants

    def clean_intervention_data(self) -> dict:
        intervention_data = self.cleaned_data["intervention_data"]
        errors = []
        for each_intervention_entry in intervention_data:
            if (
                each_intervention_entry.get("intervention_label")
                and len(each_intervention_entry.get("intervention_label", "")) > 100
            ):
                errors.append(
                    f"Intervention labels must be 100 characters or less."
                    f" {each_intervention_entry['intervention_label']} is too long."
                )
            if each_intervention_entry.get("params"):
                for each_param in each_intervention_entry.get("params"):
                    if not each_param.get("value"):
                        errors.append(
                            f"A value for the parameter \"{each_param['label']}\" "
                            f"on \"{each_intervention_entry['title']}\" is required."
                        )
        if errors:
            raise forms.ValidationError(errors)
        return intervention_data

    def _grant_is_valid(self, grant) -> bool:
        return True if re.match(r"^\S+$", grant) else False


class CategorizeCostTypeBulkForm(forms.Form):
    cost_type = forms.ModelChoiceField(CostType.objects)
    category = forms.ModelChoiceField(Category.objects)
    config_ids = forms.TypedMultipleChoiceField(coerce=int, widget=forms.MultipleHiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["config_ids"].choices = (
            (config_id, config_id) for config_id in kwargs["initial"]["config_ids"]
        )


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
        widget=CKEditorWidget(config_name="help_text_limitless"),
    )


class DefineInterventionsForm(forms.Form):
    interventions = AnalysisInterventionManageField()

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.request = kwargs.pop("request", "")
        super().__init__(*args, **kwargs)
        self.fields["interventions"].initial = self._get_interventions(self.request)

    def _get_interventions(self, request) -> list:
        if request:
            return json.loads(html.unescape(request.GET.get("data", "[]")))
        return []

    class Media:
        js = (
            "website/steps/define-form.js",
            "panels/lib/Sortable.js",
            "panels/js/json-manager-widget.js",
        )
        css = {"all": ("panels/css/panels-relation-widget.css",)}


class AnalysisInterventionForm(forms.Form):
    intervention = forms.ModelChoiceField(
        Intervention.objects,
        required=False,
    )
    intervention_label = forms.CharField(
        max_length=100,
        help_text="Optional custom name for the intervention being analyzed",
        required=False,
    )

    # for updating results view
    original_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    # store InterventionInstance pk if set
    instance_pk = forms.IntegerField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Inject intervention->parameters mapping into intervention field.
        self.mapping = get_intervention_parameter_mapping()

        self.fields["intervention"].widget.attrs.update(
            {
                "data-mapping": jsonattr(self.mapping),
            }
        )

        intervention_data = self._get_intervention_data(self.request)
        intervention_id = intervention_data.get("id")

        # Add fields for all possible parameters.  We do this because the form JS
        #   will need to display them when/if a new intervention is selected
        for parameter_name, field in get_all_intervention_parameter_fields().items():
            field_name = self._parameter_field_name(parameter_name)
            self.fields[field_name] = field
            self.fields[field_name].initial = None
            self.fields[field_name].widget.attrs["class"] = "parameter"

            # Set everything to Required as the default.  We'll adjust these
            # dynamically in JS
            self.fields[field_name].required = True

            # Update parameter requirement based on selected intervention.
            # Only runs when the form is being submitted.
            if self.data and self.data.get("intervention"):
                new_intervention_id = int(self.data.get("intervention"))
                if parameter_name not in self.mapping[new_intervention_id][0]:
                    self.fields[field_name].required = False

        # Set requirements for secondary output metric based on submitted data
        if self.data and self.data.get("intervention") and len(self.mapping[new_intervention_id]) > 1:
            new_intervention_id = int(self.data.get("intervention"))
            needs_required = False
            for parameter_name in self.mapping[new_intervention_id][1]:
                field_name = self._parameter_field_name(parameter_name)
                # Only consider fields that do not overlap the primary metric
                if self.data.get(field_name) and parameter_name not in self.mapping[new_intervention_id][0]:
                    # Propagating field requirement is only necessary when multiple secondary parameters exist
                    if len(self.mapping[new_intervention_id][1]) > 1:
                        needs_required = True

            if needs_required:
                for parameter_name in self.mapping[new_intervention_id][1]:
                    field_name = self._parameter_field_name(parameter_name)
                    self.fields[field_name].required = True

        # Set initial form values if received
        if intervention_id:
            self.fields["intervention"].initial = intervention_id
            self.fields["original_id"].initial = intervention_id
        if intervention_data.get("instance_pk"):
            self.fields["instance_pk"].initial = intervention_data.get("instance_pk")
        self.fields["intervention_label"].initial = intervention_data.get("intervention_label")
        for parameter in intervention_data.get("params", []):
            parameter_name = self._parameter_field_name(parameter.get("name"))
            self.fields[parameter_name].initial = parameter.get("value")

    def _parameter_field_name(self, field_name):
        return f"parameter__{field_name}"

    def _get_intervention_data(self, request: WSGIRequest | None) -> dict:
        data = request.GET.get("data", "")
        if data:
            return json.loads(html.unescape(data))
        else:
            return {}

    class Media:
        js = ("website/steps/intervention-edit-form.js",)
