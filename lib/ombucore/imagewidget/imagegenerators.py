from imagekit import ImageSpec, register
from imagekit.processors import ResizeToFit


class PreviewThumbnail(ImageSpec):
    processors = [ResizeToFit(200)]


register.generator("imagewidget:preview", PreviewThumbnail)
