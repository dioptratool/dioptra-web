from django.utils.translation import gettext as _

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


def intervention_parameters_display(intervention_instance: InterventionInstance) -> list[dict]:
    """
    Label/value pairs for an intervention instance's valid parameters, for display.
    """
    fields = get_all_intervention_parameter_fields()
    params = []
    for parameter_name in get_valid_intervention_parameter(intervention_instance):
        field = fields.get(parameter_name)
        if field is None:
            continue
        params.append(
            {
                "label": str(field.label),
                "value": intervention_instance.parameters.get(parameter_name, ""),
            }
        )
    return params


def get_intervention_output_metric_mapping() -> dict:
    mapping = {}
    for intervention in Intervention.objects.all():
        mapping[intervention.pk] = intervention.output_metrics
    return mapping


def get_parameter_field_name(parameter_name) -> str:
    return f"parameter__{parameter_name}"


def load_field_label_override(field_name: str, default=None, overrides=None):
    # Read current labels: a save in another worker cannot invalidate a process-local cache. A caller
    # resolving several labels in one request passes the singleton it already fetched as `overrides`.
    obj = overrides if overrides is not None else FieldLabelOverrides.get()
    if getattr(obj, f"{field_name}_overridden", False):
        return getattr(obj, field_name) or default
    return default


def transaction_header_labels(custom_fields=()):
    """
    The labels of the transaction table each cost item row opens (Site, Date, Amount, then one per
    given custom column, as listed by ``Analysis.transaction_custom_fields``), from one read of the
    overrides. Pages that list many rows put this in the context once, as
    ``transaction_header_labels``, instead of looking every label up again on every row. Translated
    like the ``label_override`` template filter.
    """
    overrides = FieldLabelOverrides.get()

    def label(field_name, default):
        return _(load_field_label_override(field_name, default, overrides=overrides))

    return {
        "site": label("tr_site_code", "Site"),
        "date": label("tr_date", "Date"),
        "amount": label("tr_amount", "Amount"),
        "custom": [label(column["label_key"], column["default_label"]) for column in custom_fields],
    }
