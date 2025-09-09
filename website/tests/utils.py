import os
import subprocess

from django.apps import AppConfig, apps
from django.conf import settings


def setup_test_app(package, label=None):
    """
    Setup a Django test app for the provided package to allow test models
    tables to be created if the containing app has migrations.

    This function should be called from app.tests __init__ module and pass
    along __package__.

    https://code.djangoproject.com/ticket/7835
    """
    app_config = AppConfig.create(package)
    app_config.apps = apps
    if label is None:
        containing_app_config = apps.get_containing_app_config(package)
        label = f"{containing_app_config.label}_tests"
    if label in apps.app_configs:
        raise ValueError(f"There's already an app registered with the '{label}' label.")
    app_config.label = label
    apps.app_configs[app_config.label] = app_config
    app_config.import_models()
    apps.clear_cache()


def import_test_transaction_store(dump):
    db = settings.DATABASES["transaction_store"]
    user = db["USER"]
    name = db["NAME"]
    host = db["HOST"]
    pw = db["PASSWORD"]
    port = str(db["PORT"])

    # build the base psql command
    base_cmd = ["psql", "-q", "-h", host, "-p", port, "-U", user, name]

    # copy the current env and inject PGPASSWORD
    env = os.environ.copy()
    env["PGPASSWORD"] = pw

    subprocess.run(
        base_cmd + ["-c", "DROP TABLE IF EXISTS transactions; DROP TABLE IF EXISTS transactions_meta;"],
        env=env,
        check=True,
    )

    dump_path = os.path.join(settings.PROJECT_DIR, "website/tests/test_data", dump)
    subprocess.run(
        base_cmd + ["-f", dump_path],
        env=env,
        check=True,
    )
