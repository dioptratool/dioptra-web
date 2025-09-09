import re

from django import forms
from django.core.validators import RegexValidator
from django.db import models
from mptt.models import TreeForeignKey
from sortedm2m.fields import SortedManyToManyField

from ombucore.admin.forms import (
    ModelChoiceField,
    ModelMultipleChoiceField,
    ModelMultipleChoiceTreeField,
)


class ManyToManyField(SortedManyToManyField):
    model_classes = None
    clone_on_clone = False

    def __init__(self, to, **kwargs):
        self.model_classes = kwargs.pop("models", None)
        self.clone_on_clone = kwargs.pop("clone_on_clone", False)
        super().__init__(to, **kwargs)

    def formfield(self, **kwargs):
        defaults = {}
        defaults["form_class"] = ModelMultipleChoiceField
        if self.model_classes:
            defaults["model_classes"] = self.model_classes
        defaults.update(kwargs)
        return super().formfield(**defaults)


class CustomTreeForeignKey(TreeForeignKey):
    model_classes = None

    def __init__(self, to, **kwargs):
        self.model_classes = kwargs.pop("models", None)
        self.label = kwargs.pop("label", None)
        super().__init__(to, **kwargs)

    def formfield(self, **kwargs):
        defaults = {}
        self.model_class_dict = {}
        if self.model_classes:
            defaults["model_classes"] = self.model_classes
            for model_class in self.model_classes:
                self.model_class_dict[model_class._meta.verbose_name] = model_class
        defaults["form_class"] = ModelMultipleChoiceTreeField
        defaults["field_name"] = self.related_query_name()
        defaults["label"] = self.label
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def save_form_data(self, instance, data):
        # If the root node *and* the form instance have been saved to the db,
        # the form instance will have the root node's ID stored in its '[query_name]_id' field
        root_node = getattr(instance, self.name)
        base_block_class = self.related_model.__bases__[0]

        # If there is no root node, check if any of the nodes in data have a root node
        if not root_node:
            # Loop through the data get a root node
            for index, item in enumerate(data):
                node_data = data[index]
                if node_data and not getattr(instance, self.name):
                    node_id = node_data["objInfo"]["id"]
                    node = base_block_class.objects.filter(id=node_id).first()
                    root_node = node.get_root()
                    if root_node.__class__ == self.related_model:
                        setattr(instance, self.name, root_node)
                        break
                    elif node_data.get("children"):
                        children_data = node_data.get("children")
                        self.recursive_find_root_node(children_data, instance, base_block_class)

        if not getattr(instance, self.name):
            setattr(
                instance,
                self.name,
                self.related_model.objects.create(title=self.name + "_rootblock"),
            )

        root_node = getattr(instance, self.name)
        root_node.refresh_from_db()

        current_tree_pks = []

        for index, node_info in enumerate(data):
            node_instance = base_block_class.objects.get(pk=node_info["id"])

            node_instance.move_to(root_node, "last-child")
            root_node.refresh_from_db()  # Do this to update where 'last-child' is
            current_tree_pks.append(node_instance.pk)

            if node_info.get("children"):
                for child_index, node_child in enumerate(node_info.get("children")):
                    child_node_instance = base_block_class.objects.get(pk=node_child["id"])

                    self.recursive_tree_save(
                        node_instance,
                        child_node_instance,
                        node_info["children"],
                        child_index,
                        current_tree_pks,
                        base_block_class,
                        root_node,
                    )

        nodes_to_remove = root_node.get_descendants().exclude(pk__in=current_tree_pks)
        for node in nodes_to_remove.order_by("-level"):
            node.refresh_from_db()
            node.delete()

    def recursive_find_root_node(self, data, instance, base_block_class):
        for index, item in enumerate(data):
            node_data = data[index]
            if node_data and not getattr(instance, self.name):
                node_id = node_data["objInfo"]["id"]
                node = base_block_class.objects.filter(id=node_id).first()
                root_node = node.get_root()
                if root_node.__class__ == self.related_model:
                    setattr(instance, self.name, root_node)
                    break
                elif node_data.get("children"):
                    children_data = node_data.get("children")
                    self.recursive_find_root_node(children_data, instance, base_block_class)

    def recursive_tree_save(
        self,
        parent_instance,
        node_instance,
        data,
        index,
        current_tree_pks,
        base_block_class,
        root_node,
    ):
        node_instance.move_to(parent_instance, "last-child")
        root_node.refresh_from_db()
        parent_instance.refresh_from_db()  # Do this to update where 'last-child' is
        current_tree_pks.append(node_instance.pk)

        if data[index].get("children"):
            for child_index, node_child in enumerate(data[index].get("children")):
                child_node_instance = base_block_class.objects.get(pk=node_child["id"])

                self.recursive_tree_save(
                    node_instance,
                    child_node_instance,
                    data[index]["children"],
                    child_index,
                    current_tree_pks,
                    base_block_class,
                    root_node,
                )


