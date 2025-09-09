from django.forms import Form, ModelForm


def update_field_empty_labels(form, empty_label="(None)"):
    """
    Sets the empty label for any fields that have one on a form.
    """
    for field_name in form.fields:
        if hasattr(form.fields[field_name], "empty_label") and form.fields[field_name].empty_label:
            if form.fields[field_name].required:
                form.fields[field_name].empty_label = "(Choose)"
            else:
                form.fields[field_name].empty_label = "(None)"


def update_field_placeholders(form):
    if hasattr(form, "Meta") and hasattr(form.Meta, "placeholders"):
        for field_name, placeholder in list(form.Meta.placeholders.items()):
            attrs = form.fields[field_name].widget.attrs
            if not "placeholder" in attrs:
                attrs["placeholder"] = placeholder
                form.fields[field_name].widget.attrs = attrs


def update_fields_to_readonly(form):
    for key in form.fields.keys():
        form.fields[key].disabled = True
    return form


class FormBase(Form):
    buttons = None

    def __init__(self, *args, **kwargs):
        self.readonly = kwargs.pop("readonly", False)
        super(Form, self).__init__(*args, **kwargs)
        update_field_empty_labels(self)
        update_field_placeholders(self)
        if self.readonly:
            update_fields_to_readonly(self)


class ModelFormBase(ModelForm):
    buttons = None

    def __init__(self, *args, **kwargs):
        self.readonly = kwargs.pop("readonly", False)
        self.user = kwargs.pop("user", None)
        super(ModelForm, self).__init__(*args, **kwargs)
        update_field_empty_labels(self)
        update_field_placeholders(self)
        if self.readonly:
            update_fields_to_readonly(self)

    class Meta:
        fields = "__all__"
