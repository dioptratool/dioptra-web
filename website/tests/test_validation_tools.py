"""
Tests for the release-validation tooling: the validate_statuses and
ensure_all_analysis_endpoints_load management commands and the standalone
validation_scripts/find_diffs.py comparator.
"""

import csv
import datetime
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from website.management.commands.ensure_all_analysis_endpoints_load import Command as EndpointsCommand
from website.management.commands.validate_statuses import _first_intervention_metrics
from website.users.models import User
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
    UserFactory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIND_DIFFS = REPO_ROOT / "validation_scripts" / "find_diffs.py"


@pytest.mark.django_db
class TestValidateStatuses:
    def _saved_rows(self, tmp_path):
        out = tmp_path / "statuses.csv"
        call_command("validate_statuses", save=str(out), stdout=StringIO())
        with open(out, newline="") as csvfile:
            return {row["id"]: row for row in csv.DictReader(csvfile)}

    def test_save_handles_zero_intervention_analysis(self, defaults, tmp_path):
        analysis = AnalysisFactory()

        rows = self._saved_rows(tmp_path)

        row = rows[str(analysis.id)]
        assert row["output_cost"] == ""
        assert json.loads(row["output_costs_all"]) == {}
        assert json.loads(row["subcomponent_averages"]) == {}

    def test_save_includes_full_output_costs_and_subcomponent_averages(
        self, analysis_workflow_with_allocations, tmp_path
    ):
        analysis = analysis_workflow_with_allocations.analysis
        instance = analysis.interventioninstance_set.first()
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=instance,
            subcomponent_labels=["Treatment", "Outreach"],
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=analysis.cost_line_items.first().config,
            allocations={"0": "60", "1": "40"},
        )

        rows = self._saved_rows(tmp_path)

        row = rows[str(analysis.id)]
        assert json.loads(row["output_costs_all"]) == analysis.output_costs
        averages = json.loads(row["subcomponent_averages"])
        assert str(instance.id) in averages
        assert isinstance(averages[str(instance.id)], list)

    def test_first_intervention_metrics_shapes(self, defaults):
        analysis = AnalysisFactory()

        # No interventions, empty output_costs.
        assert _first_intervention_metrics(analysis) is None

        # Legacy v1.13 single-activity shape: metric ids at the top level.
        analysis.output_costs = {"NumberOfChildren": {"all": 5.0}}
        assert _first_intervention_metrics(analysis) == {"NumberOfChildren": {"all": 5.0}}

    def test_first_intervention_metrics_instance_keyed(self, analysis_workflow_with_allocations):
        analysis = analysis_workflow_with_allocations.analysis
        instance = analysis.interventioninstance_set.first()

        metrics = _first_intervention_metrics(analysis)

        assert metrics == analysis.output_costs[str(instance.id)]


class TestEndpointsCommandRecording:
    def test_check_url_records_non_200_without_debug(self):
        command = EndpointsCommand()
        client = SimpleNamespace(get=lambda url, follow=True: SimpleNamespace(status_code=500))
        analysis_data = (1, "Title", datetime.datetime(2026, 1, 1))

        command._check_url(client, analysis_data, "analysis/1/insights", "/analysis/1/insights", False)

        assert command.summary[analysis_data]["analysis/1/insights"] == "Status 500"

    def test_check_url_records_exceptions_without_debug(self):
        def boom(url, follow=True):
            raise RuntimeError("connection reset")

        command = EndpointsCommand()
        analysis_data = (1, "Title", datetime.datetime(2026, 1, 1))

        command._check_url(SimpleNamespace(get=boom), analysis_data, "label", "/x", False)

        assert command.summary[analysis_data]["label"] == "connection reset"


