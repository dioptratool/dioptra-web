# Quickstart

### One-shot: validate between two git refs

The whole preflight → validate cycle, no manual branch switching:

```shell
make validate-release-range OLD=v2.1 NEW=v2.2-rc4 BACKUPS=~/dioptra-backups
```

This checks out `OLD`, snapshots every `*.backup` in `BACKUPS` (default `validation_scripts/backups`), checks
out `NEW`, runs the full validation for every backup, restores your original checkout (even on failure), and
writes per-backup reports plus `summary-<old>-vs-<new>.md` to `validation_scripts/results/`. Exits non-zero on
any failure. Requires a clean working tree (untracked files are fine) and the Docker databases running; `NEW`
must contain the current validation tooling. Both phases run in your current virtualenv.

The two-step flow below still works when you want to run the phases separately (e.g. the backups were snapshot
on another machine). Both scripts honor `BACKUP_DIR=/path` as an override for `validation_scripts/backups`.

### Backporting the tooling to an old release

The enhanced snapshot columns (`output_costs_all`, `subcomponent_averages`) only participate when the OLD side
also writes them. To get that on the first cycle, cherry-pick the validation-tooling commit onto a branch from
the old baseline and use that branch as `OLD`:

```shell
git branch validation-tooling-2.0 f118e696b4c59d791b9ac80e8eebe78f9d9dfe09   # 2.0 baseline (Jan 2026)
git checkout validation-tooling-2.0
git cherry-pick -x <tooling-commit-sha>          # applies cleanly: the touched files are unchanged since 2.0
git rm website/tests/test_validation_tools.py    # optional: a few tests use 2.2-shaped factories
git commit -m "Tooling branch: drop 2.2-shaped tests"
git checkout <your-release-branch>
make validate-release-range OLD=validation-tooling-2.0 NEW=<your-release-branch> BACKUPS=~/backups
```

`validate_statuses` is deliberately dual-shape: on pre-2.2 refs it reads the analysis-level
`SubcomponentCostAnalysis` and keys it by the first intervention instance by `(order, id)` — the same instance
migration `0002_intervention_subcomponents` attaches it to during the upgrade — so old and new
`subcomponent_averages` line up row-for-row across the migration.

### Preflight

Use the `make backup-all` command in the infrastructure repo.   
Download all the backups that you'd like to validate and put them in the `validation_scripts/backups` directory

With the repo on `main` (or whatever the current version is for the backups) run:

```shell
make validate-release-preflight
``` 
This will save the current Statuses and Output Costs for all Analyses for each Backup

### Validate

###### IMPORTANT: The transaction store DB must be running (unpopulated is fine) — see the note below.

Switch to new branch whose changes you'd like to observe.

Run:

```shell
make validate-release
```

This will validate that all endpoints load and compare the statuses and output costs that were saved in the
preflight. The endpoint check authenticates as `analytics@dioptratool.org` by default — override with
`VALIDATION_USER=someone@example.org make validate-release`.

Results are written to `validation_scripts/results/` as markdown (`-endpoints.md`, `-diff.md`). The command
exits non-zero when any backup shows endpoint failures or status/output differences, so it can gate a release.

What is compared per analysis: workflow status, `last_updated`, the legacy single `output_cost` number, the
full `output_costs` JSON (all interventions × metrics, numeric tolerance), and the live-computed sub-component
averages per intervention. The last two columns only participate once the *preflight* CSV also contains them —
i.e. the first release cycle after they were introduced still compares the legacy columns only.

The endpoint check visits every workflow step AND sub-step URL per analysis (per-grant allocate pages,
Other Supporting Costs, sub-component pages, Add Other Costs pages) plus the spreadsheet download
(`ensure_all_analysis_endpoints_load --all-step-urls`).

If a release intentionally changes statuses (e.g. a step was removed), ignore those transitions instead of
editing code:

```shell
python find_diffs.py old.csv new.csv --allow-transition set-contribution:categorize --allow-transition fix-missing-data:load-data
```

(`--no-fail` makes find_diffs informational-only.)


----

Note: The transaction store DB container must be **running** (`make up` starts it). Populating it via the
Transaction Pipeline (steps below) is desirable but not required: an unpopulated store just means the
load-data page shows a transaction count of 0 for analyses that haven't loaded data yet, and store counts are
never snapshotted or diffed, so validation results are identical either way. (Without the store running at
all, the pages still render — the query is error-guarded — but every pre-load analysis logs an exception and
shows an inline error message, so keep the container up.)

Pipeline repository: https://github.com/dioptratool/dioptra-service-transaction-pipeline

 Quickstart Guide for the Transaction Pipeline:
 These commands are run in the dioptra-service-transaction-pipeline project root 
 
Build the project:

```shell
make build
make up
```
Generate sample data:

```shell
make gen-test-data
```

Import test the sample data:
```shell
make testimport-transactionscsv
```