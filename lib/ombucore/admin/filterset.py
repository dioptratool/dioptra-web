import copy
from collections import OrderedDict

from django import forms
from django.http import QueryDict
from django_filters.filterset import FilterSet as FiltersFilterSet

from ombucore.admin.templatetags.panels_extras import a_or_an


class FilterSet(FiltersFilterSet):
    def __init__(self, *args, **kwargs):
        if "order_by" in self.base_filters:
            if "data" in kwargs and kwargs["data"]:
                data = copy.copy(kwargs["data"])  # Make the QueryDict mutable.
            else:
                data = QueryDict(mutable=True)
            if not data.get("order_by"):
                data["order_by"] = self.base_filters["order_by"].extra["choices"][0][0]
                kwargs["data"] = data

        super().__init__(*args, **kwargs)
        if "search" in self.filters and not "placeholder" in self.filters["search"].field.widget.attrs:
            verbose_name = self._meta.model._meta.verbose_name
            placeholder = f"Find {a_or_an(verbose_name)} {verbose_name.lower()}..."
            self.filters["search"].field.widget.attrs["placeholder"] = placeholder

    def get_form_class(self):
        """
        Overwritten to include hidden fields for any query string values not
        implemented by filterset fields, thus persisting them across searches.
        """
        fields = OrderedDict([(name, filter_.field) for name, filter_ in self.filters.items()])

        # <OMBU CHANGE:
        fields = self.add_hidden_fields_for_data(fields, self.data)
        # OMBU>

        return type(f"{self.__class__.__name__}Form", (self._meta.form,), fields)

    def add_hidden_fields_for_data(self, fields, data):
        for key, value in data.items():
            if not key in fields:
                fields[key] = forms.CharField(widget=forms.HiddenInput)
        return fields
