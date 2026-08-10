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
# Requirements: a CLEAN working tree (the script refuses otherwise), the local
# Docker databases running, and NEW_REF containing the current validation
# tooling (a validate_new_version.sh that honors BACKUP_DIR).
#
# Note: both phases run in your current virtualenv. If the two refs need
# incompatible dependencies, handle that yourself between runs.
#
# The whole script body lives in main() and main is the last line: bash parses
# the entire file before executing, so the git checkouts below cannot yank the
# script out from under the running interpreter.

set -euo pipefail

ORIGINAL_REF=""

usage() {
  echo "Usage: $0 OLD_REF NEW_REF [BACKUP_DIR]" >&2
  echo "  e.g. $0 v2.1 v2.2-rc4 ~/dioptra-backups" >&2
  echo "  BACKUP_DIR defaults to validation_scripts/backups" >&2
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

restore_db() {
  # load-sql is the Postgres-17-safe restore; fall back for refs without it.
  if make -n load-sql >/dev/null 2>&1; then
    BACKUP="$1" make load-sql
  else
    BACKUP="$1" make restore-db-pgdump
  fi
  make migrate
}

restore_original_checkout() {
  if [[ -n "${ORIGINAL_REF}" ]]; then
    echo "Restoring original checkout: ${ORIGINAL_REF}"
    git checkout -q "${ORIGINAL_REF}"
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

  if ! compgen -G "${backup_dir}/*.backup" >/dev/null; then
    echo "No *.backup files found in ${backup_dir}" >&2
    exit 2
  fi

  # Untracked files (the QA plan, local backups) survive checkouts safely;
  # only modifications to tracked files make switching refs dangerous.
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Working tree has uncommitted changes — commit or stash first; this script switches git refs." >&2
    exit 2
  fi

  export DJANGO_SETTINGS_MODULE="website.settings.local"

  local statuses_dir="${repo_root}/validation_scripts/statuses"
  local results_dir="${repo_root}/validation_scripts/results"
  mkdir -p "${statuses_dir}" "${results_dir}"

  local old_short new_short
  old_short="$(git rev-parse --short "${old_ref}")"
  new_short="$(git rev-parse --short "${new_ref}")"
  local summary_file="${results_dir}/summary-${old_short}-vs-${new_short}.md"

  ORIGINAL_REF="$(git symbolic-ref --short -q HEAD || git rev-parse HEAD)"
  trap restore_original_checkout EXIT

  echo "======================================================"
  echo "Phase 1/2: preflight snapshots on OLD ref ${old_ref} (${old_short})"
  echo "======================================================"
  git checkout -q "${old_ref}"
  local backup_file label
  for backup_file in "${backup_dir}"/*.backup; do
    label="$(label_for_backup "${backup_file}")"
    echo "--- Preflight for ${label} (${backup_file})"
    restore_db "${backup_file}"
    python manage.py validate_statuses --save "${statuses_dir}/analysis_statuses-${label}-old.csv"
  done

  echo "======================================================"
  echo "Phase 2/2: validation on NEW ref ${new_ref} (${new_short})"
  echo "======================================================"
  git checkout -q "${new_ref}"
  if [[ ! -x validation_scripts/validate_new_version.sh ]]; then
    echo "NEW ref has no validation_scripts/validate_new_version.sh — it must contain the validation tooling." >&2
    exit 2
  fi
  local validation_status="PASSED"
  if ! (cd validation_scripts && BACKUP_DIR="${backup_dir}" ./validate_new_version.sh); then
    validation_status="FAILED"
  fi

  {
    echo "# Release validation: ${old_ref} (${old_short}) -> ${new_ref} (${new_short})"
    echo
    echo "- Ran: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "- Backups: ${backup_dir}"
    echo "- Result: **${validation_status}**"
    echo
    echo "Per-backup reports:"
    for backup_file in "${backup_dir}"/*.backup; do
      label="$(label_for_backup "${backup_file}")"
      echo "- ${label}: [diff](analysis_statuses-${label}-diff.md), [endpoints](analysis_statuses-${label}-endpoints.md)"
    done
  } > "${summary_file}"

  echo "======================================================"
  cat "${summary_file}"
  echo "Summary written to ${summary_file}"

  [[ "${validation_status}" == "PASSED" ]] || exit 1
}

main "$@"
