import re

from PIL import Image
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext as _


class NumberValidator:
    def validate(self, password, user=None):
        if not re.findall(r"\d", password):
            raise ValidationError(
                _("The password must contain at least 1 digit, 0-9."),
                code="password_no_number",
            )

    def get_help_text(self):
        return _("Your password must contain at least 1 digit, 0-9.")


class LetterValidator:
    def validate(self, password, user=None):
        if not re.findall(r"[A-Z]|[a-z]", password):
            raise ValidationError(
                _("The password must contain at least 1 letter"),
                code="password_no_letter",
            )

    def get_help_text(self):
        return _("The password must contain at least 1 letter")


class UppercaseValidator:
    def validate(self, password, user=None):
        if not re.findall("[A-Z]", password):
            raise ValidationError(
                _("The password must contain at least 1 uppercase letter, A-Z."),
                code="password_no_upper",
            )

    def get_help_text(self):
        return _("Your password must contain at least 1 uppercase letter, A-Z.")


class LowercaseValidator:
    def validate(self, password, user=None):
        if not re.findall("[a-z]", password):
            raise ValidationError(
                _("The password must contain at least 1 lowercase letter, a-z."),
                code="password_no_lower",
            )

    def get_help_text(self):
        return _("Your password must contain at least 1 lowercase letter, a-z.")


class SymbolValidator:
    def validate(self, password, user=None):
        if not re.findall(r'[()[\]{}|\\`~!@#$%^&*_\-+=;:\'",<>./?]', password):
            raise ValidationError(
                _(r"""The password must contain at least 1 symbol: ()[]{}|\`~!@#$%^&*_-+=;:'",<>./?"""),
                code="password_no_symbol",
            )

    def get_help_text(self):
        return _(r"""Your password must contain at least 1 symbol: ()[]{}|\`~!@#$%^&*_-+=;:'",<>./?""")


@deconstructible
class FileSizeValidator:
    def __init__(self, byte_limit=(5 * 1024 * 1024)):
        self.limit = byte_limit

    def __call__(self, value):
        if value.size > self.limit:
            raise ValidationError(
                _(f"This file is too large. Size should not exceed {self.limit // 1024 // 1024} MB.")
            )

    def __eq__(self, other):
        return self.limit == other.limit

    def get_help_text(self):
        return _("Your file must be less than {}mb.")


@deconstructible
class ImageSizeValidator:
    def __init__(self, dim=(228, 228)):
        self.x = dim[0]
        self.y = dim[1]

    def __call__(self, value):
        try:
            im = Image.open(value)
        except OSError:
            raise ValidationError(_("Unable to validate this as an image file."))
        x, y = im.size
        if x > self.x or x <= 0 or y > self.y or y <= 0:
            raise ValidationError(_(f"Image must be at most {self.x}x{self.y}.  This was {x}x{y}"))

    def __eq__(self, other):
        return self.x == other.x and self.y == self.y
