from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class AppLogConfig(AppConfig):
    name = "app_log"
    label = "app_log"
    verbose_name = "Application Log"

    DEFAULT_SETTINGS = {
        "notifiers": [
            "app_log.notifiers.SendEmailNotifier",
        ],
    }

    def ready(self):
        """
        Pre-loads the notifiers and stores them in the `notifiers` dict.
        """
        self.load_notifiers()

    def load_notifiers(self):
        app_log_settings = getattr(settings, "APP_LOG", self.DEFAULT_SETTINGS)
        notifier_paths = app_log_settings.get("notifiers")
        self.notifiers = {}
        for notifier_path in notifier_paths:
            self.notifiers[notifier_path] = import_string(notifier_path)()

    def get_notifier(self, notifier_path):
        if not notifier_path in self.notifiers:
            raise ImproperlyConfigured(
                f"{notifier_path} is not a valid notifier. Set it in `settings.APP_LOG['notifiers']`."
            )
        return self.notifiers[notifier_path]

    def get_notifier_choices(self):
        return [(notifier_path, notifier.display_name) for notifier_path, notifier in self.notifiers.items()]
