from django.forms.utils import flatatt
from django.template.loader import get_template
from django.utils.html import format_html


class LinkButton:
    text = None
    href = None
    panels_trigger = True
    reload_on = ["saved", "deleted"]
    style = "primary"  # 'secondary', 'success', 'info', 'danger' 'cancel'
    attrs = {}
    disable_when_form_unchanged = False
    uri_params = None
    align = "left"

    def __init__(self, **kwargs):
        attrs = self.attrs or {}
        attrs.update(
            {
                "class": "",
            }
        )
        self.attrs = attrs
        for key, value in kwargs.items():
            if key == "attrs":
                self.attrs.update(value)
            elif hasattr(self, key):
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

        if self.disable_when_form_unchanged:
            attrs["disable-when-form-unchanged"] = True
            attrs["disabled"] = True

        attrs["class"] = "btn btn-{} {}".format(self.style, attrs["class"])

        return format_html("<a {attrs}>{text}</a>", attrs=flatatt(attrs), text=self.text)


class CancelButton(LinkButton):
    text = "Cancel"
    href = "#"
    style = "cancel"
    reload_on = None
    panels_trigger = False
    attrs = {
        "data-panels-action": "reject-close",
    }


class BackLink(LinkButton):
    href = "#"
    reload_on = None
    panels_trigger = False
    attrs = {
        "onclick": "window.history.back(); return false;",
    }


class SubmitButton:
    text = "Save"
    attrs = None
    style = "primary"  # 'secondary', 'success', 'info', 'danger' 'cancel'
    disable_when_form_unchanged = True
    confirmation_text = None
    align = "left"
    method = None  # When set, normal form submit is ignored and the method on the view is called.

    def __init__(self, **kwargs):
        attrs = self.attrs or {}
        attrs.update(
            {
                "type": "submit",
                "class": "",
            }
        )
        self.attrs = attrs
        for key, value in kwargs.items():
            if key == "attrs":
                self.attrs.update(value)
            elif hasattr(self, key):
                setattr(self, key, value)

    def render(self):
        attrs = self.attrs.copy()
        if self.disable_when_form_unchanged:
            attrs["disable-when-form-unchanged"] = True
            attrs["disabled"] = True
        attrs["class"] = "btn btn-{} {}".format(self.style, attrs["class"])

        if self.method:
            attrs.update(
                {
                    "name": "method",
                    "value": self.method,
                }
            )

        if self.confirmation_text:
            attrs["onclick"] = f'return confirm("{self.confirmation_text}");'

        return format_html("<button {attrs}/>{text}</button>", attrs=flatatt(attrs), text=self.text)


class ButtonGroup:
    """
    A group of buttons hidden by default and shown when the opening button is
    clicked.

    Based on the Bootstrap 4 dropdown component.
    """

    text = "More"
    style = "cancel"  # 'primary', 'secondary', 'success', 'info', 'danger' 'cancel'
    align = "right"  # 'left'
    position = "dropup"
    template_name = "bootstrap/_button-group.html"

    def __init__(self, *buttons, **kwargs):
        self.buttons = buttons
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_context_data(self):
        return {
            "text": self.text,
            "style": self.style,
            "align": self.align,
            "position": self.position,
            "buttons": self.buttons,
        }

    def render(self):
        template = get_template(self.template_name)
        context = self.get_context_data()
        return template.render(context)