@pytest.mark.django_db
class TestEndpointsCommand:
    def test_all_step_urls_cover_substep_pages(self, analysis_workflow_with_allocations):
        analysis = analysis_workflow_with_allocations.analysis
        SubcomponentCostAnalysisFactory(
            intervention_instance=analysis.interventioninstance_set.first(),
            subcomponent_labels=["Treatment", "Outreach"],
        )
        special = CostLineItemFactory(
            analysis=analysis,
            grant_code="DF119",
            is_special_lump_sum=True,
        )
        CostLineItemConfigFactory(cost_line_item=special, cost_type=None, category=None)

        command = EndpointsCommand()
        urls = [url for _, url in command._urls_to_check(analysis.id, True, (analysis.id, "t", None))]

        assert not command.summary, "URL discovery must not record errors"
        assert any("/allocate-subcomponents/" in url for url in urls)
        assert any("/other-costs/" in url for url in urls)  # Other Supporting Costs page
        assert any(url.endswith("/download") for url in urls)

    def test_happy_path_records_no_failures(self, defaults):
        AnalysisFactory()
        admin = UserFactory(role=User.ADMIN)
        out = StringIO()

        call_command("ensure_all_analysis_endpoints_load", username=admin.email, stdout=out)

        assert "No errors found." in out.getvalue()

    def test_raises_command_error_on_failures(self, defaults, monkeypatch):
        AnalysisFactory()
        admin = UserFactory(role=User.ADMIN)
        monkeypatch.setattr(
            "django.test.Client.get",
            lambda self, url, follow=True: SimpleNamespace(status_code=500),
        )

        with pytest.raises(CommandError, match="endpoint failure"):
            call_command("ensure_all_analysis_endpoints_load", username=admin.email, stdout=StringIO())


def _write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_find_diffs(*args):
    return subprocess.run(
        [sys.executable, str(FIND_DIFFS), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


class TestFindDiffs:
    FIELDS = ["id", "status", "last_updated", "output_cost"]

    def _row(self, **overrides):
        row = {"id": "1", "status": "insights", "last_updated": "2026-01-01", "output_cost": "123.456"}
        row.update(overrides)
        return row

    def test_identical_files_exit_zero(self, tmp_path):
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        _write_csv(old, [self._row()], self.FIELDS)
        _write_csv(new, [self._row()], self.FIELDS)

        result = _run_find_diffs(old, new)

        assert result.returncode == 0
        assert "No differences found" in result.stdout

    def test_float_differences_within_tolerance_ignored(self, tmp_path):
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        _write_csv(old, [self._row(output_cost="123.45600000000001")], self.FIELDS)
        _write_csv(new, [self._row(output_cost="123.456")], self.FIELDS)

        result = _run_find_diffs(old, new)

        assert result.returncode == 0

    def test_json_columns_compared_with_tolerance(self, tmp_path):
        fields = [*self.FIELDS, "output_costs_all"]
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        _write_csv(old, [self._row(output_costs_all='{"7": {"M": {"all": 1.2300000001}}}')], fields)
        _write_csv(new, [self._row(output_costs_all='{"7": {"M": {"all": 1.23}}}')], fields)

        result = _run_find_diffs(old, new)

        assert result.returncode == 0

    def test_real_difference_exits_nonzero_and_no_fail_overrides(self, tmp_path):
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        _write_csv(old, [self._row(output_cost="100")], self.FIELDS)
        _write_csv(new, [self._row(output_cost="200")], self.FIELDS)

        result = _run_find_diffs(old, new)
        assert result.returncode == 1
        assert "output_cost" in result.stdout

        assert _run_find_diffs(old, new, "--no-fail").returncode == 0

    def test_allow_transition_ignores_status_change(self, tmp_path):
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        _write_csv(old, [self._row(status="set-contribution")], self.FIELDS)
        _write_csv(new, [self._row(status="categorize")], self.FIELDS)

        assert _run_find_diffs(old, new).returncode == 1
        result = _run_find_diffs(old, new, "--allow-transition", "set-contribution:categorize")
        assert result.returncode == 0

    def test_column_missing_from_one_file_is_skipped(self, tmp_path):
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        _write_csv(old, [self._row(output_costs_all="{}")], [*self.FIELDS, "output_costs_all"])
        _write_csv(new, [self._row()], self.FIELDS)

        assert _run_find_diffs(old, new).returncode == 0

    def test_unmatched_id_reports_containing_file_and_fails(self, tmp_path):
        old, new = tmp_path / "old.csv", tmp_path / "new.csv"
        _write_csv(old, [self._row()], self.FIELDS)
        _write_csv(new, [self._row(), self._row(id="2")], self.FIELDS)

        result = _run_find_diffs(old, new)

        assert result.returncode == 1
        assert f"ID 2 is only in {new}." in result.stdout
