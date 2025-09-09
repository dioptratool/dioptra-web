from django.forms.utils import flatatt
from django.utils.html import format_html


class ActionLink:
    text = None
    href = None
    panels_trigger = True
    reload_on = ["saved", "deleted"]
    attrs = {}
    primary = True
    uri_params = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def render(self):
        attrs = self.attrs.copy()

        if self.href:
            attrs["href"] = self.href

        if self.uri_params:
            uri = "?"
            for key, val in self.uri_params.items():
                uri += key + "=" + val + "&"

            if "href" in attrs:
                attrs["href"] += uri

        if self.panels_trigger:
            attrs["data-panels-trigger"] = True
            if self.reload_on:
                attrs["data-panels-reload-on"] = ",".join(self.reload_on)

        return format_html("<a {attrs}>{text}</a>", attrs=flatatt(attrs), text=self.text)
