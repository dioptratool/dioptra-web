#!/usr/bin/env bash
set -euo pipefail

# Set Django settings (adjust if needed)
export DJANGO_SETTINGS_MODULE="website.settings.local"

# User the endpoint checks authenticate as (override with VALIDATION_USER=...)
VALIDATION_USER="${VALIDATION_USER:-analytics@dioptratool.org}"

# Directory containing your .backup files (override with BACKUP_DIR=/path)
BACKUP_DIR="${BACKUP_DIR:-backups}"
STATUSES_DIR="statuses"
RESULT_DIR="results"

# Set to 1 whenever any backup shows endpoint failures or diffs; the loop keeps
# going so one bad backup doesn't hide results for the rest.
overall_failure=0

mkdir -p ${RESULT_DIR}
# Ensure the directory exists
if [ ! -d "$BACKUP_DIR" ]; then
  echo "Error: Backup directory '$BACKUP_DIR' does not exist."
  exit 1
fi

# Loop over each .backup file in the directory
for backup_file in "$BACKUP_DIR"/*.backup; do
  # If there are no matching files, we skip
  if [ ! -e "$backup_file" ]; then
    echo "No .backup files found in '$BACKUP_DIR'."
    break
  fi

  filename="$(basename "${backup_file}")"
  # Remove the trailing ".backup" (7 chars) to make substring logic easier
  filename_noext="${filename%.backup}"

  # If the file name (minus .backup) is at least 24 chars longer than the minimal name,
  # we assume it includes the date/time zone suffix:
  # e.g. '-2025-01-29_15-23-42-PST' = 24 characters
  if [[ ${#filename_noext} -ge 24 ]]; then
    # Strip the last 24 characters (the '-YYYY-MM-DD_hh-mm-ss-TZ' portion)
    label="${filename_noext:0:$((${#filename_noext}-24))}"
  else
    # If it's too short to contain that date/time suffix, keep the entire name
    label="${filename_noext}"
  fi

  old_statuses="${STATUSES_DIR}/analysis_statuses-${label}-old.csv"
  new_statuses="${STATUSES_DIR}/analysis_statuses-${label}-new.csv"
  diff_statuses="${RESULT_DIR}/analysis_statuses-${label}-diff.md"
  endpoint_check="${RESULT_DIR}/analysis_statuses-${label}-endpoints.md"


  # Export BACKUP so the Makefile picks it up
  export BACKUP="$(realpath "$backup_file")"

  echo "------------------------------------------------------"
  echo "Restoring database for label: ${label}"
  echo "Backup file: ${backup_file}"
  echo "------------------------------------------------------"

  echo "Loading sql..."
  make -C .. load-sql

  echo "Migrating the database..."
  make -C .. migrate

  # Perform your extra steps
  echo "Backing up analysis dates..."
  python ../manage.py backup_analysis_dates
  echo "Recomputing Output Costs..."
  python ../manage.py clear_output_costs
  echo "Restoring analysis dates..."
  python ../manage.py backup_analysis_dates --restore
  echo "Enabling the Admin User..."
  python ../manage.py enable_admin_user
  printf "\033[32mValidating all endpoints load for %s... (this can take a long time)\033[0m\n" "${label}"
  if ! python ../manage.py ensure_all_analysis_endpoints_load --all-step-urls --username "${VALIDATION_USER}" > "${endpoint_check}"; then
    overall_failure=1
    printf "\033[31mEndpoint failures for %s — see %s\033[0m\n" "${label}" "${endpoint_check}"
  fi
  printf "\033[32mFinished validating all endpoints load.\033[0m\n"

  python ../manage.py validate_statuses --save "${new_statuses}"

  # Compare the two CSVs
  printf "\033[32mComparing the old and new statuses....\033[0m\n"
  if ! python find_diffs.py "$old_statuses" "$new_statuses" > "${diff_statuses}"; then
    overall_failure=1
    printf "\033[31mStatus/output differences for %s — see %s\033[0m\n" "${label}" "${diff_statuses}"
  fi
  printf "\033[32mDone processing backup: $backup_file\033[0m\n"
  echo
done

echo "All .backup files processed."
if [ "${overall_failure}" -ne 0 ]; then
  printf "\033[31mValidation FAILED — see the files noted above in %s/.\033[0m\n" "${RESULT_DIR}"
  exit 1
fi
