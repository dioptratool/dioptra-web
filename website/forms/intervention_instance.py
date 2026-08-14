import copy

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _l

from ombucore.admin.forms.base import ModelFormBase
from ombucore.admin.templatetags.panels_extras import jsonattr
from website.models import CostLineItemInterventionAllocation, Intervention, InterventionInstance
from website.models.utils import (
    get_all_intervention_parameter_fields,
    get_intervention_parameter_mapping,
    get_parameter_field_name,
)


class InterventionInstanceForm(ModelFormBase):
    """
    Panel form for an intervention being analyzed. All possible output-metric
    parameter fields are added to the form; `intervention-edit-form.js`
    shows/requires the ones relevant to the selected intervention.
    """

    # This panel uses Django for validation and JavaScript to mark the active
    # metric inputs as required. Omitting the HTML attribute also preserves the
    # field order from Meta instead of triggering the legacy flex-order rule.
    use_required_attribute = False

    class Meta:
        model = InterventionInstance
        fields = ["intervention", "label"]
        labels = {"label": _l("Intervention label")}
        help_texts = {"label": _l("Optional custom name for the intervention being analyzed")}

    class Media:
        js = ("website/steps/intervention-edit-form.js",)

    def __init__(self, *args, analysis=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.analysis = analysis or (self.instance.analysis if self.instance.pk else None)

        # Inject intervention->parameters mapping into the intervention field.
        self.mapping = get_intervention_parameter_mapping()
        self.fields["intervention"].widget.attrs.update(
            {
                "data-mapping": jsonattr(self.mapping),
            }
        )

        # Add fields for all possible parameters. We do this because the form JS
        # will need to display them when/if a new intervention is selected.
        submitted_intervention_id = self._submitted_intervention_id()
        for parameter_name, field in get_all_intervention_parameter_fields().items():
            field = copy.deepcopy(field)
            field_name = get_parameter_field_name(parameter_name)
            self.fields[field_name] = field
            field.initial = None
            field.widget.attrs["class"] = "parameter"

            # Set everything to Required as the default. We'll adjust these
            # dynamically in JS.
            field.required = True

            # Update parameter requirement based on the submitted intervention.
            if submitted_intervention_id is not None:
                metrics = self.mapping.get(submitted_intervention_id) or [[]]
                if parameter_name not in metrics[0]:
                    field.required = False

        # Set requirements for the secondary output metric based on submitted data.
        if submitted_intervention_id is not None:
            metrics = self.mapping.get(submitted_intervention_id) or []
            if len(metrics) > 1:
                primary, secondary = metrics[0], metrics[1]
                needs_required = False
                for parameter_name in secondary:
                    field_name = get_parameter_field_name(parameter_name)
                    # Only consider fields that do not overlap the primary metric.
                    # Propagating the requirement is only necessary when multiple
                    # secondary parameters exist.
                    if self.data.get(field_name) and parameter_name not in primary:
                        if len(secondary) > 1:
                            needs_required = True
                if needs_required:
                    for parameter_name in secondary:
                        self.fields[get_parameter_field_name(parameter_name)].required = True

        # Seed parameter values when editing an existing instance.
        if self.instance.pk:
            for parameter_name, value in self.instance.parameters.items():
                field_name = get_parameter_field_name(parameter_name)
                if field_name in self.fields:
                    self.fields[field_name].initial = value

    def _submitted_intervention_id(self) -> int | None:
        if self.data and self.data.get("intervention"):
            try:
                return int(self.data.get("intervention"))
            except (TypeError, ValueError):
                return None
        return None

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and self.analysis:
            if self.analysis.interventioninstance_set.count() >= settings.MAX_ANALYSIS_INTERVENTIONS:
                raise ValidationError(
                    _l("No more than %(limit)s interventions are allowed.")
                    % {"limit": settings.MAX_ANALYSIS_INTERVENTIONS},
                    code="invalid",
                )
        return cleaned_data

    def save(self, commit=True):
        if not self.instance.pk:
            self.instance.analysis = self.analysis
            # Must be None so InterventionInstance.save() appends it to the end.
            self.instance.order = None
        elif "intervention" in self.changed_data:
            self._clear_dependent_data()
        self.instance.parameters = self._collect_parameters(self.cleaned_data["intervention"])
        return super().save(commit=commit)

    def _collect_parameters(self, intervention: Intervention) -> dict[str, float]:
        parameters = {}
        for metric_parameters in self.mapping.get(intervention.pk, []):
            for parameter_name in metric_parameters:
                value = self.cleaned_data.get(get_parameter_field_name(parameter_name))
                if value is not None:
                    parameters[parameter_name] = float(value)
        return parameters

    def _clear_dependent_data(self) -> None:
        # Changing the intervention type invalidates the sub-component analysis
        # and any allocations made against the previous intervention.
        if hasattr(self.instance, "subcomponent_cost_analysis"):
            self.instance.subcomponent_cost_analysis.delete()
        CostLineItemInterventionAllocation.objects.filter(intervention_instance=self.instance).delete()
