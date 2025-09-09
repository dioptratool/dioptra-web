from website.models import Analysis
from website.workflows._steps_base import MultiStep, Step, SubStep


class Workflow:
    step_classes: list[type[Step]] = []
    steps: list[Step] = []

    def __init__(self, analysis: Analysis | None):
        self.analysis = analysis
        self.steps = [cls(self) for cls in self.step_classes]

    def get_step(self, step_name: str) -> Step | None:
        for step in self.steps:
            if step.name == step_name:
                return step

    def get_prev(self, step: Step | None) -> Step | None:
        try:
            step_index = self.steps.index(step)
            if step_index - 1 < 0:
                return None
            prev_step = self.steps[step_index - 1]
            if isinstance(prev_step, MultiStep) and len(prev_step.steps):
                prev_sub_step = prev_step.steps[0]
                for sub_step in prev_step.steps:
                    prev_sub_step = sub_step
                    if not sub_step.is_complete:
                        prev_sub_step = sub_step
                        break
                prev_step = prev_sub_step
            return prev_step

        except (IndexError, ValueError):
            return None

    def get_next(self, step: Step) -> Step | None:
        try:
            step_index = self.steps.index(step)
            for step in self.steps[step_index + 1 :]:
                if step.is_enabled:
                    return step
        except (IndexError, ValueError):
            return None

    def get_last_incomplete_or_last(self, skip_final=False) -> Step:
        if not skip_final:
            final_step = self.get_final_step()
            if final_step and final_step.is_complete:
                return final_step
        last_incomplete = self.get_last_incomplete()
        if last_incomplete:
            return last_incomplete
        return self.steps[-1]

    def get_last_incomplete(self) -> Step | None:
        for step in self.steps:
            if step.is_enabled and not step.is_complete:
                if isinstance(step, MultiStep):
                    last = step.get_last_incomplete_or_last()
                    if last:
                        return last
                return step
        return None

    def get_last_complete(self) -> Step | None:
        latest_step = self.get_last_incomplete()
        if isinstance(latest_step, SubStep):
            latest_step = latest_step.parent
        return self.get_prev(latest_step)

    def get_final_step(self) -> Step | None:
        for step in self.steps:
            if step.is_final:
                return step

    def invalidate_step(self, step_name: str) -> None:
        for step in self.steps:
            if step.name == step_name:
                step.invalidate()
