from django.conf import settings
from django.template.loader import get_template
from django.utils.html import format_html

DOCUMENT_TYPE_NAME_MAP = {
    "ppt": "Microsoft PowerPoint Document",
    "pptx": "Microsoft PowerPoint Document",
    "pdf": "PDF Document",
    "doc": "Microsoft Word Document",
    "docx": "Microsoft Word Document",
    "xls": "Microsoft Excel Document",
    "xlt": "Microsoft Excel Document",
    "txt": "Text Document",
    "zip": "ZIP Archive",
}


def wrap_in_aspect_box(html, nativeWidth, nativeHeight):
    template = "<div class='aspect-ratio-box'><span class='aspect-prop' style='padding-top: {ratioPercentage}%;'></span>{html}</div>"
    ratioPercentage = (float(nativeHeight) / float(nativeWidth)) * 100
    return template.format(ratioPercentage=ratioPercentage, html=html)


def render_label(asset, local_settings=None):
    return format_html("<label>{title}</label>", title=asset.title)


class RendererBase:
    template_name = None

    def __call__(self, asset, local_settings=None):
        context = self.get_context(asset)
        if local_settings is not None:
            context.update(local_settings)
        return self.render(context)

    def get_context(self, asset):
        return {}

    def render(self, context):
        template = get_template(self.template_name)
        return template.render(context)


class ImageRenderer(RendererBase):
    template_name = "assets/image-embedded.html"

    def __call__(self, asset, local_settings=None):
        context = self.get_context(asset)
        if local_settings is not None:
            context.update(local_settings)
            if "caption" in local_settings:
                context["title"] = local_settings["caption"]
        return self.render(context)

    def get_context(self, asset):
        return {
            "asset": asset,
            "src": self.get_url(asset),
            "title": asset.title,
            "align": "center",
            "asset_caption": asset.caption,
            "hide_caption": asset.hide_caption,
        }

    def get_url(self, asset):
        generator_name = getattr(settings, "ASSET_IMAGE_EMBEDDED_GENERATOR", None)
        if generator_name:
            resized_image = asset.resized_image(generator_name)
            return resized_image.url
        return asset.url


class DocumentRenderer(RendererBase):
    template_name = "assets/document-embedded.html"

    def get_context(self, asset):
        return {
            "asset": asset,
            "title": asset.title,
            "url": asset.url,
            "file_type_name": DOCUMENT_TYPE_NAME_MAP[asset.file_type],
            "align": "left",
            "file_type": asset.file_type,
            "file_size": asset.document.file.size,
        }
