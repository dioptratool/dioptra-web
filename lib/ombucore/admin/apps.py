from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class AdminConfig(AppConfig):
    name = "ombucore.admin"
    label = "ombucore_admin"
    verbose_name = "Administration"

    def ready(self):
        autodiscover_modules("admin")
