from django import forms
from django.db import transaction


class ReorderForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.order_field = kwargs.pop("order_field")
        self.queryset = kwargs.pop("choices")
        try:
            self.label = kwargs.pop("label")
        except KeyError:
            pass
        super().__init__(*args, **kwargs)
        self.fields["choices"] = forms.ModelMultipleChoiceField(
            queryset=self.queryset,
            widget=forms.widgets.SelectMultiple,
            initial=self.queryset,
        )

    def clean(self):
        # Absent when field validation failed (e.g. a posted pk no longer in
        # the queryset); let that error surface instead of crashing.
        choices_qs = self.cleaned_data.get("choices")
        if choices_qs is None:
            return self.cleaned_data
        choices = self.data.getlist("choices")
        with transaction.atomic():
            for i, choice in enumerate(choices):
                ordered_object = choices_qs.get(pk=choice)
                setattr(ordered_object, self.order_field, i + 1)
                ordered_object.save()
        return self.cleaned_data

    class Media:
        js = (
            "panels/lib/Sortable.js",
            "panels/js/panels-reorder.js",
        )

        css = {"all": ("panels/css/panels-relation-widget.css",)}
