#!/usr/bin/env bash
#
# validate_release_range.sh OLD_REF NEW_REF [BACKUP_DIR]
#
# Runs the whole release validation without manual branch switching:
#   1. checks out OLD_REF and snapshots statuses/output costs for every backup
#      (the preflight — inlined here rather than calling OLD_REF's
#      preflight.sh, so it works on refs that predate these scripts),
#   2. checks out NEW_REF and runs its validate_new_version.sh (recompute,
#      endpoint checks, snapshot, diff) for every backup,
#   3. restores your original checkout (even on failure) and writes a summary
#      to validation_scripts/results/.
#
# Every backup gets its own database, validation_<label>, on the local Postgres
# container, and backups are processed JOBS at a time (default 4) in both phases.
# The databases are left in place for inspection; `make validate-release-cleanup`
# drops them.
#
# Requirements: a CLEAN working tree (the script refuses otherwise), the local
# Docker databases running, and NEW_REF containing the current validation
# tooling (a validate_new_version.sh that honors BACKUP_DIR and JOBS). The OLD
# ref must read DATABASE_NAME in its settings (every release since 2.0 does).
#
# Note: both phases run in your current virtualenv. If the two refs need
# incompatible dependencies, handle that yourself between runs.
#
# The whole script body lives in functions and main is the last line: bash parses
# the entire file before executing, so the git checkouts below cannot yank the
# script out from under the running interpreter. For the same reason the helpers
# below are a copy of lib.sh rather than a `source`: after the checkout, lib.sh on
# disk belongs to whichever ref is checked out (or does not exist at all).

set -euo pipefail

ORIGINAL_REF=""
JOBS="${JOBS:-4}"
VALIDATION_DB_HOST="${DATABASE_HOST:-127.0.0.1}"
VALIDATION_DB_PORT="${DATABASE_PORT:-12432}"
VALIDATION_DB_USER="${DATABASE_USER:-dioptra}"
export PGPASSWORD="${PGPASSWORD:-${DATABASE_PASSWORD:-}}"

usage() {
  echo "Usage: $0 OLD_REF NEW_REF [BACKUP_DIR]" >&2
  echo "  e.g. $0 v2.3.1 v2.5-rc1 ~/dioptra-backups" >&2
  echo "  BACKUP_DIR defaults to validation_scripts/backups; JOBS=<n> sets the parallelism (default 4)" >&2
  exit 2
}

