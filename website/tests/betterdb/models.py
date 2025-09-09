from django.db import models

from website.betterdb import ReprMixin


class ExampleTree(ReprMixin, models.Model):
    name = models.TextField()

    parent = models.ForeignKey(
        "ExampleTree", null=True, on_delete=models.SET_NULL, related_name="children_set"
    )


class ExampleM2M(ReprMixin, models.Model):
    name = models.TextField()

    others = models.ManyToManyField("ExampleM2M", related_name="others_reverse")
