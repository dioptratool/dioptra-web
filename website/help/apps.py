from django.apps import AppConfig


class HelpAppConfig(AppConfig):
    name = "website.help"
    verbose_name = "Help"

    def ready(self):
        try:
            import website.help.signals  # noqa F401
        except ImportError:
            pass
