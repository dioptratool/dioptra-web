from django.apps import AppConfig


class UsersAppConfig(AppConfig):
    name = "website.users"
    verbose_name = "Users"

    def ready(self):
        try:
            import website.users.signals  # noqa F401
        except ImportError:
            pass
