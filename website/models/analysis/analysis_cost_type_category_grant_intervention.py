from django.db import models


class AnalysisCostTypeCategoryGrantIntervention(models.Model):
    cost_type_grant = models.ForeignKey(
        "website.AnalysisCostTypeCategoryGrant",
        on_delete=models.CASCADE,
        related_name="contributors",
    )
    intervention_instance = models.ForeignKey(
        "website.InterventionInstance",
        on_delete=models.CASCADE,
    )

    cloned_from = models.ForeignKey(
        "website.AnalysisCostTypeCategoryGrantIntervention",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    def __repr__(self):
        return (
            f"<AnalysisCostTypeCategoryGrantIntervention: "
            f"{self.cost_type_grant.cost_type_category.cost_type} :: "
            f"{self.cost_type_grant.cost_type_category.category} :: "
            f"{self.cost_type_grant.grant} :: "
            f"{self.intervention_instance.display_name()} for: "
            f"{self.analysis.title} >"
        )

    class Meta:
        unique_together = ("cost_type_grant", "intervention_instance")
