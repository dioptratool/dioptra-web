from django.db import models


class OrderableMixin:
    """
    A model mixin that will automatically set an ordering value to the
    current largest + 1 when saving if it's not already set.
    """

    order_field = "order"

    def save(self, *args, **kwargs):
        # Fill in the `order` if it doesn't exist yet.
        if not getattr(self, self.order_field):
            largest_weight = self.__class__.objects.aggregate(models.Max(self.order_field))[
                f"{self.order_field}__max"
            ]
            new_weight = largest_weight + 1 if largest_weight is not None else 0
            setattr(self, self.order_field, new_weight)
        return super().save(*args, **kwargs)
