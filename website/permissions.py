from __future__ import annotations

import rules
from django.contrib.auth import get_user_model

from website.models import Analysis

User = get_user_model()


@rules.predicate
def is_analysis_owner(user: User, analysis: Analysis = None) -> bool | None:
    if user.is_anonymous:
        return False
    if analysis:
        return user == analysis.owner
    return None


@rules.predicate
def is_analysis_in_users_primary_countries(user: User, analysis: Analysis = None) -> bool | None:
    if user.is_anonymous:
        return False
    if analysis:
        return analysis.country in user.primary_countries.all()
    return None


@rules.predicate
def is_analysis_in_users_secondary_countries(user: User, analysis: Analysis = None) -> bool | None:
    if user.is_anonymous:
        return False
    if analysis:
        return analysis.country in user.secondary_countries.all()
    return None


@rules.predicate
def is_dioptra_admin(user: User) -> bool:
    if user.is_anonymous:
        return False
    return user.role == User.ADMIN


@rules.predicate
def is_analysis_complete(user: User, analysis: Analysis = None) -> bool:
    if user.is_anonymous:
        return False
    if analysis:
        return analysis.is_complete()
    return False


rules.add_perm(
    "website.change_analysis",
    is_dioptra_admin | is_analysis_owner | is_analysis_in_users_primary_countries,
)
rules.add_perm(
    "website.duplicate_analysis",
    is_dioptra_admin | is_analysis_owner | is_analysis_in_users_primary_countries,
)
rules.add_perm(
    "website.view_analysis",
    (
        is_dioptra_admin
        | is_analysis_owner
        | is_analysis_in_users_primary_countries
        | is_analysis_in_users_secondary_countries
    ),
)
rules.add_perm("website.delete_analysis", is_dioptra_admin | is_analysis_owner)


class SiteRolePermissionBackend:
    """
    Custom back-end to look up site role-based permissions for a user.
    """

    def authenticate(self, username, password):
        return None

    def has_perm(self, user, perm, *args, **kwargs):
        return self._has_site_permission(user, perm)

    def has_module_perms(self, user, app_label):
        return self._has_site_permission(user, app_label)

    def _has_site_permission(self, user, perm):
        return perm in self._user_site_permissions(user)

    def _user_site_permissions(self, user):
        perm_cache_name = "_site_role_perm_cache"
        if not hasattr(user, perm_cache_name):
            permissions = []
            role_permissions = self.ROLE_PERMISSIONS.get(user.role, None) if hasattr(user, "role") else None
            if role_permissions:
                permissions += role_permissions
            setattr(user, perm_cache_name, permissions)
        return getattr(user, perm_cache_name)

    ROLE_PERMISSIONS = {
        "BASIC": [
            "website.add_analysis",
            "users.change_own_user",
            "users.change_user",
        ],
        "ADMIN": [
            "ombucore_admin.access_admin_central",
            "website.add_analysis",
            "website.change_analysis",
            "website.reassign_analysis",
            "website.delete_analysis",
            "website.duplicate_analysis",
            "website.add_costtype",
            "website.change_costtype",
            "website.delete_costtype",
            "website.add_category",
            "website.change_category",
            "website.delete_category",
            "website.add_country",
            "website.change_country",
            "website.delete_country",
            "website.add_region",
            "website.change_region",
            "website.delete_region",
            "website.change_settings",
            "users.add_user",
            "users.change_user",
            "users.change_any_user",
            "users.delete_user",
            "website.add_intervention",
            "website.change_intervention",
            "website.delete_intervention",
            "website.add_interventiongroup",
            "website.change_interventiongroup",
            "website.delete_interventiongroup",
            "website.add_costtypecategorymapping",
            "website.change_costtypecategorymapping",
            "website.delete_costtypecategorymapping",
            "website.add_insightcomparisondata",
            "website.change_insightcomparisondata",
            "website.delete_insightcomparisondata",
            "website.add_costefficiencystrategy",
            "website.change_costefficiencystrategy",
            "website.delete_costefficiencystrategy",
            "website.add_accountcodedescription",
            "website.change_accountcodedescription",
            "website.delete_accountcodedescription",
            "website.add_helpitem",
            "website.change_helpitem",
            "website.delete_helpitem",
            "website.add_helppage",
            "website.change_helppage",
            "website.delete_helppage",
            "website.add_helpmenuitem",
            "website.change_helpmenuitem",
            "website.delete_helpmenuitem",
            "assets.add_imageasset",
            "assets.change_imageasset",
            "assets.delete_imageasset",
            "assets.add_documentasset",
            "assets.change_documentasset",
            "assets.delete_documentasset",
            "assets.add_assetfolder",
            "assets.change_assetfolder",
            "assets.delete_assetfolder",
            "help.add_helppage",
            "help.change_helppage",
            "help.delete_helppage",
            "help.add_helpitem",
            "help.change_helpitem",
            "help.delete_helpitem",
            "help.add_topicmenuitem",
            "help.change_topicmenuitem",
            "help.delete_topicmenuitem",
            "help.add_linkmenuitem",
            "help.change_linkmenuitem",
            "help.delete_linkmenuitem",
            "taggit.add_tag",
            "taggit.change_tag",
            "taggit.delete_tag",
            "website.add_fieldlabeloverrides",
            "website.change_fieldlabeloverrides",
            "website.delete_fieldlabeloverrides",
            "app_log.add_subscription",
            "app_log.change_subscription",
            "app_log.delete_subscription",
            "app_log.change_applogentry",
        ],
    }
