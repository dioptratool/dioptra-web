import os
from collections import defaultdict
from decimal import Decimal

from django.apps import apps

from website.models import Analysis
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
