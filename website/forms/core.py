from django.utils.html import format_html
from django.utils.translation import gettext as _

from ombucore.admin.forms.base import ModelFormBase
from ombucore.htmloutput_field.fields import HtmlOutputField


class CostTypeCategoryMappingForm(ModelFormBase):
    criteria_text = HtmlOutputField(
        label="",
        render_fn=lambda *ars, **kwargs: format_html("<h2>{}</h2>", _("Criteria")),
        required=False,
    )
    result_text = HtmlOutputField(
        label="",
        render_fn=lambda *ars, **kwargs: format_html("<h2>{}</h2>", _("Result")),
        required=False,
    )

    def clean(self):
        cleaned_data = self.cleaned_data
        if not cleaned_data["cost_type"] and not cleaned_data["category"]:
            self.add_error("category", _("Please select a cost type, category, or both"))
        return cleaned_data

    class Meta:
        fields = [
            "criteria_text",
            "country_code",
            "grant_code",
            "budget_line_code",
            "account_code",
            "site_code",
            "sector_code",
            "budget_line_description",
            "result_text",
            "cost_type",
            "category",
        ]
