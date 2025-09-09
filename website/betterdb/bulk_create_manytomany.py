from collections.abc import Iterable

from django.db import models


def bulk_create_manytomany(
    model_from,
    field_name: str,
    model_from_name: str,
    model_to_name: str,
    from_to_pairs: Iterable[tuple[models.Model, models.Model]],
):
    """Bulk create many-to-many relationship.
    Many thanks to https://stackoverflow.com/a/62658821
    for the inspiration.

        tag1 = Tag.objects.get(id=1)
        tag2 = Tag.objects.get(id=2)
        photo1 = Photo.objects.get(id=1)
        photo2 = Photo.objects.get(id=2)

        bulk_create_manytomany(
            model_from=Tag,
            field_name="photos",
            model_from_name="tag",
            model_to_name="photo",
            from_to_pairs=[
                (tag1, photo1),
                (tag1, photo2),
                (tag2, photo2),
            ]
        )
    """
    through_objs = []
    for from_obj, to_obj in from_to_pairs:
        through_objs.append(
            getattr(model_from, field_name).through(
                **{
                    f"{model_from_name.lower()}_id": from_obj.pk,
                    f"{model_to_name.lower()}_id": to_obj.pk,
                }
            )
        )
    getattr(model_from, field_name).through.objects.bulk_create(through_objs)
