import django.db.models.deletion
from django.db import migrations, models

from website import betterdb


class Migration(migrations.Migration):
    dependencies = [("website", "0001_fresh_start")]

    operations = [
        migrations.CreateModel(
            name="ExampleTree",
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
                ("name", models.TextField()),
            ],
            bases=(
                models.Model,
                betterdb.ReprMixin,
            ),
        ),
        migrations.AddField(
            model_name="exampletree",
            name="parent",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="children_set",
                to="betterdb.ExampleTree",
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="ExampleM2M",
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
                ("name", models.TextField()),
                (
                    "others",
                    models.ManyToManyField(related_name="others_reverse", to="betterdb.ExampleM2M"),
                ),
            ],
            bases=(
                betterdb.ReprMixin,
                models.Model,
            ),
        ),
    ]
