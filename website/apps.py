from django.apps import AppConfig


class WebsiteConfig(AppConfig):
    name = "website"
    label = "website"
    verbose_name = "Website"

    def ready(self):
        try:
            import website.signals  # noqa F401
        except ImportError:
            pass
