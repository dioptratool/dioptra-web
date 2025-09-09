# Dioptra / Web application service

Quickstart:

```console
export DJANGO_SECRET_KEY=a_secret_key
export DATABASE_PASSWORD=a_password
docker compose build
docker compose run web python manage.py build -y
docker compose up -d
# go to http://localhost:8000
# Login as dioptra_default+administrator@dioptratool.org, password 'password'
```

## Running using Docker

Define environment variables with the secrets required to run the application locally:

```console
export django_secret_key=a_secret_key
export DATABASE_PASSWORD=a_password
```

Start all services:

```console
docker compose up
```

If necessary, build the site content:

```console
docker compose up
docker compose run web python manage.py build -y
```

Visit `http://localhost:8000`

Or, start each service individually:

```console
docker compose up
docker compose up db
docker compose up web
```

The users created by the build command are defined in
 `website/management/commands/build.py`.

To run Django `manage.py` commands in the docker containers, use:

```console
docker compose up
docker compose run web python manage.py ...
```

Rebuild the Docker images:

```console
docker compose up
docker compose build
```

## Running with a local Python interpreter

The app runs in Docker containers, so a local Python environment is not
strictly required to run it, but it's need it by the development tools. The
target Python version of the app documented in `.tool-versions`.

1. Install the application dependencies

    ```console
    make install
    ```

2. Bring up the supporting services for the application

    ```console
    make up
    ```

    By default, we'll use the settings file `website/settings/local.py`,
    which will run against Docker containers with external services,
    as configured in `docker/docker compose-local.yml`.

    You can use a different file if you have different settings.
    Use `export DJANGO_SETTINGS_MODULE=website.settings.whatever` if that's the case.
    Or try out some of the other settings files.

    Note that some things outside the application (like `make psql`)
    assume the values configured in `local.py`, so you may need to change some things.

3. Initialize the database

    If you have an existing DB, you can import it:

    ```console
    BACKUP=/path/to/backup.sql.gz make restore-db
    BACKUP=/path/to/transactions.sql make restore-transactions-db
    ```

    After running `make up`, there will be a PostgreSQL database named `dioptra` running in a Docker container. We can initialize it with a `system` superuser and imported sample data.

    ```console
    make bootstrap-db
    ```

    You can connect to the DB in either of these ways:

    ```console
    make dbshell # Uses manage.py dbshell
    make psql # Opens directly
    ```

4. Run the site

    ```console
    make run
    ```

    Visit http://localhost:8000.  Log in with
    `dioptra_default+administrator@dioptratool.org` and `password`.

### Validation

You can try connecting to the app ore running a test:

```console
$ make shell

```

```console
$ make test
...
Ran 13 tests in 0.868s
OK
```

## Running the transaction pipeline and datastore

Go that service directory: `../../transaction-data-pipeline/` and follow the
steps in the README.

## OAuth Support

By default, Dioptra runs with regular Django authentication.
We have configurable OAuth providers through django-allauth.

For each integration we want to support,
we need to create an `allauth` social app
that contains the OAuth client and secret.

First, create a new OAuth app in your provider service (Okta, OneLogin, etc).
Record your client ID and secret.
Then run:

    python ./manage.py initialize_auth --provider=## --client-id=## --secret=##

You can also use the `--reset` flag to delete all existing `allauth` apps.

Then, when you run the app, you need to set the `AUTH_PROVIDERS` **environment
variable** to a comma-separated list of enabled auth providers. See `manage.py
initialize_auth -h` for the list of supported providers. Some providers require
additional configuration. These are the current known provider configurations:

`okta`:

- `OKTA_URL` (i.e. dev-123.okta.com)
- `OKTA_OAUTH2_PATH` (i.e. /oauth2/v1)

The Okta API Key is issued at `https://...admin.okta.com/admin/access/api/tokens`.

`onelogin`:

- `ONELOGIN_APP` (i.e. dioptra)

The OneLogin API secrets are issued at
`https://....onelogin.com/api_credentials`. The app API calls require the
*Manage Users* scope.


`microsoft`:

- `MICROSOFT_TENANT_ID` (Tenant ID displayed within your registered application in Microsoft AD)

When running the `initialize_auth` command:  
`--client-id` corresponds to the Client ID within your registered application in Microsoft AD  
`--secret` corresponds to a "client secret value" (NOT "client secret ID") added to that application in Microsoft AD

If an `AUTH_PROVIDERS` is set and requires additional config that is missing,
an error indicating the missing config is raised at load time.

## Running tests

Some initial pytest style tests have been added. They require two databases, the normal Django database and an external transaction_store. There are `make` targets to run tests.

By default, the test database is preserved between runs.

```
make test
```

It is also possible to force the test database to be rebuilt.

```
make test-rebuild-db
```

## Helpful commands

Connect to psql:

    psql postgres://dioptra:$DATABASE_PASSWORD@127.0.0.1:5432/dioptra

Restore a transactions database dump:

    psql postgres://dioptra:$DATABASE_PASSWORD@127.0.0.1:5433/dioptra_transactions -f <filename>

## Benchmarks

There's a benchmarking script for running some routines that have traditionally been slow.
There are some options for running from fixtures, or you can run from live data.

```
$ docker compose run web python manage.py benchmark import
$ docker compose run web python manage.py benchmark import --debug-sql --analysis=6
```
