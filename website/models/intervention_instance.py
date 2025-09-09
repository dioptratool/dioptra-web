from django.db import models
from django.db.models import Max

from website.models.field_types import InterventionParametersType
from website.models.fields import TypedJsonField


class InterventionInstanceManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().order_by("order")


class InterventionInstance(models.Model):
    """
    This model keeps some info about the instance intervention
     that has been linked to the Analysis model.
    """

    analysis = models.ForeignKey("website.Analysis", on_delete=models.CASCADE, null=True)
    intervention = models.ForeignKey("website.Intervention", on_delete=models.CASCADE)
    label = models.CharField(max_length=100, blank=True, null=True)
    order = models.IntegerField(default=0)

    cloned_from = models.ForeignKey(
        "website.InterventionInstance",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    parameters = TypedJsonField(
        typed_json=InterventionParametersType,
        default=dict,
    )

    objects = InterventionInstanceManager()

    def __repr__(self):
        return f"<InterventionInstance: {self.label} ({self.id})>"

    def display_name(self) -> str:
        return self.label if self.label else self.intervention.name

    def save(self, *args, **kwargs):
        # Ensure that order is incremented
        if self.order is None:  # only when order is not already set
            max_order = InterventionInstance.objects.filter(
                analysis=self.analysis,
            ).aggregate(
                Max("order")
            )["order__max"]

            if max_order is None:
                max_order = -1
            self.order = max_order + 1
        super().save(*args, **kwargs)

    def has_parameters(self):
        """
        Check if all required parameters are set on the first Output Metric.
        """
        if self.intervention.output_metric_objects():
            output_metric = self.intervention.output_metric_objects()[0]
            for param_key, param_field in output_metric.parameters.items():
                if self.parameters.get(param_key) is None:
                    return False
        return True
