from typing import Any

from django import forms
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type

from website.forms.widgets import ArrayCheckboxSelectMultiple


class ChoiceArrayField(ArrayField):
    """
    A field that allows us to store an array of choices.
    Uses Django's Postgres ArrayField
    and a MultipleChoiceField for its formfield.
    """

    def formfield(self, **kwargs):
        defaults = {
            "form_class": forms.MultipleChoiceField,
            "choices": self.base_field.choices,
            "widget": ArrayCheckboxSelectMultiple,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def to_python(self, value):
        res = super().to_python(value)
        if isinstance(res, list):
            value = [self.base_field.to_python(val) for val in res]
        return value


class TypedJson:
    """
    Base class for JSON types.
    """

    def __init__(self, typed_json: Any) -> None:
        self.typed_json = typed_json

    def validate(self, value: Any) -> Any:
        try:
            check_type(
                value,
                self.typed_json,
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        except TypeCheckError as e:
            raise ValidationError(e, code="invalid")

        return value


class TypedJsonField(models.JSONField):
    """
    JsonField with type validation.
    """

    def __init__(self, typed_json: TypedJson | None = None, **kwargs) -> None:
        self.typed_json = typed_json
        super().__init__(**kwargs)

    def _validate_type(self, value: TypedJson) -> TypedJson:
        # Disable validation when migrations are faked
        if self.model.__module__ == "__fake__":
            return value

        if self.typed_json is None:
            return value

        if value is not None:
            try:
                self.typed_json.validate(value)
            except ValidationError as e:
                raise ValidationError(f" {e.message} Field:  {self.name} Value: {value}", code=e.code)
        elif not self.null:
            raise ValidationError(f"value must not be {value}", code="invalid")

        return value

    def validate(self, value: TypedJson, model_instance: models.Model) -> TypedJson:
        super().validate(value, model_instance)
        return self._validate_type(value)

    def pre_save(self, model_instance: models.Model, add: bool) -> TypedJson:
        value = super().pre_save(model_instance, add)
        return self._validate_type(value)
