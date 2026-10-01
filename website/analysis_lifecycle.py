"""Lifecycle operations on an analysis: status transitions and archiving.

After creation these two services are the only writers of ``Analysis.LIFECYCLE_FIELDS`` and the
only code that locks an analysis row. Each operation runs in one transaction: lock the row, check
permission and readiness against the record as stored, write only its own fields, and create the
application-log entry alongside them. Subscribers are notified after the transaction commits, so a
notification problem can neither hold the lock nor undo a committed operation.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from app_log.logger import notify_of_log_entry
from website.app_log.loggers import (
    log_analysis_archived,
    log_analysis_status_changed,
    log_analysis_unarchived,
)
from website.models import Analysis, AnalysisStatus
from website.permissions import is_dioptra_admin
from website.workflows import AnalysisWorkflow
from website.workflows.utils import WORKFLOW_PREFETCHES

User = get_user_model()


class AnalysisLifecycleError(Exception):
    """The operation was rejected and nothing was written. The message is meant for the user."""


class AnalysisLifecyclePermissionDenied(AnalysisLifecycleError, PermissionDenied):
    pass


class AnalysisNotReady(AnalysisLifecycleError):
    """Entering Complete or Validated needs every required workflow step, Insights included."""


def permitted_status_targets(user, analysis: Analysis) -> list[AnalysisStatus]:
    """
    The statuses ``user`` may move ``analysis`` to from the status control, the current one
    included. Empty when the user may not change the status at all, so the UI shows a plain badge.
    """
    if user is None or not user.has_perm("website.change_analysis_status", analysis):
        return []
    if is_dioptra_admin(user):
        return list(AnalysisStatus)
    return [AnalysisStatus.IN_PROGRESS, AnalysisStatus.COMPLETE]


def analysis_is_ready(analysis: Analysis) -> bool:
    """
    Whether every enabled workflow step, including Insights, is complete right now.

    Builds a new workflow around the analysis it is given, so no step state cached by a request
    is reused; pass an analysis loaded with WORKFLOW_PREFETCHES after the edit in question.
    """
    return AnalysisWorkflow(analysis).all_steps_complete


def change_analysis_status(
    analysis_id: int, actor, target_status: str, *, automatic: bool = False
) -> Analysis:
    """
    Move an analysis to ``target_status`` on behalf of ``actor``, and return it as stored.

    A manual transition checks the actor's permission for this particular transition and, when
    entering Complete or Validated, that the workflow is complete. Asking for the current status
    is a no-op: nothing is written and no event is logged.

    ``automatic=True`` is the internal reconciliation path and is never bound from a request. It
    may only reset Complete or Validated to In Progress, does so only when a fresh readiness check
    under the row lock fails, and records ``actor`` as the editing user (None for system work).
    It is a system rule, so it does not consult the actor's status permission.
    """
    try:
        target = AnalysisStatus(target_status)
    except ValueError:
        raise AnalysisLifecycleError(_("Unknown analysis status."))
    if automatic and target != AnalysisStatus.IN_PROGRESS:
        raise ValueError("Automatic status changes can only reset an analysis to In Progress.")

    with transaction.atomic():
        analysis = _lock_analysis(analysis_id)
        current = AnalysisStatus(analysis.analysis_status)

        if automatic:
            if current == target or analysis_is_ready(analysis):
                return analysis
        else:
            _check_transition_permission(actor, analysis, current, target)
            if current == target:
                return analysis
            if target != AnalysisStatus.IN_PROGRESS and not analysis_is_ready(analysis):
                raise AnalysisNotReady(
                    _(
                        "Every analysis step, including Insights, must be complete before the "
                        "analysis can be marked %(status)s."
                    )
                    % {"status": str(target.label)}
                )

        user = actor if isinstance(actor, User) else None
        analysis.analysis_status = target
        analysis.status_changed_by = user
        analysis.status_changed_at = timezone.now()
        analysis.save(update_fields=["analysis_status", "status_changed_by", "status_changed_at"])
        entry = log_analysis_status_changed(
            analysis, str(current.label), str(target.label), user=user, automatic=automatic
        )
        _notify_after_commit(entry)
    return analysis


def set_analysis_archived(analysis_id: int, actor, archived: bool) -> Analysis:
    """
    Archive (``archived=True``) or unarchive an analysis on behalf of ``actor``, returning it as
    stored. Only the archive flag and its audit fields change; status, data and permissions do
    not. Repeating the current state is a no-op with no event.
    """
    with transaction.atomic():
        analysis = Analysis.objects.select_for_update().get(pk=analysis_id)
        if archived:
            permission, denied = "website.archive_analysis", _("You cannot archive this analysis.")
        else:
            permission, denied = "website.unarchive_analysis", _("You cannot unarchive this analysis.")
        if actor is None or not actor.has_perm(permission, analysis):
            raise AnalysisLifecyclePermissionDenied(denied)
        if analysis.is_archived == archived:
            return analysis

        analysis.is_archived = archived
        analysis.archived_by = actor if archived else None
        analysis.archived_at = timezone.now() if archived else None
        analysis.save(update_fields=["is_archived", "archived_by", "archived_at"])
        if archived:
            entry = log_analysis_archived(analysis, user=actor)
        else:
            entry = log_analysis_unarchived(analysis, user=actor)
        _notify_after_commit(entry)
    return analysis


def _lock_analysis(analysis_id: int) -> Analysis:
    # The lock covers the analysis row only; the prefetches are what the readiness check reads.
    return Analysis.objects.select_for_update().prefetch_related(*WORKFLOW_PREFETCHES).get(pk=analysis_id)


def _check_transition_permission(actor, analysis: Analysis, current: AnalysisStatus, target: AnalysisStatus):
    if actor is None or not actor.has_perm("website.change_analysis_status", analysis):
        raise AnalysisLifecyclePermissionDenied(
            _("You do not have permission to change the status of this analysis.")
        )
    if AnalysisStatus.VALIDATED in (current, target) and not is_dioptra_admin(actor):
        raise AnalysisLifecyclePermissionDenied(
            _("Only an administrator can mark an analysis as Validated or change a Validated analysis.")
        )


def _notify_after_commit(entry):
    # A named function rather than functools.partial: Django reports a failing robust callback
    # by its __qualname__, which a partial does not have.
    def notify_subscribers():
        notify_of_log_entry(entry)

    transaction.on_commit(notify_subscribers, robust=True)
