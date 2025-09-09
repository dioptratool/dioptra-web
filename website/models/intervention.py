from collections.abc import Iterable

from django.db import models
from django.forms import Field
from django.utils.translation import gettext_lazy as _

from ombucore.admin.fields import ForeignKey
from .field_types import SubcomponentLabelsType
from .fields import ChoiceArrayField, TypedJsonField
from .output_metric import OUTPUT_METRICS_BY_ID, OUTPUT_METRIC_CHOICES
from .query_utils import require_prefetch


class InterventionGroup(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_interventiongroup_change"

    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
    )

    class Meta:
        verbose_name = _("Intervention Group")
        verbose_name_plural = _("Intervention Groups")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def interventions_for_menu(self):
        interventions = require_prefetch(self, "interventions")
        return [i for i in interventions if i.show_in_menu]


class Intervention(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_intervention_change"
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
    )
    description = models.TextField(
        verbose_name=_("Description"),
        blank=True,
        null=True,
    )
    icon = models.CharField(
        choices=(
            ("water", _("Access to Clean Water")),
            ("agriculture", _("Agricultural Extension Support")),
            ("business_training", _("Business Skills Training")),
            ("at_risk_children", _("Case Mangement for At-Risk Children")),
            ("child_friendly_spaces", _("Child Friendly Spaces")),
            ("family_planning", _("Distribution of Family Planning Supplies")),
            ("delivery", _("Encouraging Women to Deliver at Health Institutions")),
            ("food_assistance", _("Food Assistance")),
            ("latrine", _("Latrine-building Program")),
            ("legal_aid", _("Legal Aid")),
            ("nonfood_distribution", _("Non-food-item Distribution")),
            ("business_grants", _("Providing Business Grants")),
            (
                "primary_healthcare_services",
                _("Provision of Primary Healthcare Services"),
            ),
            ("vaccines", _("Provision of Vaccines")),
            (
                "gbv_survivors",
                _("Supporting Gender-based Violence Survivors at Women's Centers"),
            ),
            ("teacher_development", _("Teacher Development: Face-to-face Training")),
            (
                "teacher_development_ongoing",
                _("Teacher Development: Ongoing Professional Support"),
            ),
            ("malnutrition", _("Treatment for Severe Acute Malnutrition")),
            ("cash", _("Unconditional Cash Distribution")),
            ("villages", _("Villages")),
        ),
        default="cash",
        max_length=255,
    )
    group = ForeignKey(
        InterventionGroup,
        on_delete=models.PROTECT,
        related_name="interventions",
        null=True,
        blank=True,
    )
    output_metrics = ChoiceArrayField(
        models.CharField(
            max_length=255,
            blank=True,
            choices=OUTPUT_METRIC_CHOICES,
        ),
        verbose_name=_("Output Metrics"),
        default=list,
    )
    show_in_menu = models.BooleanField(
        verbose_name=_("Show this intervention in the Program Design Lessons menu"),
        help_text=_(
            "When checked, this intervention insights page will be accessible from the Program Design Lessons menu."
        ),
        default=True,
    )

    subcomponent_labels = TypedJsonField(
        typed_json=SubcomponentLabelsType,
        default=list,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("Intervention")
        verbose_name_plural = _("Interventions")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def output_metric_objects(self):
        objs = []
        for output_metric_id in self.output_metrics:
            output_metric = OUTPUT_METRICS_BY_ID.get(output_metric_id)
            if output_metric is None:
                raise ValueError(f"Unknown output metric ID: {output_metric_id}")
            objs.append(output_metric)
        return objs

    def _get_all_parameter_names(self) -> list[list[str]]:
        all_names = []
        for output_metric in self.output_metrics:
            all_names.append(list(OUTPUT_METRICS_BY_ID[output_metric].parameters.keys()))
        return all_names

    def get_all_parameter_names_by_label(self) -> dict[str, Field]:
        labels = {}
        for output_metric in self.output_metric_objects():
            for k, v in output_metric.parameters.items():
                labels[v.label] = k
        return labels

    def check_parameter(self, parameter_name: str) -> bool:
        """
        Does this parameter exist for this intervention?
        """
        for output_metric in self.output_metrics:
            if parameter_name in OUTPUT_METRICS_BY_ID[output_metric].parameters.keys():
                return True
        raise ValueError(f"Unknown parameter provided for {self.name}: {parameter_name} not found")

    def check_parameters(self, parameter_names: Iterable[str]) -> bool:
        """
        Do all the parameters provided exist for this intervention?
        """

        # Only the first Output Metric has required parameters
        if self._get_all_parameter_names():
            for each_parameter_name in self._get_all_parameter_names()[0]:
                if each_parameter_name not in parameter_names:
                    raise ValueError(
                        f"Missing parameter for {self.name}: {each_parameter_name} was not provided"
                    )

        return all(self.check_parameter(p) for p in parameter_names)
