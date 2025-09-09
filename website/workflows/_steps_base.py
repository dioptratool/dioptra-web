from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.functional import cached_property

if TYPE_CHECKING:
    from website.workflows._workflow_base import Workflow


class Step:
    name: str | None = None
    nav_title: str | None = None
    is_enabled: bool = True

    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.analysis = workflow.analysis

    def clear_cached(self, property_name: str) -> None:
        if property_name in self.__dict__:
            del self.__dict__[property_name]

    @cached_property
    def is_complete(self) -> bool:
        return False

    @cached_property
    def is_final(self) -> bool:
        return False

    @cached_property
    def dependencies_met(self) -> bool:
        return False

    def get_nav_title(self) -> str | None:
        return self.nav_title

    def get_href(self) -> str | None:
        return None

    def get_prev(self) -> Step | None:
        return self.workflow.get_prev(self)

    def get_next(self) -> Step | None:
        return self.workflow.get_next(self)

    def invalidate(self) -> None:
        pass


class MultiStep(Step):
    def __init__(self, workflow: Workflow):
        super().__init__(workflow)
        self.steps: list[Step] = []

    def get_last_incomplete_or_last(self) -> Step | None:
        last_incomplete = self.get_last_incomplete()
        if last_incomplete:
            return last_incomplete
        try:
            return self.steps[-1]
        except IndexError:
            return None

    def get_last_incomplete(self) -> Step | None:
        for step in self.steps:
            if not step.is_complete:
                return step
        return None

    @property
    def is_complete(self) -> bool:
        if not self.dependencies_met:
            return False
        if self.analysis and getattr(self.analysis, "pk", None):
            return all([substep.is_complete for substep in self.steps])
        return False


class SubStep(Step):
    parent: MultiStep

    def get_prev(self) -> Step:
        try:
            # Get prev sub-step.
            step_index = self.parent.steps.index(self)
            if step_index - 1 < 0:
                return self.parent.get_prev()
            return self.parent.steps[step_index - 1]
        except (IndexError, ValueError):
            return self.parent.get_prev()

    def get_next(self) -> Step:
        try:
            # Get prev sub-step.
            step_index = self.parent.steps.index(self)
            return self.parent.steps[step_index + 1]
        except (IndexError, ValueError):
            return self.parent.get_next()
