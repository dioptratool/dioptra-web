from django.forms import Field

from .widgets import HtmlOutputWidget


class HtmlOutputField(Field):
    widget = HtmlOutputWidget

    def __init__(self, *args, **kwargs):
        self.render_fn = kwargs.pop("render_fn")
        super().__init__(*args, **kwargs)
        self.widget.render_fn = self.render_fn

    def get_bound_field(self, *args, **kwargs):
        bound_field = super().get_bound_field(*args, **kwargs)
        bound_field.field.widget.form = bound_field.form
        return bound_field
