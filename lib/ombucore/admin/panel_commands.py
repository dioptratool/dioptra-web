from django.template.loader import get_template


class PanelCommand:
    """
    A class that encompasses the functionality that can be called on the current
    panel.
    """

    panel_method = "resolve"
    template_name = "_panel-command.html"
    payload = None

    def __init__(self, payload=None):
        self.payload = payload

    def render(self):
        template = get_template(self.template_name)
        context = self.get_context_data()
        return template.render(context)

    def get_context_data(self):
        context = {"payload": self.payload}
        if self.panel_method:
            context["panel_method"] = self.panel_method
        return context


class Reject(PanelCommand):
    panel_method = "reject"


class Resolve(PanelCommand):
    panel_method = "resolve"


class NotifyOpener(PanelCommand):
    panel_method = "notify"


class RedirectOpener(PanelCommand):
    panel_method = "notify"

    def __init__(self, to_url):
        self.payload = {"redirect_to": to_url}


class Redirect(PanelCommand):
    template_name = "_panel-command-redirect.html"
    panel_method = None


class MultiPanelCommand(PanelCommand):
    commands = []

    def render(self):
        output = "\n\r".join([command.render() for command in self.commands])
        return output


class CloseCurrentAndRedirectOpener(MultiPanelCommand):
    def __init__(self, to_url):
        self.commands = [
            RedirectOpener(
                to_url
            ),  # Notifies the opener that it should be redirected when current is closed.
            Reject(),  # Close the current panel.
        ]
