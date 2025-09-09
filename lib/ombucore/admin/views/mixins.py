import copy

from django.contrib import messages
from django.utils.html import strip_tags
from django.views.generic.edit import BaseUpdateView
from django_filters import views as filters_views

from ombucore.admin.actionlink import ActionLink
from ombucore.admin.sites import site


class PanelUIMixin:
    title = None
    supertitle = None
    subtitle = None
    subtitle_auxiliary = None
    model_admin = None
    tabs = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.panel_commands = []

    def get_title(self):
        return self.title

    def get_supertitle(self):
        return self.supertitle

    def get_subtitle(self):
        return self.subtitle

    def get_subtitle_auxiliary(self):
        return self.subtitle_auxiliary

    def get_tabs(self):
        return self.tabs

    def get_panel_commands(self):
        return self.panel_commands

    def get_panel_ui_context(self):
        panel_action_links = self.get_panel_action_links()
        context = {
            "title": self.get_title(),
            "supertitle": self.get_supertitle(),
            "subtitle": self.get_subtitle(),
            "subtitle_auxiliary": self.get_subtitle_auxiliary(),
            "panel_action_links": {
                "primary": [l for l in panel_action_links if l.primary],
                "secondary": [l for l in panel_action_links if not l.primary],
            },
            "tabs": self.get_tabs(),
            "panel_commands": self.get_panel_commands(),
        }
        return context

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        kwargs.update(self.get_panel_ui_context())
        return kwargs

    def get_panel_action_links(self):
        return []


class FilterMixin(filters_views.FilterMixin):
    """
    Replacement for django-filters-mixin which only provides a single view mixin
    that isn't Python 3 compatible.

    @see https://github.com/bashu/django-filters-mixin
    """

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        if kwargs["data"] is not None and "page" in kwargs["data"]:
            data = kwargs["data"].copy()
            del data["page"]
            kwargs["data"] = data
        return kwargs


class MultipleSubmitButtonsMixin:
    """
    A mixin that lets the form submit with multiple buttons. If a button has
    the `method` property set, that method will be called on the view instead
    of the usual form validation flow.
    """

    buttons = None

    def get_buttons(self):
        return copy.deepcopy(self.buttons)

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        kwargs["buttons"] = self.get_buttons()
        return kwargs

    def post(self, request, *args, **kwargs):
        method = request.POST.get("method", None)
        if method:
            if isinstance(self, BaseUpdateView):
                self.object = self.get_object()
            for button in self.get_buttons():
                if hasattr(button, "method") and button.method == method and hasattr(self, button.method):
                    return getattr(self, button.method)()
        return super().post(request, *args, **kwargs)


class ModelFormMixin(PanelUIMixin, MultipleSubmitButtonsMixin):
    title = None
    supertitle = None
    template_name = "panel-form.html"
    success_message = ""
    success_redirect_urlname = "change"
    log_action = ""

    def form_valid(self, form):
        # Save the object.
        self.object = form.save()

        # Create a success message.
        success_message = self.get_success_message(form.cleaned_data)
        if success_message:
            messages.success(self.request, success_message)

        # Log the event.
        if self.model_admin and self.log_action:
            self.model_admin.log(
                actor=self.request.user,
                action=self.log_action,
                obj=self.object,
                message=self.get_log_message(form.cleaned_data),
            )

        # Append the success commands for the template rendering.
        self.panel_commands += self.get_success_commands()

        # Rebuild the form to re-render the template.
        form_class = self.get_form_class()
        fkwargs = self.get_form_kwargs()
        fkwargs.pop("data")
        fkwargs.pop("files")
        new_form = form_class(**fkwargs)

        return self.render_to_response(self.get_context_data(form=new_form))

    def get_success_commands(self):
        return []

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        if self.object:
            kwargs["obj_info"] = site.related_info_for(self.object)
            kwargs["title"] = kwargs["obj_info"]["title"]
        return kwargs

    def get_success_message(self, cleaned_data):
        if not "title" in cleaned_data:
            cleaned_data = cleaned_data.copy()
            cleaned_data["title"] = str(self.object)
        return self.success_message % cleaned_data

    def get_log_message(self, cleaned_data):
        return strip_tags(self.get_success_message(cleaned_data))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "user": self.request.user,
            }
        )
        return kwargs


class ChangelistSelectViewMixin:
    template_name = "filter-list/select-list.html"
    selectable = True
    supertitle = "Select a"

    def get_title(self):
        return self.model._meta.verbose_name

    def get_object_action_links(self, obj):
        object_action_links = [
            ActionLink(
                text="Choose",
                href="#",
                panels_trigger=False,
                attrs={"class": "operations-select"},
            ),
        ]
        object_action_links += super().get_object_action_links(obj)
        return object_action_links
