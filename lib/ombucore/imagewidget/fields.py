from django.forms import CheckboxInput, ClearableFileInput
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _
from imagekit.cachefiles import ImageCacheFile
from imagekit.registry import generator_registry


class PreviewableImageInput(ClearableFileInput):
    template_name = "django/forms/widgets/file.html"
    template_with_initial = """
    <span class="previewable-file-widget" data-mode="{mode}">
        <span class="mode-empty">
            <span class="drag-text">{drag_text}, {or_text}</span>
            <label for="id_{name}" class="change">{upload_text}</label>
        </span>
        <span class="mode-value">
            <span class="preview">{preview}</span>
            <label for="id_{name}" class="change">{change_text}</label>
            {clear_template}
        </span>
        {input}
        {clear}
    </span>
    """

    template_with_clear = '<a href="#" class="remove" for="{clear_checkbox_id}">{clear_checkbox_label}</a>"'

    clear_checkbox_label = "Remove"
    preview_generator = "imagewidget:preview"

    def __init__(self, **kwargs):
        self.preview_generator = kwargs.pop("preview_generator", self.preview_generator)
        super().__init__(**kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs.update(
            {
                "data-ajax-file-preview-url": reverse("ajax-file-preview"),
                "data-preview-generator": self.preview_generator,
                "class": "notrackchange",
            }
        )
        substitutions = {
            "name": name,
            "clear": "",
            "clear_template": "",
            "clear_checkbox_label": _(self.clear_checkbox_label),
            "preview": "",
            "value": value,
            "mode": "value" if value else "empty",
            "input": super().render(name, value, attrs, renderer=renderer),
            "drag_text": _("Drag an image here"),
            "or_text": _("or"),
            "upload_text": _("Upload from computer"),
            "change_text": _("Change"),
        }

        if self.is_initial(value):
            substitutions.update(self.get_template_substitution_values(value))
            if not self.is_required:
                checkbox_name = self.clear_checkbox_name(name)
                checkbox_id = self.clear_checkbox_id(checkbox_name)
                substitutions["clear"] = CheckboxInput().render(
                    checkbox_name,
                    False,
                    attrs={"id": checkbox_id, "class": "clear-checkbox notrackchange"},
                )
                substitutions["clear_template"] = format_html(
                    self.template_with_clear,
                    clear_checkbox_id=checkbox_id,
                    clear_checkbox_label=substitutions["clear_checkbox_label"],
                )

        return format_html(self.template_with_initial, **substitutions)

    def get_template_substitution_values(self, value):
        generator = generator_registry.get(self.preview_generator, source=value)
        f = ImageCacheFile(generator)
        return {
            "preview": format_html('<img src="{}"/>', f.url),
        }

    class Media:
        js = ("js/ajax-file-preview.js",)
        css = {"all": ("css/ajax-file-preview.css",)}
