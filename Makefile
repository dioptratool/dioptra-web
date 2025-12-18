DB_PASSWORD=$(DATABASE_PASSWORD)
LOCAL_DB_BASEURL=postgres://dioptra:$(DB_PASSWORD)@localhost:12432/
DBNAME=dioptra
LOCAL_DB_URL=$(LOCAL_DB_BASEURL)$(DBNAME)
DJ_LOG_LEVEL=$(or $(LOG_LEVEL), INFO)
TEST_LOG_LEVEL=$(or $(LOG_LEVEL), FATAL)
DJ_SETTINGS_MODULE=$(or $(DJANGO_SETTINGS_MODULE), website.settings.local)
ROLL_BACK=2

AWS_ACCESS=$(or $(AWS_ACCESS_KEY_ID), test)
AWS_SECRET=$(or $(AWS_SECRET_ACCESS_KEY), test)
AWS_ENDPT=$(AWS_ENDPOINT)
ifeq ($(AWS_ACCESS),test)
AWS_ENDPT=http://localhost:12533
endif

LOCALVARS=DJANGO_SETTINGS_MODULE=$(DJ_SETTINGS_MODULE) DJANGO_LOG_LEVEL=$(DJ_LOG_LEVEL) AWS_ACCESS_KEY_ID=$(AWS_ACCESS) AWS_SECRET_ACCESS_KEY=$(AWS_SECRET) AWS_ENDPOINT=$(AWS_ENDPT) $(XSTORE_ARGS)
TESTVARS=$(LOCALVARS) LOG_LEVEL=$(TEST_LOG_LEVEL) DJANGO_SETTINGS_MODULE=website.settings.test

# A list of tuples: name dockerfile context
# Each line is "NAME DOCKERFILE CONTEXT"
IMAGES = \
	"dioptra-local docker/Dockerfile.web ." \
	"dioptra-remote docker/Dockerfile.web.remote ."

up:
	docker compose -p dioptra-web -f docker/docker-compose-local.yml up -d --build

up-github:
	docker compose -p dioptra-web -f docker/docker-compose-github.yml up -d --build

stop:
	docker compose -p dioptra-web -f docker/docker-compose-local.yml stop

install:
	pip install -r requirements/development.txt

manage: env-CMD ## Set CMD env var to what you want to pass to manage.py
	$(LOCALVARS) ./manage.py $(CMD)

rebuild-db:
	$(LOCALVARS) ./manage.py build -y

psql:
	psql "$(LOCAL_DB_URL)"

psql-transactions:
	@echo "Run 'make psql' from transaction-data-pipeline to connect to the local transaction store."

dbshell:
	$(LOCALVARS) ./manage.py dbshell

shell:
	$(LOCALVARS) ./manage.py shell

notebook:
	$(LOCALVARS) ./manage.py shell_plus --notebook

create-db:
	psql "$(LOCAL_DB_BASEURL)postgres" -c "CREATE DATABASE $(DBNAME);"

bootstrap-db:
	$(LOCALVARS) python ./manage.py build -y

changepass:
	$(LOCALVARS) python ./manage.py changepassword "system@dioptratool.org"

export_help:
	$(LOCALVARS) python ./manage.py export_help

seed_help:
	$(LOCALVARS) python ./manage.py seed_help --json=website/management/commands/seed_data/help_data/exported-help.json

restore-db-pgdump: env-BACKUP
	@# This is for restoring db dump locally in the Postgres binary format
	@# DO NOT USE THIS IN PRODUCTION.  THIS WIPES OWNERS AND ACLS
	@psql --quiet "$(LOCAL_DB_BASEURL)postgres" -c "DROP DATABASE IF EXISTS $(DBNAME)"
	@psql --quiet "$(LOCAL_DB_BASEURL)postgres" -c "CREATE DATABASE $(DBNAME);"
	@PGPASSWORD="$(DB_PASSWORD)" pg_restore --no-owner --no-acl -d dioptra -p 12432  -h 127.0.0.1 -U dioptra "$(BACKUP)" > /dev/null
	@echo "Successfully restored ${BACKUP}\n"


