#!/usr/bin/env bash
#
# validate_new_version.sh
#
# For every *.backup in BACKUP_DIR: restore it into its own database
# (validation_<label>), migrate, recompute output costs, check that every analysis
# endpoint loads, snapshot statuses, and diff them against the preflight snapshot.
# Backups are processed JOBS at a time (default 4); each step reaches its database
# through DATABASE_NAME.
#
# Per-backup output in results/: <label>-endpoints.md, <label>-diff.md, <label>.log
# (every step's output) and <label>.status (PASSED/FAILED). Exits non-zero when any
# backup shows endpoint failures or status/output differences, after processing them
# all, so one bad backup does not hide the rest.

set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source ./lib.sh

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-website.settings.local}"

# User the endpoint checks authenticate as (override with VALIDATION_USER=...)
VALIDATION_USER="${VALIDATION_USER:-analytics@dioptratool.org}"

BACKUP_DIR="${BACKUP_DIR:-backups}"
STATUSES_DIR="statuses"
RESULT_DIR="results"
mkdir -p "${STATUSES_DIR}" "${RESULT_DIR}"

if [ ! -d "${BACKUP_DIR}" ]; then
  echo "Error: Backup directory '${BACKUP_DIR}' does not exist." >&2
  exit 1
fi

validate_one() {
  local backup_file="$1"
  local label db_name log old_statuses new_statuses diff_statuses endpoint_check dates_file
  label="$(label_for_backup "${backup_file}")"
  db_name="$(db_name_for_label "${label}")"
  log="${RESULT_DIR}/${label}.log"
  old_statuses="${STATUSES_DIR}/analysis_statuses-${label}-old.csv"
  new_statuses="${STATUSES_DIR}/analysis_statuses-${label}-new.csv"
  diff_statuses="${RESULT_DIR}/analysis_statuses-${label}-diff.md"
  endpoint_check="${RESULT_DIR}/analysis_statuses-${label}-endpoints.md"
  dates_file="${STATUSES_DIR}/analysis_dates-${label}.csv"

  # Not `if ( ... )`: bash ignores `set -e` inside an if-condition, so a failed restore or
  # migrate would not stop the pipeline.
  (
    set -euo pipefail
    export DATABASE_NAME="${db_name}"
    echo "Backup: ${backup_file}"
    echo "Database: ${db_name}"
    if [ ! -f "${old_statuses}" ]; then
      echo "No preflight snapshot at ${old_statuses}; run preflight.sh on the old version first." >&2
      exit 1
    fi
    echo "Restoring..."
    restore_backup "${backup_file}" "${db_name}"
    echo "Migrating..."
    python ../manage.py migrate
    echo "Backing up analysis dates..."
    python ../manage.py backup_analysis_dates "${dates_file}"
    echo "Recomputing output costs..."
    python ../manage.py clear_output_costs
    echo "Restoring analysis dates..."
    python ../manage.py backup_analysis_dates --restore "${dates_file}"
    echo "Enabling the admin user..."
    python ../manage.py enable_admin_user
    echo "Validating that all endpoints load (this can take a long time)..."
    step_failed=0
    if ! python ../manage.py ensure_all_analysis_endpoints_load --all-step-urls --username "${VALIDATION_USER}" > "${endpoint_check}"; then
      echo "Endpoint failures; see ${endpoint_check}"
      step_failed=1
    fi
    echo "Snapshotting statuses..."
    python ../manage.py validate_statuses --save "${new_statuses}"
    echo "Comparing old and new statuses..."
    if ! python find_diffs.py "${old_statuses}" "${new_statuses}" > "${diff_statuses}"; then
      echo "Status/output differences; see ${diff_statuses}"
      step_failed=1
    fi
    exit "${step_failed}"
  ) > "${log}" 2>&1
  local rc=$?
  if [ "${rc}" -eq 0 ]; then
    echo "PASSED" > "${RESULT_DIR}/${label}.status"
  else
    echo "FAILED" > "${RESULT_DIR}/${label}.status"
    printf "\033[31mFAILED %s (exit %s) — see %s\033[0m\n" "${label}" "${rc}" "${log}" >&2
  fi
}

backup_files=()
for backup_file in "${BACKUP_DIR}"/*.backup; do
  [ -e "${backup_file}" ] && backup_files+=("${backup_file}")
done
if [ "${#backup_files[@]}" -eq 0 ]; then
  echo "No .backup files found in '${BACKUP_DIR}'." >&2
  exit 1
fi

echo "Validating ${#backup_files[@]} backup(s), ${JOBS} at a time, one database each (validation_<label>)."
if run_backups_in_parallel validate_one "${RESULT_DIR}" "${backup_files[@]}"; then
  printf "\033[32mAll backups PASSED.\033[0m\n"
else
  printf "\033[31mValidation FAILED — see the -diff.md / -endpoints.md / .log files in %s/.\033[0m\n" "${RESULT_DIR}" >&2
  exit 1
fi
