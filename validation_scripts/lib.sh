# Shared helpers for the release-validation scripts. Sourced by preflight.sh and
# validate_new_version.sh. validate_release_range.sh carries its own copy on purpose:
# it switches git refs while running, so it must not read files from the checkout.
#
# Every backup is restored into its own database, validation_<label>, on the local
# Postgres container, so backups can be processed in parallel (JOBS, default 4). Each
# step reaches the right database through DATABASE_NAME, which website/settings/base.py
# reads. Bash 3.2 (macOS) compatible: no wait -n, no associative arrays.

VALIDATION_DB_HOST="${DATABASE_HOST:-127.0.0.1}"
VALIDATION_DB_PORT="${DATABASE_PORT:-12432}"
VALIDATION_DB_USER="${DATABASE_USER:-dioptra}"
export PGPASSWORD="${PGPASSWORD:-${DATABASE_PASSWORD:-}}"
JOBS="${JOBS:-4}"

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
  # A Postgres identifier: validation_<label>, lowercase, non-alphanumerics as '_', <= 63 chars.
  local slug
  slug="$(echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c '[:alnum:]\n' '_')"
  echo "validation_${slug}" | cut -c1-63
}

_psql_admin() {
  psql -q -X -h "${VALIDATION_DB_HOST}" -p "${VALIDATION_DB_PORT}" -U "${VALIDATION_DB_USER}" -d postgres "$@"
}

restore_backup() {
  # restore_backup BACKUP_FILE DB_NAME: drop, create, pg_restore. Falls back to the
  # dump-to-SQL route (the Postgres 17 workaround behind `make load-sql`) if a direct
  # restore fails.
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
  # run_backups_in_parallel FUNCTION STATUS_DIR BACKUP_FILE...
  # Runs FUNCTION BACKUP_FILE for each backup, at most JOBS at a time. FUNCTION must
  # write "PASSED" or "FAILED" to STATUS_DIR/<label>.status and keep its own output in
  # a log file; this runner only prints start/finish lines. Returns non-zero if any
  # backup did not PASS.
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

drop_validation_databases() {
  # Drops every validation_* database on the local server.
  local db
  for db in $(_psql_admin -At -c "SELECT datname FROM pg_database WHERE datname LIKE 'validation\\_%';"); do
    echo "Dropping ${db}"
    _psql_admin -c "DROP DATABASE IF EXISTS \"${db}\";"
  done
}
