import django.db.models.deletion
from django.db import migrations, models

import website.models.fields


def migrate_subcomponents_to_interventions(apps, schema_editor):
    SubcomponentCostAnalysis = apps.get_model("website", "SubcomponentCostAnalysis")
    SubcomponentCostAllocation = apps.get_model("website", "SubcomponentCostAllocation")
    InterventionInstance = apps.get_model("website", "InterventionInstance")
    CostLineItemConfig = apps.get_model("website", "CostLineItemConfig")
    db_alias = schema_editor.connection.alias

    for subcomponent_analysis in SubcomponentCostAnalysis.objects.using(db_alias).all().order_by("id"):
        intervention_instance = (
            InterventionInstance.objects.using(db_alias)
            .filter(analysis_id=subcomponent_analysis.analysis_id)
            .order_by("order", "id")
            .first()
        )
        if intervention_instance is None:
            subcomponent_analysis.delete(using=db_alias)
            continue

        subcomponent_analysis.intervention_instance_id = intervention_instance.id
        subcomponent_analysis.save(using=db_alias, update_fields=["intervention_instance"])

        allocation_rows = []
        cost_line_configs = CostLineItemConfig.objects.using(db_alias).filter(
            cost_line_item__analysis_id=intervention_instance.analysis_id
        )
        for config in cost_line_configs:
            if config.subcomponent_analysis_allocations or config.subcomponent_analysis_allocations_skipped:
                allocation_rows.append(
                    SubcomponentCostAllocation(
                        subcomponent_analysis_id=subcomponent_analysis.id,
                        cli_config_id=config.id,
                        allocations=config.subcomponent_analysis_allocations or {},
                        skipped=config.subcomponent_analysis_allocations_skipped,
                    )
                )

        if allocation_rows:
            SubcomponentCostAllocation.objects.using(db_alias).bulk_create(
                allocation_rows, ignore_conflicts=True
            )


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0001_fresh_start"),
    ]

    operations = [
        migrations.AddField(
            model_name="subcomponentcostanalysis",
            name="intervention_instance",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subcomponent_cost_analysis",
                to="website.interventioninstance",
                verbose_name="Intervention",
            ),
        ),
        migrations.CreateModel(
            name="SubcomponentCostAllocation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "allocations",
                    website.models.fields.TypedJsonField(default=dict, null=True),
                ),
                ("skipped", models.BooleanField(default=False)),
                (
                    "cli_config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subcomponent_cost_allocations",
                        to="website.costlineitemconfig",
                        verbose_name="Cost Line Item Config",
                    ),
                ),
                (
                    "cloned_from",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="website.subcomponentcostallocation",
                    ),
                ),
                (
                    "subcomponent_analysis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="allocations",
                        to="website.subcomponentcostanalysis",
                        verbose_name="Subcomponent Cost Analysis",
                    ),
                ),
            ],
            options={
                "verbose_name": "Subcomponent Cost Allocation",
                "verbose_name_plural": "Subcomponent Cost Allocations",
            },
        ),
        migrations.AddConstraint(
            model_name="subcomponentcostallocation",
            constraint=models.UniqueConstraint(
                fields=("subcomponent_analysis", "cli_config"),
                name="unique_subcomponent_allocation_per_config",
            ),
        ),
        migrations.RunPython(
            migrate_subcomponents_to_interventions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
