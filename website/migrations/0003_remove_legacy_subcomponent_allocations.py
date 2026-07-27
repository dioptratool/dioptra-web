from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0003_finalize_intervention_subcomponents"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="costlineitemconfig",
            name="subcomponent_analysis_allocations",
        ),
        migrations.RemoveField(
            model_name="costlineitemconfig",
            name="subcomponent_analysis_allocations_skipped",
        ),
    ]
