from django.forms import FileField, Form

from .widgets import TemplateDownloadField


class UploadCostTypeMappingForm(Form):
    mapping_file = FileField(
        label="Upload Cost Type Category Mapping File",
        required=True,
    )
    excel_template = TemplateDownloadField(
        template_path="excel_templates/cost_type_category_mapping_template.xlsx",
        label="Template",
    )
