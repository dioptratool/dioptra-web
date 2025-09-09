import re

from django import forms
from django.forms import FileField, Form
from django.utils.translation import gettext as _

from ombucore.admin.forms.base import ModelFormBase
from ombucore.admin.templatetags.panels_extras import jsonattr
from website.forms.fields import PositiveFixedDecimalField
from website.forms.widgets import TagEditorWidget
from website.models.insight_comparison_data import InsightComparisonData
from website.models.intervention import Intervention
from website.models.output_metric import OUTPUT_METRICS
from website.models.utils import (
    get_all_intervention_parameter_fields,
    get_intervention_output_metric_mapping,
    get_intervention_parameter_mapping,
)
from .widgets import TemplateDownloadField


class UploadInsightComparisonDataForm(Form):
    mapping_file = FileField(
        label="Upload Cost Type Category Mapping File",
        required=True,
    )
    excel_template = TemplateDownloadField(
        template_path="excel_templates/insight_comparison_data_template.xlsx",
        label="Template",
    )


class InsightComparisonDataForm(ModelFormBase):
    class Meta:
        model = InsightComparisonData
        fields = [
            "name",
            "country",
            "grants",
            "intervention",
        ]
        widgets = {
            "grants": TagEditorWidget(options={"forceLowercase": False}),
        }

    class Media:
        js = ("website/js/admin/insight-comparison-data-form.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.intervention_parameter_mapping = get_intervention_parameter_mapping()
        self.intervention_output_metric_mapping = get_intervention_output_metric_mapping()

        # Inject intervention->parameters and intervention->output_metrics mappings
        # into intervention field.
        self.fields["intervention"].widget.attrs.update(
            {
                "data-intervention-parameter-mapping": jsonattr(self.intervention_parameter_mapping),
                "data-intervention-output-metric-mapping": jsonattr(self.intervention_output_metric_mapping),
            }
        )

        # Add fields for all possible parameters.
        for parameter_name, field in get_all_intervention_parameter_fields().items():
            field_name = self._parameter_field_name(parameter_name)
            self.fields[field_name] = field

            # Update parameter requirement based on selected intervention.
            # Only runs when the form is being submitted so all fields appear
            # required otherwise.
            self.fields[field_name].required = True
            if self.data and self.data.get("intervention"):
                intervention_id = int(self.data.get("intervention"))
                if parameter_name not in self.intervention_parameter_mapping[intervention_id]:
                    self.fields[field_name].required = False

        # Add fields for all possible output metric costs.
        for output_metric in OUTPUT_METRICS:
            base_label = output_metric.metric_name
            output_metric_id = output_metric.id
            field_name_all = self._output_metric_cost_all_field_name(output_metric_id)
            field_name_direct_only = self._output_metric_cost_direct_only_field_name(output_metric_id)
            self.fields[field_name_direct_only] = PositiveFixedDecimalField(
                label=f"{base_label} {_('(Program Costs only)')}",
                required=False,
            )
            self.fields[field_name_all] = PositiveFixedDecimalField(
                label="{label} {type}".format(
                    label=base_label,
                    type=_("(Including Program Costs, Support Costs, and Indirect Costs)"),
                ),
                required=False,
            )

            # Update output metric cost requirement based on selected intervention.
            # Only runs when the form is being submitted so all fields appear
            # required otherwise.
            if self.data and self.data.get("intervention"):
                intervention_id = int(self.data.get("intervention"))
                intervention = Intervention.objects.get(pk=intervention_id)
                if output_metric_id not in self.intervention_output_metric_mapping[intervention_id]:
                    self.fields[field_name_all].required = False
                    self.fields[field_name_direct_only].required = False

        # Unpack the `parameters` dict into initial values for the form.
        for parameter_name, value in self.instance.parameters.items():
            self.initial[self._parameter_field_name(parameter_name)] = value

        # Unpack the `costs` dict into initial values for the form.
        for output_metric_id, values in self.instance.output_costs.items():
            self.initial[self._output_metric_cost_all_field_name(output_metric_id)] = values.get("all", None)
            self.initial[self._output_metric_cost_direct_only_field_name(output_metric_id)] = values.get(
                "direct_only", None
            )

    def save(self, commit=True):
        self.instance.parameters = self._collect_parameters_data()
        self.instance.output_costs = self._collect_costs_data()
        return super().save(commit=commit)

    def _collect_parameters_data(self):
        data = {}
        intervention = self.cleaned_data["intervention"]

        intervention_parameters = self.intervention_parameter_mapping[intervention.id]
        for parameter_group in intervention_parameters:
            for parameter_name in parameter_group:
                field_name = self._parameter_field_name(parameter_name)
                if field_name in self.cleaned_data:
                    if self.cleaned_data[field_name]:
                        data[parameter_name] = float(self.cleaned_data[field_name])
                    else:
                        data[parameter_name] = None
        return data

    def _collect_costs_data(self):
        data = {}
        intervention = self.cleaned_data["intervention"]

        intervention_output_metrics = self.intervention_output_metric_mapping[intervention.id]
        for output_metric_id in intervention_output_metrics:
            data[output_metric_id] = {}
            field_name_all = self._output_metric_cost_all_field_name(output_metric_id)
            if field_name_all in self.cleaned_data:
                all_value = self.cleaned_data[field_name_all]
                if all_value:
                    all_value = float(all_value)
                data[output_metric_id]["all"] = all_value
            field_name_direct_only = self._output_metric_cost_direct_only_field_name(output_metric_id)
            if field_name_direct_only in self.cleaned_data:
                direct_only_value = self.cleaned_data[field_name_direct_only]
                if direct_only_value:
                    direct_only_value = float(direct_only_value)
                data[output_metric_id]["direct_only"] = direct_only_value

        return data

    def _parameter_field_name(self, parameter_name: str) -> str:
        return f"parameter__{parameter_name}"

    def _output_metric_cost_all_field_name(self, output_metric_id):
        return f"output_cost__all__{output_metric_id}"

    def _output_metric_cost_direct_only_field_name(self, output_metric_id):
        return f"output_cost__direct_only__{output_metric_id}"

    def parameter_fields(self):
        """
        Serves the parameter fields up dynamically for the template to render.
        """
        for field_name in self.fields:
            if "parameter__" in field_name:
                yield self[field_name]

    def clean_grants(self):
        grants = self.cleaned_data["grants"]
        if grants:
            grants = list(map(str.strip, grants.split(",")))
            for grant in grants:
                if not self._grant_is_valid(grant):
                    raise forms.ValidationError(f'Invalid grant format: "{grant}"')
            grants = ",".join(grants)
        return grants

    def _grant_is_valid(self, grant):
        return True if re.match(r"^\S+$", grant) else False

    def clean(self):
        cleaned_data = super().clean()
        intervention = cleaned_data.get("intervention")

        if intervention:
            parameter_groups = self.intervention_parameter_mapping[intervention.id]

            # flatten it to a single list of parameter names
            required_params = [p for group in parameter_groups for p in group]

            # track any missing ones
            missing = []
            for param in required_params:
                field_name = self._parameter_field_name(param)
                value = cleaned_data.get(field_name)
                if value in (None, ""):
                    missing.append(self.fields[field_name].label or param)
                    self.add_error(
                        field_name,
                        _("This parameter is required for the selected intervention."),
                    )

        return cleaned_data
