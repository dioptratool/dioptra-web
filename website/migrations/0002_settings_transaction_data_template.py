from django.db import migrations, models
from django.utils.translation import gettext_lazy as _
import website.data_loading.transaction_templates.registry


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0001_fresh_start"),
    ]

    operations = [
        migrations.AddField(
            model_name="settings",
            name="transaction_data_template",
            field=models.CharField(
                choices=website.data_loading.transaction_templates.registry.get_transaction_template_choices,
                default="dioptra_default",
                help_text=_("The transaction upload template available on the Load Data step."),
                max_length=100,
                verbose_name=_("Transaction Import Template"),
            ),
        ),
    ]