class ManyToManyTreeField(SortedManyToManyField):
    model_classes = None

    def __init__(self, to, **kwargs):
        self.model_classes = kwargs.pop("models", None)
        super().__init__(to, **kwargs)

    def formfield(self, **kwargs):
        defaults = {}
        self.model_class_dict = {}
        if self.model_classes:
            defaults["model_classes"] = self.model_classes
            for model_class in self.model_classes:
                self.model_class_dict[model_class._meta.verbose_name] = model_class
        defaults["form_class"] = ModelMultipleChoiceTreeField
        defaults["field_name"] = self.name
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def save_form_data(self, instance, data):
        for index, node in enumerate(data):
            node_class = self.model_class_dict[node["objInfo"]["verbose_name"]]
            node_instance = node_class.objects.get(pk=node["objInfo"]["id"])

            if node.get("children"):
                for child_index, node_child in enumerate(node.get("children")):
                    child_node_class = self.model_class_dict[node_child["objInfo"]["verbose_name"]]
                    child_node_instance = child_node_class.objects.get(pk=node_child["objInfo"]["id"])
                    self.recursive_tree_save(
                        node_instance,
                        child_node_instance,
                        node["children"],
                        child_index,
                    )

            if index > 0:
                node_instance.lft = data[index - 1]["objInfo"]["id"]
            if index + 1 < len(data):
                node_instance.rght = data[index + 1]["objInfo"]["id"]
            node_instance.save()

    def recursive_tree_save(self, parent_instance, node_instance, data, index):
        node_instance.parent = parent_instance
        if index > 0:
            node_instance.lft = data[index - 1]["objInfo"]["id"]
        if index + 1 < len(data):
            node_instance.rght = data[index + 1]["objInfo"]["id"]
        node_instance.save()

        if data[index].get("children"):
            for child_index, node_child in enumerate(data[index].get("children")):
                child_node_class = self.model_class_dict[node_child["objInfo"]["verbose_name"]]
                child_node_instance = child_node_class.objects.get(pk=node_child["objInfo"]["id"])
                self.recursive_tree_save(
                    node_instance,
                    child_node_instance,
                    data[index]["children"],
                    child_index,
                )


class ForeignKey(models.ForeignKey):
    """
    Wrapper around ForeignKey to trigger the ModelChoice instead of a
    select input.
    """

    model_classes = None

    def __init__(self, to, **kwargs):
        self.model_classes = kwargs.pop("models", None)
        super().__init__(to, **kwargs)

    def formfield(self, **kwargs):
        defaults = {}
        defaults["form_class"] = ModelChoiceField
        if self.model_classes:
            defaults["model_classes"] = self.model_classes
        defaults.update(kwargs)
        return super().formfield(**defaults)


# Allows alphanumberic characters, dashes, underscores and slashes.
# May not start with a slash.
url_path_re = re.compile(r"^[^\/][-a-zA-Z0-9_\/]+$")
validate_url_path = RegexValidator(
    url_path_re,
    "Enter a valid 'URL Path' consisting of letters, numbers, underscores, hyphens and slashes.",
    "invalid",
)


class UrlPathField(models.CharField):
    default_validators = [validate_url_path]
    description = "URL Path (up to %(max_length)s)"

    def formfield(self, **kwargs):
        defaults = {"form_class": UrlPathFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class UrlPathFormField(forms.fields.CharField):
    default_validators = [validate_url_path]

    def clean(self, value):
        value = self.to_python(value).strip().strip("/")
        return super().clean(value)