restore-db-pgdump-and-migrate: env-BACKUP
	@# This is for restoring db dump locally in the Postgres binary format
	@# DO NOT USE THIS IN PRODUCTION.  THIS WIPES OWNERS AND ACLS
	@psql --quiet "$(LOCAL_DB_BASEURL)postgres" -c "DROP DATABASE IF EXISTS $(DBNAME)"
	@psql --quiet "$(LOCAL_DB_BASEURL)postgres" -c "CREATE DATABASE $(DBNAME);"
	@PGPASSWORD="$(DB_PASSWORD)" pg_restore --no-owner --no-acl -d dioptra -p 12432  -h 127.0.0.1 -U dioptra "$(BACKUP)" > /dev/null
	$(LOCALVARS) python ./manage.py migrate
	$(LOCALVARS) python ./manage.py backup_analysis_dates
	$(LOCALVARS) python ./manage.py clear_output_costs
	$(LOCALVARS) python ./manage.py backup_analysis_dates --restore
	$(LOCALVARS) python ./manage.py enable_admin_user
	@echo "Successfully restored, migrated and recomputed output costs for ${BACKUP}\n"

## load-sql: env-DUMPFILE Convert a pg_dump file to sql and load database using psql
##   This was created to workaround some issues with the Postgres 17 transition.   If you get an error
##    about "unrecognized configuration parameter "transaction_timeout"" with the `make restore-db-pgdump` command
##    you can try this command with the same dump file to load the file.   Please remove this commmand when
##    the transition to Postgres 17 is complete
load-sql: env-BACKUP
	@pg_restore --no-owner --no-privileges -f $(BACKUP).sql $(BACKUP)
	@PGPASSWORD="$(DB_PASSWORD)" dropdb -h 0.0.0.0 -p 12432 -U dioptra dioptra
	@PGPASSWORD="$(DB_PASSWORD)" createdb -h 0.0.0.0 -p 12432 -U dioptra dioptra
	@PGPASSWORD="$(DB_PASSWORD)" psql -q -h 0.0.0.0 -p 12432 -U dioptra -d dioptra -f $(BACKUP).sql > /dev/null

restore-transactions-db: env-BACKUP
	psql "$(LOCAL_DB_URL)" -f "$(BACKUP)"

test:
	$(TESTVARS) pytest -Wa --reuse-db --random-order

test-rebuild-db:
	$(TESTVARS) pytest -Wa

run:
	$(LOCALVARS) ./manage.py runserver

run-with-sso:
	$(LOCALVARS) $(SSOVARS) ./manage.py runserver

makemigrations:
	$(LOCALVARS) ./manage.py makemigrations

makemigrations-empty:
	$(LOCALVARS) ./manage.py makemigrations website --empty

makemigrations-merge:
	$(LOCALVARS) ./manage.py makemigrations --merge

migrate:
	$(LOCALVARS) ./manage.py migrate

one-time-squash-migrations:
	$(LOCALVARS) ./manage.py cleanup_migrations --yes

showmigrations:
	$(LOCALVARS) ./manage.py showmigrations

migrate-back:
	$(LOCALVARS) ./manage.py migrate website `$(LOCALVARS) ./manage.py showmigrations website | tail -n $(ROLL_BACK) | head -1 | cut -d " " -f 3`

fe-install:
	cd ./website/static/website && npm install && cd ../../..

fe-build:
	cd ./website/static/website && npm run sass && npm run js

fe-watch:
	cd ./website/static/website && npm start

env-%:
	@if [ -z '${${*}}' ]; then echo 'ERROR: variable $* not set' && exit 1; fi

cmd-exists-%:
	@hash $(*) > /dev/null 2>&1 || \
		(echo "ERROR: '$(*)' must be installed and available on your PATH."; exit 1)

## tidy : : Run the following linters:  black, djade, django-upgrade, pyupgrade
.PHONY: tidy
tidy:
	black --line-length 110 .
	git ls-files -z -- '*.html' | xargs -0r djade --target-version 5.2
	git ls-files -z -- '*.py' | xargs -0r django-upgrade --target-version 5.2
	git ls-files -z -- '*.py' | xargs -0r pyupgrade --py313-plus

## audit : : Dry run the following linters:  black, djade, django-upgrade, pyupgrade
.PHONY: audit
audit:
	black --line-length 110 --diff --check .
	git ls-files -z -- '*.html' | xargs -0r djade --check --target-version 5.2
	git ls-files -z -- '*.py' | xargs -0r django-upgrade --target-version 5.2
	git ls-files -z -- '*.py' | xargs -0r pyupgrade --py313-plus

## security/audit : :  Run a full bandit check
.PHONY: security/audit
security/audit:
	bandit -ll -r lib website

## security/bandit-baseline : :  Run bandit against the baseline report
.PHONY: security/bandit-baseline
security/bandit-baseline:
	bandit -ll -b bandit-baseline.json -r lib website

