import os
from collections import defaultdict
from decimal import Decimal

from django.apps import apps

from website.intervention_metadata import validate_number
from website.models import (
    Analysis,
    InterventionMetadataField,
    InterventionMetadataOption,
    MetadataFieldType,
)
from website.workflows import AnalysisWorkflow
from website.workflows._steps_base import SubStep


class BulkCreateManager:
    """
    This helper class keeps track of ORM objects to be created for multiple
    model classes, and automatically creates those objects with `bulk_create`
    when the number of objects accumulated for a given model class exceeds
    `chunk_size`.
    Upon completion of the loop that's `add()`ing objects, the developer must
    call `done()` to ensure the final set of objects is created for all models.
    """

    def __init__(self, chunk_size=100):
        self._create_queues = defaultdict(list)
        self.chunk_size = chunk_size

    def _commit(self, model_class):
        model_key = model_class._meta.label
        model_class.objects.bulk_create(self._create_queues[model_key])
        self._create_queues[model_key] = []

    def add(self, obj):
        """
        Add an object to the queue to be created, and call bulk_create if we
        have enough objs.
        """
        model_class = type(obj)
        model_key = model_class._meta.label
        self._create_queues[model_key].append(obj)
        if len(self._create_queues[model_key]) >= self.chunk_size:
            self._commit(model_class)

    def done(self):
        """
        Always call this upon completion to make sure the final partial chunk
        is saved.
        """
        for model_name, objs in self._create_queues.items():
            if len(objs) > 0:
                self._commit(apps.get_model(model_name))


def get_cli_option(options, flag: str, envvar=None, required=False):
    """Return an option from the CLI, or fall back to an environment variable.

    envvar is the name of the environment variable;
    by default it will transform 'foo-bar' would look for 'FOO_BAR'.
    """
    key = flag.replace("-", "_")
    if options.get(key) is not None:
        return options.get(key)
    envvar = envvar or key.upper()
    if envvar in os.environ:
        return os.environ[envvar]
    if required:
        raise RuntimeError(f"Option missing, pass {flag} flag, or set {envvar} env var")
    return None


def parse_csv_currency_to_decimal(value):
    if value:
        return Decimal(clean_csv_number(value))
    return value


def clean_csv_number(value):
    if value:
        value = value.replace("$", "")
        value = value.replace(",", "")
    return value


def _get_last_completed_step_name(analysis: Analysis):
    completed_step = AnalysisWorkflow(analysis=analysis).get_last_complete()

    if completed_step is None:
        return "NO STEPS COMPLETED"
    if isinstance(completed_step, SubStep):
        completed_step = completed_step.parent

    return completed_step.name


def _check_analysis_status(analysis: Analysis, expected_step_name: str) -> None:
    completed_step = _get_last_completed_step_name(analysis)
    assert (
        completed_step == expected_step_name
    ), f'Expected the last completed step for "{analysis.title}" to be: {expected_step_name} but got {completed_step}'


def seed_metadata_definitions(intervention, specs: list[dict]) -> dict[str, InterventionMetadataField]:
    """
    Create an intervention's metadata fields, and their options, from seed specs in the given order.

    A spec has ``name``, ``field_type``, ``number_type`` for a Number field and ``options`` (labels)
    for a choice field. Returns the fields by name.
    """
    fields = {}
    for order, spec in enumerate(specs):
        field = InterventionMetadataField.objects.create(
            intervention=intervention,
            name=spec["name"],
            field_type=spec["field_type"],
            number_type=spec.get("number_type"),
            order=order,
        )
        for option_order, label in enumerate(spec.get("options", [])):
            InterventionMetadataOption.objects.create(field=field, label=label, order=option_order)
        fields[field.name] = field
    return fields


def metadata_values(intervention, values: dict) -> dict:
    """
    The stored metadata dict for readable seed values keyed by field name.

    Option labels become option keys (a list for a multiple-choice field, which also accepts one
    label), numbers are validated for their type, text is stored as given. An unknown field name
    or option label raises ValueError so a typo fails the build, as a bad parameter does.
    """
    definitions = {
        definition.name: definition for definition in intervention.metadata_fields.prefetch_related("options")
    }
    stored = {}
    for name, value in values.items():
        definition = definitions.get(name)
        if definition is None:
            raise ValueError(f"{intervention.name!r} has no metadata field {name!r}")
        if definition.is_choice:
            keys_by_label = {option.label: option.storage_key for option in definition.options.all()}
            labels = value if isinstance(value, list) else [value]
            for label in labels:
                if label not in keys_by_label:
                    raise ValueError(f"{intervention.name!r} field {name!r} has no option {label!r}")
            if definition.field_type == MetadataFieldType.SINGLE_CHOICE:
                if len(labels) != 1:
                    raise ValueError(f"{intervention.name!r} field {name!r} takes one option")
                stored[definition.storage_key] = keys_by_label[labels[0]]
            else:
                stored[definition.storage_key] = [keys_by_label[label] for label in labels]
        elif definition.is_number:
            stored[definition.storage_key] = validate_number(str(value), definition.number_type)
        else:
            stored[definition.storage_key] = str(value)
    return stored
