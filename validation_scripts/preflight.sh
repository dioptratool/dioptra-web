#!/usr/bin/env bash
#
# preflight-validate.sh
#
# This script loops over all *.backup files in the validation_scripts/backups directory,
# restores each backup to the database, and then runs the "validate_statuses" command
# to generate a file with analysis statuses and the final output metrics (where relevant).
#

set -euo pipefail

# Set Django settings (adjust as needed for your environment)
export DJANGO_SETTINGS_MODULE="website.settings.local"

BACKUP_DIR="backups"
STATUSES_DIR="statuses"

# Create output directory for status files
mkdir -p "${STATUSES_DIR}"

# Loop over each .backup file in BACKUP_DIR
for backup_file in "${BACKUP_DIR}"/*.backup; do
  # If no .backup files exist, skip
  if [ ! -e "${backup_file}" ]; then
    echo "No .backup files found in ${BACKUP_DIR}."
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

  echo "------------------------------------------------------"
  echo "Restoring database for label: ${label}"
  echo "Backup file: ${backup_file}"
  echo "------------------------------------------------------"

  # Export BACKUP file path so make can use it
  export BACKUP="$(realpath "${backup_file}")"

  # Restore the database from this backup
  make -C .. load-sql
  make -C .. migrate

  # Run the validate_statuses management command; store the CSV in "statues"
  # under a file name including the label
  csv_output="${STATUSES_DIR}/analysis_statuses-${label}-old.csv"
  echo "Running validate_statuses to save statuses to -> ${csv_output}"
  python ../manage.py validate_statuses --save "${csv_output}"

  echo "Done processing label: ${label}"
  echo
done

echo "All backups processed."