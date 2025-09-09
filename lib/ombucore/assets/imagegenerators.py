from imagekit import ImageSpec, register
from imagekit.processors import ResizeToFit


class PreviewThumbnail(ImageSpec):
    processors = [ResizeToFit(200)]


class AssetEmbeddedImage(ImageSpec):
    processors = [ResizeToFit(width=1500, upscale=False)]


register.generator("assets:preview_thumbnail", PreviewThumbnail)
register.generator("assets:asset_embedded_image", AssetEmbeddedImage)
