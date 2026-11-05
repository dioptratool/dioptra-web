#!/usr/bin/env bash
#
# preflight.sh
#
# Restores every *.backup in BACKUP_DIR into its own database (validation_<label>) and
# snapshots analysis statuses and output metrics with `validate_statuses`, so the
# snapshots can be compared after switching to the new version. Backups are processed
# JOBS at a time (default 4). Run it with the repo on the version the backups come from.
#
# Per-backup output: statuses/analysis_statuses-<label>-old.csv, with the step log in
# results/<label>-preflight.log.

set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source ./lib.sh

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-website.settings.local}"

BACKUP_DIR="${BACKUP_DIR:-backups}"
STATUSES_DIR="statuses"
RESULT_DIR="results"
mkdir -p "${STATUSES_DIR}" "${RESULT_DIR}"

if [ ! -d "${BACKUP_DIR}" ]; then
  echo "Error: Backup directory '${BACKUP_DIR}' does not exist." >&2
  exit 1
fi

preflight_one() {
  local backup_file="$1"
  local label db_name log
  label="$(label_for_backup "${backup_file}")"
  db_name="$(db_name_for_label "${label}")"
  log="${RESULT_DIR}/${label}-preflight.log"
  # Not `if ( ... )`: bash ignores `set -e` inside an if-condition, so failures would be masked.
  (
    set -euo pipefail
    export DATABASE_NAME="${db_name}"
    echo "Backup: ${backup_file}"
    echo "Database: ${db_name}"
    restore_backup "${backup_file}" "${db_name}"
    python ../manage.py migrate
    python ../manage.py validate_statuses --save "${STATUSES_DIR}/analysis_statuses-${label}-old.csv"
  ) > "${log}" 2>&1
  local rc=$?
  if [ "${rc}" -eq 0 ]; then
    echo "PASSED" > "${RESULT_DIR}/${label}.status"
  else
    echo "FAILED" > "${RESULT_DIR}/${label}.status"
    echo "Preflight FAILED for ${label} (exit ${rc}); see ${log}" >&2
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

echo "Preflight: ${#backup_files[@]} backup(s), ${JOBS} at a time, one database each (validation_<label>)."
if run_backups_in_parallel preflight_one "${RESULT_DIR}" "${backup_files[@]}"; then
  echo "All backups snapshot."
else
  echo "Preflight FAILED for one or more backups; see the logs noted above in ${RESULT_DIR}/." >&2
  exit 1
fi