## security/bandit-baseline-make : :  Make the bandit baseline report
.PHONY: security/bandit-baseline-make
security/bandit-baseline-make:
	bandit -ll -f json -o bandit-baseline.json -r lib website

write-vars:
	 echo 'export $(LOCALVARS)' > .local-env

compile-python-requirements:
	 pip-compile --no-strip-extras requirements/base.in
	 pip-compile --no-strip-extras requirements/development.in
	 pip-compile --no-strip-extras requirements/remote.in

upgrade-python-requirements:
	 pip-compile -U --no-strip-extras requirements/base.in
	 pip-compile -U --no-strip-extras requirements/development.in
	 pip-compile -U --no-strip-extras requirements/remote.in

validate-subcomponent-data:
	$(LOCALVARS) ./manage.py fix_types_in_subcomponent_allocations

fix-subcomponent-data:
	$(LOCALVARS) ./manage.py fix_types_in_subcomponent_allocations --write

clear_cached_output_costs:
	$(LOCALVARS) ./manage.py clear_output_costs

backup_analysis_updated_dates:
	$(LOCALVARS) ./manage.py backup_analysis_dates

restore_analysis_updated_dates:
	$(LOCALVARS) ./manage.py backup_analysis_dates --restore

check-deploy-status:
	@# This checks the production config for common configuration issues.
	@# The DJANGO_SECRET_KEY is just a random value here to avoid that check and ISO_CURRENCY_CODE is required so it is included
	$(LOCALVARS) DJANGO_SECRET_KEY=$(shell openssl rand -base64 38 | cut -c1-50) DJANGO_SETTINGS_MODULE=website.settings.remote ISO_CURRENCY_CODE=USD ./manage.py check --deploy --fail-level=ERROR

validate-analysis-endpoints:
	$(LOCALVARS) ./manage.py ensure_all_analysis_endpoints_load --username analytics@dioptratool.org

validate-release-preflight:
	@cd validation_scripts/ && ./preflight.sh

validate-release:
	@cd validation_scripts/ && ./validate_new_version.sh

## fmt-check-hadolint: : Run hadolint on Dockerfiles
# We're ignoring these rules:
# DL3008: Pin versions in apt-get install
# DL3018: Pin versions in apk add
# DL3013: Pin versions in pip
.PHONY: fmt-check-hadolint
fmt-check-hadolint:
	@echo "Linting Dockerfiles..."
	@find . -type f -name '*Dockerfile*' -print0 | \
	xargs -0 -I {} docker run --rm -v .:/app -w /app hadolint/hadolint hadolint --ignore DL3008 --ignore DL3018 --ignore DL3013 {}
	@echo "Done."

## fmt-check-dclint: : Run dclint on docker compose files
.PHONY: fmt-check-dclint
fmt-check-dclint:
	@echo "Linting Docker Compose files..."
	docker run -t --rm -v .:/app zavoloklom/dclint -r .
	@echo "Done."

## security/docker-scout: : Run docker scout
.PHONY: security/docker-scout
security/docker-scout:
	@echo "Starting Docker Scout scans..."
	@for line in $(IMAGES); do \
		name=$$(echo $$line | cut -d' ' -f1); \
		dockerfile=$$(echo $$line | cut -d' ' -f2); \
		context=$$(echo $$line | cut -d' ' -f3); \
		echo "============================================================"; \
		echo "Building image '$$name' from '$$dockerfile' with context '$$context'..."; \
		docker build --no-cache -f $$dockerfile -t $$name:latest $$context || { echo "Build failed for $$name"; exit 1; }; \
		echo "Running Docker Scout scan for '$$name'..."; \
		docker scout cves $$name:latest --only-fixed --only-severity critical,high,medium || { echo "Scan failed for $$name"; exit 1; }; \
	done
	@echo "All images scanned successfully. Review above for vulnerabilities."
	@echo "Removing built images..."
	@for line in $(IMAGES); do \
		name=$$(echo $$line | cut -d' ' -f1); \
		docker rmi $$name:latest &> /dev/null || true; \
	done

## security/nginx: : Run nginx lint
.PHONY: security/nginx
security/nginx:
	docker run --rm -v ./docker/nginx.conf:/etc/nginx/conf/nginx.conf getpagespeed/gixy /etc/nginx/conf/nginx.conf

enable-admin:
	$(LOCALVARS) python ./manage.py enable_admin_user
