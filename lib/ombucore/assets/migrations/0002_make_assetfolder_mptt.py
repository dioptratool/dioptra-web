import django.db.models.deletion
import mptt.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="assetfolder",
            options={"verbose_name": "Folder"},
        ),
        migrations.AddField(
            model_name="assetfolder",
            name="level",
            field=models.PositiveIntegerField(db_index=True, default=None, editable=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="assetfolder",
            name="lft",
            field=models.PositiveIntegerField(db_index=True, default=None, editable=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="assetfolder",
            name="parent",
            field=mptt.fields.TreeForeignKey(
                blank=True,
                help_text="The parent folder to put this folder under.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="children",
                to="assets.AssetFolder",
                verbose_name="Parent Folder",
            ),
        ),
        migrations.AddField(
            model_name="assetfolder",
            name="rght",
            field=models.PositiveIntegerField(db_index=True, default=None, editable=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="assetfolder",
            name="tree_id",
            field=models.PositiveIntegerField(db_index=True, default=None, editable=False),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="asset",
            name="folder",
            field=mptt.fields.TreeForeignKey(
                blank=True,
                help_text="The folder to put this asset into.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="folder",
                to="assets.AssetFolder",
                verbose_name="Asset Folder",
            ),
        ),
    ]
