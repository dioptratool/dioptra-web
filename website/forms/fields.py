from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms import DecimalField, ModelChoiceField
from django.utils.translation import gettext_lazy as _

from website.models.field_types import SubcomponentLabelsType
from .widgets import (
    SortableSelectMultipleAnalysisInterventionsWidget,
    SortableSelectMultipleSubcomponentLabelsWidget,
)


class PositiveFixedDecimalField(DecimalField):
    def __init__(self, *args, **kwargs):
        self.allow_zero = kwargs.pop("allow_zero", None)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        if value:
            value = value.quantize(settings.DECIMAL_PRECISION)
        return value

    def validate(self, value):
        super().validate(value)
        if isinstance(value, Decimal):
            if self.allow_zero:
                if value < 0:
                    raise ValidationError(
                        "This field is required and must be greater than or equal to zero.",
                        code="invalid",
                    )
            else:
                if value <= 0:
                    raise ValidationError(
                        "This field is required and must be greater than zero.",
                        code="invalid",
                    )


class SubcomponentLabelField(forms.JSONField):
    widget = SortableSelectMultipleSubcomponentLabelsWidget

    def clean(self, value: list) -> dict:
        value = super().clean(value)
        SubcomponentLabelsType.validate(value)
        if len(value) > 8:
            raise ValidationError(_("No more than 8 sublabels are allowed."), code="invalid")
        return value


class AnalysisInterventionManageField(forms.JSONField):
    widget = SortableSelectMultipleAnalysisInterventionsWidget

    def __init__(self, *args, **kwargs):
        kwargs["required"] = False
        super().__init__(*args, **kwargs)

    def clean(self, value: list) -> dict:
        value = super().clean(value)
        if len(value) > 5:
            raise ValidationError(_("No more than 5 interventions are allowed."), code="invalid")
        return value


class InterventionInstanceChoiceField(ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.display_name()
