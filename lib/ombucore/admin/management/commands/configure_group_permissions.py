from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        configure_group_permissions()


def configure_group_permissions(group_permissions=None):
    """
    Configures the Groups and Permissions for the site.

    If `group_permissions` is not passed, the `GROUP_PERMISSIONS` settings is
    looked for and used.'
    """
    if not group_permissions:
        group_permissions = getattr(settings, "GROUP_PERMISSIONS", None)

    if not group_permissions:
        raise ImproperlyConfigured("GROUP_PERMISSIONS not defined in settings.")

    for group_name, perm_strings in list(group_permissions.items()):
        group, created = Group.objects.get_or_create(name=group_name)
        group.permissions.clear()
        permissions = Permission.objects.filter(codename__in=perm_strings)
        group.permissions.add(*permissions)
