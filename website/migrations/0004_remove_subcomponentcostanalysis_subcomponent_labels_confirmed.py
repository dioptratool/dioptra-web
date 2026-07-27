from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0003_remove_legacy_subcomponent_allocations"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="subcomponentcostanalysis",
            name="subcomponent_labels_confirmed",
        ),
    ]
