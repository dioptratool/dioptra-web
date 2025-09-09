from django.utils.html import format_html
from imagekit import ImageSpec, register
from imagekit.cachefiles import ImageCacheFile
from imagekit.processors import ResizeToFit
from imagekit.registry import generator_registry


class PanelsWidgetPreview(ImageSpec):
    processors = [ResizeToFit(100, 100)]


class PanelsListImage(ImageSpec):
    processors = [ResizeToFit(80, 40)]


register.generator("panels:widget:preview", PanelsWidgetPreview)
register.generator("panels:list:image", PanelsListImage)


def list_image(imagefile):
    generator = generator_registry.get("panels:list:image", source=imagefile)
    cachefile = ImageCacheFile(generator)
    return format_html('<img src="{url}" />', url=cachefile.url)
