from django.forms import Widget
from django.forms.utils import flatatt
from django.utils.html import format_html


class HtmlOutputWidget(Widget):
    def render(self, *args, **kwargs):
        args = (self.form,) + args
        rendered = self.render_fn(*args, **kwargs)
        final_attrs = self.build_attrs(kwargs["attrs"])
        if not "class" in final_attrs:
            final_attrs["class"] = ""
        final_attrs["class"] += " html-output-widget"
        return format_html("<div {}>{}</div>", flatatt(final_attrs), rendered)
