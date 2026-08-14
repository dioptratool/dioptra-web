from django.db import migrations
from django.db.models import Q


def delete_husk_subcomponent_analyses(apps, schema_editor):
    """
    Delete SubcomponentCostAnalysis rows with no labels and no allocation rows.

    The pre-2.2 side flow created a SubcomponentCostAnalysis as soon as a user
    opened it, so production data contains empty husks (labels [], zero
    allocations) on analyses whose sub-component work never started. In 2.2 the
    allocate-subcomponents step gates insights, so these husks would re-open
    long-finished analyses; they also propagate through the duplicator. Rows
    with any allocation data or any labels are real work and are kept.
    """
    SubcomponentCostAnalysis = apps.get_model("website", "SubcomponentCostAnalysis")
    db_alias = schema_editor.connection.alias
    (
        SubcomponentCostAnalysis.objects.using(db_alias)
        .filter(Q(subcomponent_labels=[]) | Q(subcomponent_labels__isnull=True))
        .filter(allocations__isnull=True)
        .delete()
    )


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0006_merge_20260727_0934"),
    ]

    operations = [
        migrations.RunPython(
            delete_husk_subcomponent_analyses,
            migrations.RunPython.noop,
        ),
    ]
