import os

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class FileExtensionValidator:
    whitelist = []

    def __init__(self, whitelist=None):
        if whitelist is not None:
            self.whitelist = [i.lower() for i in whitelist]

    def __call__(self, value):
        filename = value.name
        ext = os.path.splitext(filename)[1].split(".")[-1].lower()
        if ext not in self.whitelist:
            types = ", ".join(self.whitelist)
            raise ValidationError(f"Please upload a file of the type: {types}")

    def __eq__(self, other):
        return self.whitelist == other.whitelist
