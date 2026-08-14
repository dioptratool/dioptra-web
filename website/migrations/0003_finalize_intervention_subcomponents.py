import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0002_intervention_subcomponents"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="subcomponentcostanalysis",
            name="analysis",
        ),
        migrations.AlterField(
            model_name="subcomponentcostanalysis",
            name="intervention_instance",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subcomponent_cost_analysis",
                to="website.interventioninstance",
                verbose_name="Intervention",
            ),
        ),
    ]
