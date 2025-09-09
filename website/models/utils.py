from functools import lru_cache

from django.urls import reverse

from . import FieldLabelOverrides
from .intervention import Intervention
from .intervention_instance import InterventionInstance
from .output_metric import OUTPUT_METRICS, OUTPUT_METRICS_BY_ID


def get_all_intervention_parameter_fields() -> dict:
    parameters = {}
    for output_metric in OUTPUT_METRICS:
        parameters.update(output_metric.parameters)
    return parameters


def get_valid_intervention_parameter(an_intervention_instance: InterventionInstance) -> list[str]:
    valid_parameters = set()
    for output_metric in an_intervention_instance.intervention.output_metrics:
        for parameter in OUTPUT_METRICS_BY_ID[output_metric].parameters:
            valid_parameters.add(parameter)
    return list(valid_parameters)


def get_intervention_parameter_mapping() -> dict[int, list[str]]:
    mapping = {}
    for intervention in Intervention.objects.all():
        intervention_fields = []
        for output_metric in intervention.output_metric_objects():
            intervention_fields.append(list(output_metric.parameters.keys()))
        mapping[intervention.pk] = intervention_fields
    return mapping


def get_intervention_output_metric_mapping() -> dict:
    mapping = {}
    for intervention in Intervention.objects.all():
        mapping[intervention.pk] = intervention.output_metrics
    return mapping


def build_intervention_instance_data(kwargs) -> dict:
    intervention_id = int(kwargs["data"].get("intervention"))
    intervention = Intervention.objects.get(pk=intervention_id)

    if kwargs["data"].get("intervention_label"):
        label = kwargs["data"].get("intervention_label")
    else:
        label = intervention.name

    intervention_data = {
        "id": intervention_id,
        "intervention_name": intervention.name,
        "title": label,
        "params": [],
        "change_url": reverse("analysis-define-interventions-edit"),
    }
    if kwargs["data"].get("original_id"):
        intervention_data["original_id"] = int(kwargs["data"].get("original_id"))
    if kwargs["data"].get("instance_pk"):
        intervention_data["instance_pk"] = int(kwargs["data"].get("instance_pk"))
    if kwargs["data"].get("intervention_label"):
        intervention_data["intervention_label"] = kwargs["data"].get("intervention_label")

    mapping = get_intervention_parameter_mapping()
    intervention_parameters = mapping[intervention_id]

    for parameter_name, field in get_all_intervention_parameter_fields().items():
        for output_metric_parameters in intervention_parameters:
            if parameter_name in output_metric_parameters:
                field_name = get_parameter_field_name(parameter_name)
                if kwargs["data"].get(field_name):
                    intervention_data["params"].append(
                        {
                            "label": str(field.label),
                            "name": parameter_name,
                            "value": kwargs["data"].get(field_name),
                        }
                    )
    return intervention_data


def get_parameter_field_name(parameter_name) -> str:
    return f"parameter__{parameter_name}"


@lru_cache(maxsize=1)
def _get_overrides() -> FieldLabelOverrides:
    """Singleton lookup, cached until a save/delete clears it."""
    return FieldLabelOverrides.get()


def load_field_label_override(field_name: str, default=None):
    obj = _get_overrides()
    if getattr(obj, f"{field_name}_overridden", False):
        return getattr(obj, field_name) or default
    return default
