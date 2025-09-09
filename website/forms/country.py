from django.forms import FileField, Form

from .widgets import TemplateDownloadField


class UploadCountriesForm(Form):
    mapping_file = FileField(
        label="Upload Countries File",
        required=True,
    )
    excel_template = TemplateDownloadField(
        template_path="excel_templates/countries_template.xlsx",
        label="Template",
    )
