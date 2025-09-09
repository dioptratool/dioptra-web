import json

from django import forms
from sortedm2m.forms import SortedMultipleChoiceField

from ombucore.admin.sites import site
from ombucore.admin.widgets import GenericManyToManyWidget
from ombucore.admin.widgets import ModelMultipleChoiceTreeWidget, ModelMultipleChoiceWidget, RelationWidget


###############################################################################
# Form Fields
###############################################################################


class ModelMultipleChoiceField(SortedMultipleChoiceField):
    model_classes = []

    def __init__(self, *args, **kwargs):
        if "model_classes" in kwargs:
            self.model_classes = kwargs.pop("model_classes")
        super().__init__(*args, **kwargs)
        self.widget = ModelMultipleChoiceWidget(
            model_class=self.queryset.model, model_classes=self.model_classes
        )


class ModelMultipleChoiceTreeField(forms.CharField):
    model_classes = []

    def __init__(self, *args, **kwargs):
        kwargs.pop("limit_choices_to")
        if "to_field_name" in kwargs:
            kwargs.pop("to_field_name")
        if "model_classes" in kwargs:
            self.model_classes = kwargs.pop("model_classes")
        if "field_name" in kwargs:
            self.field_name = kwargs.pop("field_name")
        if "queryset" in kwargs:
            self.model = kwargs.pop("queryset").model
        if "label" in kwargs:
            self.label = kwargs.pop("label")
        super().__init__(*args, **kwargs)
        self.widget = ModelMultipleChoiceTreeWidget(
            model_class=self.model,
            model_classes=self.model_classes,
        )

    def to_python(self, value):
        if value:
            return json.loads(value)
        else:
            return ""

    ## Prepares the tree for the root block render widget
    ## Returns the pk of the root block for the tree
    def prepare_value(self, value):
        ## If value is a string then it is a json formatted string that describes the tree structure
        ## We have to extract the root node from this information
        ## The first entry in the dictionary is always the root node's first child
        if isinstance(value, str):
            tree_dict = json.loads(value)
            ## Return the root node pk if tree_dict has data, otherwise return the empty list tree_dict
            if tree_dict:
                return self.model.__bases__[0].objects.get(pk=tree_dict[0]["objInfo"]["id"]).parent.pk
            else:
                return tree_dict
        # Else if the value is a root node, return it's pk
        elif isinstance(value, self.model):
            return value.pk
        # Finally, if is not a string or a root node object, it's the root node's pk
        else:
            return value


class ModelChoiceField(forms.ModelChoiceField):
    model_classes = []

    def __init__(self, *args, **kwargs):
        if "model_classes" in kwargs:
            self.model_classes = kwargs.pop("model_classes")
        super().__init__(*args, **kwargs)
        self.widget = RelationWidget(model_class=self.queryset.model, model_classes=self.model_classes)


class GenericManyToManyFormField(forms.MultipleChoiceField):
    model_classes = []

    def __init__(self, *args, **kwargs):
        self.model_classes = kwargs.pop("model_classes")
        super().__init__(*args, **kwargs)
        self.widget = GenericManyToManyWidget(model_classes=self.model_classes)

    def prepare_value(self, value):
        if isinstance(value, list):
            return value
        elif not value:
            return []

        # Otherwise value is a gm2m.managers.GM2MManager instance
        def generic_id(model):
            related_info = site.related_info_for(model)
            return "{}/{}".format(related_info["ctype_id"], related_info["id"])

        return list(map(generic_id, value.all()))

    def to_python(self, values):
        """
        Converts list values in the form "{ctype_id}/{id}" to a list of models.
        """
        models = []
        for generic_id in values:
            model = self.model_from_generic_id(generic_id)
            if model:
                models.append(model)
        return models

    def has_changed(self, initial_value, data_value):
        return self.prepare_value(initial_value) != data_value

    def valid_value(self, model):
        if type(model) in self.model_classes:
            return True
        return False

    def content_type_class(self, ctype_id):
        from django.contrib.contenttypes.models import ContentType

        return ContentType.objects.get_for_id(ctype_id).model_class()

    def model_from_generic_id(self, generic_id):
        ctype_id, model_id = list(map(int, generic_id.split("/")))
        try:
            model_class = self.content_type_class(ctype_id)
            model = model_class.objects.get(id=model_id)
            return model
        except Exception:
            pass
        return None
