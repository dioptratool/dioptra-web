from imagekit import ImageSpec, register
from imagekit.processors import ResizeToFit


class LoginLogo(ImageSpec):
    processors = [ResizeToFit(228, 228)]
    options = {"quality": 95}


register.generator("website:login-logo", LoginLogo)