label_for_backup() {
  # Strip ".backup" and any trailing '-YYYY-MM-DD_hh-mm-ss-TZ' suffix (24 chars).
  local filename_noext
  filename_noext="$(basename "$1" .backup)"
  if [[ ${#filename_noext} -ge 24 ]]; then
    echo "${filename_noext:0:$((${#filename_noext}-24))}"
  else
    echo "${filename_noext}"
  fi
}

db_name_for_label() {
  local slug
  slug="$(echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c '[:alnum:]\n' '_')"
  echo "validation_${slug}" | cut -c1-63
}

_psql_admin() {
  psql -q -X -h "${VALIDATION_DB_HOST}" -p "${VALIDATION_DB_PORT}" -U "${VALIDATION_DB_USER}" -d postgres "$@"
}

restore_backup() {
  local backup_file="$1" db_name="$2"
  _psql_admin -c "DROP DATABASE IF EXISTS \"${db_name}\";"
  _psql_admin -c "CREATE DATABASE \"${db_name}\" OWNER \"${VALIDATION_DB_USER}\";"
  if ! pg_restore --no-owner --no-privileges -h "${VALIDATION_DB_HOST}" -p "${VALIDATION_DB_PORT}" \
      -U "${VALIDATION_DB_USER}" -d "${db_name}" "${backup_file}"; then
    echo "pg_restore reported errors for ${db_name}; retrying through plain SQL"
    local sql_file
    sql_file="$(mktemp -t validation-restore).sql"
    pg_restore --no-owner --no-privileges -f "${sql_file}" "${backup_file}"
    _psql_admin -c "DROP DATABASE IF EXISTS \"${db_name}\";"
    _psql_admin -c "CREATE DATABASE \"${db_name}\" OWNER \"${VALIDATION_DB_USER}\";"
    psql -q -X -h "${VALIDATION_DB_HOST}" -p "${VALIDATION_DB_PORT}" -U "${VALIDATION_DB_USER}" \
      -d "${db_name}" -f "${sql_file}" > /dev/null
    rm -f "${sql_file}"
  fi
}

run_backups_in_parallel() {
  # run_backups_in_parallel FUNCTION STATUS_DIR BACKUP_FILE... (see lib.sh)
  local function_name="$1" status_dir="$2"
  shift 2
  local backup_file label
  for backup_file in "$@"; do
    label="$(label_for_backup "${backup_file}")"
    rm -f "${status_dir}/${label}.status"
    while [[ "$(jobs -rp | wc -l | tr -d ' ')" -ge "${JOBS}" ]]; do
      sleep 2
    done
    echo "[$(date '+%H:%M:%S')] start  ${label}"
    "${function_name}" "${backup_file}" &
  done
  wait
  local failures=0 status
  for backup_file in "$@"; do
    label="$(label_for_backup "${backup_file}")"
    status="$(cat "${status_dir}/${label}.status" 2>/dev/null || echo "MISSING")"
    echo "[$(date '+%H:%M:%S')] finish ${label}: ${status}"
    [[ "${status}" == "PASSED" ]] || failures=$((failures + 1))
  done
  return "${failures}"
}

restore_original_checkout() {
  if [[ -n "${ORIGINAL_REF}" ]]; then
    echo "Restoring original checkout: ${ORIGINAL_REF}"
    git checkout -q "${ORIGINAL_REF}"
  fi
}

# Phase 1 worker: restore, migrate on the OLD ref, snapshot. Uses the globals set in main.
preflight_one() {
  local backup_file="$1"
  local label db_name log
  label="$(label_for_backup "${backup_file}")"
  db_name="$(db_name_for_label "${label}")"
  log="${RESULTS_DIR}/${label}-preflight.log"
  # Not `if ( ... )`: bash ignores `set -e` inside an if-condition, so failures would be masked.
  (
    set -euo pipefail
    export DATABASE_NAME="${db_name}"
    echo "Backup: ${backup_file}"
    echo "Database: ${db_name}"
    restore_backup "${backup_file}" "${db_name}"
    python manage.py migrate
    python manage.py validate_statuses --save "${STATUSES_DIR}/analysis_statuses-${label}-old.csv"
  ) > "${log}" 2>&1
  local rc=$?
  if [ "${rc}" -eq 0 ]; then
    echo "PASSED" > "${RESULTS_DIR}/${label}.status"
  else
    echo "FAILED" > "${RESULTS_DIR}/${label}.status"
    echo "Preflight FAILED for ${label} (exit ${rc}); see ${log}" >&2
  fi
}

main() {
  [[ $# -lt 2 ]] && usage
  local old_ref="$1"
  local new_ref="$2"

  local repo_root
  repo_root="$(cd "$(dirname "$0")/.." && pwd)"
  cd "${repo_root}"

  local backup_dir_arg="${3:-${repo_root}/validation_scripts/backups}"
  local backup_dir
  backup_dir="$(cd "${backup_dir_arg}" 2>/dev/null && pwd)" || {
    echo "Backup directory not found: ${backup_dir_arg}" >&2
    exit 2
  }

  git rev-parse --verify --quiet "${old_ref}^{commit}" >/dev/null || {
    echo "Cannot resolve OLD ref: ${old_ref}" >&2
    exit 2
  }
  git rev-parse --verify --quiet "${new_ref}^{commit}" >/dev/null || {
    echo "Cannot resolve NEW ref: ${new_ref}" >&2
    exit 2
  }

  local backup_files=()
  local backup_file label
  for backup_file in "${backup_dir}"/*.backup; do
    [[ -e "${backup_file}" ]] && backup_files+=("${backup_file}")
  done
  if [[ "${#backup_files[@]}" -eq 0 ]]; then
    echo "No *.backup files found in ${backup_dir}" >&2
    exit 2
  fi

  # Untracked files (the QA plan, local backups) survive checkouts safely;
  # only modifications to tracked files make switching refs dangerous.
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Working tree has uncommitted changes — commit or stash first; this script switches git refs." >&2
    exit 2
  fi

  export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-website.settings.local}"

  STATUSES_DIR="${repo_root}/validation_scripts/statuses"
  RESULTS_DIR="${repo_root}/validation_scripts/results"
  mkdir -p "${STATUSES_DIR}" "${RESULTS_DIR}"

  local old_short new_short
  old_short="$(git rev-parse --short "${old_ref}")"
  new_short="$(git rev-parse --short "${new_ref}")"
  local summary_file="${RESULTS_DIR}/summary-${old_short}-vs-${new_short}.md"

  ORIGINAL_REF="$(git symbolic-ref --short -q HEAD || git rev-parse HEAD)"
  trap restore_original_checkout EXIT

  echo "======================================================"
  echo "Phase 1/2: preflight snapshots on OLD ref ${old_ref} (${old_short})"
  echo "  ${#backup_files[@]} backup(s), ${JOBS} at a time, one database each (validation_<label>)"
  echo "======================================================"
  git checkout -q "${old_ref}"
  if ! run_backups_in_parallel preflight_one "${RESULTS_DIR}" "${backup_files[@]}"; then
    echo "Preflight failed for one or more backups; see the -preflight.log files in ${RESULTS_DIR}/." >&2
    exit 1
  fi

  echo "======================================================"
  echo "Phase 2/2: validation on NEW ref ${new_ref} (${new_short})"
  echo "======================================================"
  git checkout -q "${new_ref}"
  if [[ ! -x validation_scripts/validate_new_version.sh ]]; then
    echo "NEW ref has no validation_scripts/validate_new_version.sh — it must contain the validation tooling." >&2
    exit 2
  fi
  local validation_status="PASSED"
  if ! (cd validation_scripts && BACKUP_DIR="${backup_dir}" JOBS="${JOBS}" ./validate_new_version.sh); then
    validation_status="FAILED"
  fi

  {
    echo "# Release validation: ${old_ref} (${old_short}) -> ${new_ref} (${new_short})"
    echo
    echo "- Ran: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "- Backups: ${backup_dir}"
    echo "- Result: **${validation_status}**"
    echo
    echo "Per-backup reports (database validation_<label> is left in place for inspection):"
    for backup_file in "${backup_files[@]}"; do
      label="$(label_for_backup "${backup_file}")"
      echo "- ${label}: $(cat "${RESULTS_DIR}/${label}.status" 2>/dev/null || echo MISSING) — [diff](analysis_statuses-${label}-diff.md), [endpoints](analysis_statuses-${label}-endpoints.md), [log](${label}.log)"
    done
  } > "${summary_file}"

  echo "======================================================"
  cat "${summary_file}"
  echo "Summary written to ${summary_file}"

  [[ "${validation_status}" == "PASSED" ]] || exit 1
}

main "$@"
