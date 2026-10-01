"""Feature 94: object-level analysis permissions by role and lifecycle status."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from website.models import AnalysisStatus
from website.tests.factories import AnalysisFactory, UserFactory

User = get_user_model()

ROLES = ["admin", "owner", "primary_country_editor", "secondary_country_viewer", "stranger", "anonymous"]

# The roles that hold each status-independent permission.
STATUS_INDEPENDENT = {
    "website.view_analysis": {"admin", "owner", "primary_country_editor", "secondary_country_viewer"},
    "website.duplicate_analysis": {"admin", "owner", "primary_country_editor"},
    "website.archive_analysis": {"admin", "owner"},
    "website.unarchive_analysis": {"admin", "owner"},
    "website.delete_analysis": {"admin"},
}

# Editing, and changing status, depend on the lifecycle status as well as the role.
EDIT_PERMISSIONS = ["website.change_analysis", "website.change_analysis_status"]
EDITORS = {"admin", "owner", "primary_country_editor"}


def user_in_role(role, analysis):
    if role == "admin":
        return UserFactory(role=User.ADMIN)
    if role == "owner":
        return analysis.owner
    if role == "anonymous":
        return AnonymousUser()
    user = UserFactory()
    if role == "primary_country_editor":
        user.primary_countries.add(analysis.country)
    elif role == "secondary_country_viewer":
        user.secondary_countries.add(analysis.country)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize("status", list(AnalysisStatus))
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("permission", sorted(STATUS_INDEPENDENT))
def test_status_independent_permissions(permission, role, status):
    analysis = AnalysisFactory(lifecycle__analysis_status=status)
    user = user_in_role(role, analysis)
    assert user.has_perm(permission, analysis) is (role in STATUS_INDEPENDENT[permission])


@pytest.mark.django_db
@pytest.mark.parametrize("status", [AnalysisStatus.IN_PROGRESS, AnalysisStatus.COMPLETE])
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("permission", EDIT_PERMISSIONS)
def test_editors_edit_in_progress_and_complete_analyses(permission, role, status):
    analysis = AnalysisFactory(lifecycle__analysis_status=status)
    user = user_in_role(role, analysis)
    assert user.has_perm(permission, analysis) is (role in EDITORS)


@pytest.mark.django_db
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("permission", EDIT_PERMISSIONS)
def test_only_admins_edit_a_validated_analysis(permission, role):
    analysis = AnalysisFactory(lifecycle__analysis_status=AnalysisStatus.VALIDATED)
    user = user_in_role(role, analysis)
    assert user.has_perm(permission, analysis) is (role == "admin")


@pytest.mark.django_db
def test_archive_and_delete_do_not_follow_from_country_edit_access():
    analysis = AnalysisFactory()
    editor = user_in_role("primary_country_editor", analysis)
    assert editor.has_perm("website.change_analysis", analysis)
    assert not editor.has_perm("website.archive_analysis", analysis)
    assert not editor.has_perm("website.unarchive_analysis", analysis)
    assert not editor.has_perm("website.delete_analysis", analysis)


@pytest.mark.django_db
def test_checks_without_an_object_are_unchanged():
    admin = UserFactory(role=User.ADMIN)
    basic = UserFactory()
    permissions = EDIT_PERMISSIONS + sorted(STATUS_INDEPENDENT)
    for permission in permissions:
        assert admin.has_perm(permission), permission
        assert not basic.has_perm(permission), permission
    assert basic.has_perm("website.add_analysis")
