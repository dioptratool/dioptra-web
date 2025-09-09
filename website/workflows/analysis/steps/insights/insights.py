from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _l

from website.models.query_utils import require_prefetch
from website.workflows._steps_base import Step


class Insights(Step):
    name: str = "insights"
    nav_title: str = _l("View Insights")

    @cached_property
    def dependencies_met(self) -> bool:
        if self.workflow.get_step("add-other-costs").is_enabled:
            return self.workflow.get_step("add-other-costs").is_complete
        else:
            return self.workflow.get_step("allocate").is_complete

    @cached_property
    def is_complete(self) -> bool:
        return self.dependencies_met

    @cached_property
    def is_final(self) -> bool:
        return True

    def get_href(self) -> str:
        return reverse("analysis-insights", kwargs={"pk": self.analysis.pk})

    def invalidate(self) -> None:
        self.clear_cached("dependencies_met")
        self.clear_cached("is_complete")
        self.analysis.output_costs = {}

        self.analysis.save()

    def calculate_if_possible(self) -> None:
        if self.dependencies_met:
            self.analysis.calculate_output_costs()

    def calculations_done(self) -> bool:
        if not self.analysis.output_costs:
            return False

        inst_lookup = {ii.id: ii for ii in require_prefetch(self.analysis, "interventioninstance_set")}

        for each_intervention_instance_key, output_cost_metrics in self.analysis.output_costs.items():
            intervention_instance = inst_lookup.get(int(each_intervention_instance_key))
            if intervention_instance is None:  # no such instance ⇒ incomplete
                return False
            output_costs_keys = output_cost_metrics.keys()
            first_output_metric = intervention_instance.intervention.output_metric_objects()[0]
            if first_output_metric.id not in output_costs_keys:
                return False
        return True
