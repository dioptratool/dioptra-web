import datetime

from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.db.models import CharField, ProtectedError
from django.forms.models import model_to_dict
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.html import format_html, strip_tags
from django.utils.timezone import localtime
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, FormView as GenericFormView, UpdateView
from django_filters import filters
from django_filters import views as filters_views

from ombucore.admin import panel_commands as commands
from ombucore.admin.filterset import FilterSet
from ombucore.admin.forms.reorder import ReorderForm
from ombucore.admin.sites import site
from ombucore.admin.views.mixins import FilterMixin, ModelFormMixin, PanelUIMixin


def search_field_for_model(model):
    for field in model._meta.fields:
        if isinstance(field, CharField):
            return field.name
    return None


class ChangelistView(FilterMixin, PanelUIMixin, filters_views.FilterView):
    model = None
    filterset_class = None
    template_name = "filter-list/filter-list.html"
    form_template_name = "filter-list/_form.html"
    list_template_name = "filter-list/_table.html"
    paginate_by = 20
    title = None
    supertitle = "Manage"
    text_create = "Create"

    # A list of tuples of (fn/attr nane, display name).
    # The fn name can be either:
    # - A method of the object
    # - A property of the object
    # - A method of this class, object passed as argument
    # - A property of this class
    # - A method of the model admin, object passed as argument
    # - A property of the model admin
    list_display = None
    list_display_mobile = None  # Or array of field key names from `list_display`.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialize_list_display()

    def get_filterset_class(self):
        if self.filterset_class:
            return self.filterset_class
        elif self.model:
            meta_dict = {"model": self.model}
            filterset_class_dict = {}
            search_field = search_field_for_model(self.model)
            if search_field:
                meta_dict["fields"] = ["search"]
                filterset_class_dict["search"] = filters.CharFilter(
                    field_name=search_field,
                    lookup_expr="icontains",
                    help_text="",
                )
            filterset_class_dict["Meta"] = type("Meta", (object,), meta_dict)
            filterset_class = type(
                f"{self.model._meta.object_name}FilterSet",
                (FilterSet,),
                filterset_class_dict,
            )
            return filterset_class
        else:
            raise ImproperlyConfigured(
                f"'{self.__class__.__name__}' must define 'filterset_class' or 'model'"
            )

    def _initialize_list_display(self):
        if not self.list_display:
            self.list_display = [
                ("__str__", "Title"),
            ]
        if not self.list_display_mobile:
            self.list_display_mobile = [l[0] for l in self.list_display[:2]]

    def get_title(self):
        return self.model._meta.verbose_name_plural

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        filterset = kwargs["filter"]
        kwargs["filter_form"] = filterset.form
        kwargs["list_display"] = self.list_display
        kwargs["results"] = self.process_results(kwargs["object_list"])
        kwargs["list_display_mobile"] = self.get_list_display_mobile()
        return kwargs

    def get_list_display_mobile(self):
        if self.list_display_mobile:
            return self.list_display_mobile
        if len(self.list_display) == 1:
            return [self.list_display[0][0]]
        else:
            return [f[0] for f in self.list_display[:2]]

    def get(self, request, *args, **kwargs):
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)
        self.object_list = self.modify_queryset(self.filterset.qs)
        context = self.get_context_data(filter=self.filterset, object_list=self.object_list)
        return self.render_to_response(context)

    def modify_queryset(self, queryset):
        """
        Allows view-level modifications to the queryset.
        """
        return queryset

    def process_results(self, filterset):
        return [self.process_result(obj) for obj in filterset]

    def process_result(self, obj):
        fields_array = self.result_obj_to_array(obj)
        fields_dict = {f[0]: f[1] for f in fields_array}
        return {
            "obj": obj,
            "fields": fields_array,
            "fields_dict": fields_dict,
            "operations": self.get_object_action_links(obj),
            "obj_info": site.related_info_for(obj),
        }

    def result_obj_to_array(self, obj):
        field_names = [display_field[0] for display_field in self.list_display]
        return [(field_name, self.resolve_display_field(obj, field_name)) for field_name in field_names]

    def resolve_display_field(self, obj, key):
        value = self.resolve_display_field_value(obj, key)
        display_value = self.format_display_field_value(key, value)
        return display_value

    def format_display_field_value(self, key, value):
        if value is None:
            return format_html('<span class="none">-</span>')
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, datetime.date):
            return f"{localtime(value):%b. %d, %Y}"
        if isinstance(value, datetime.datetime):
            partial_date = f"{localtime(value):%b. %d, %Y}"
            full_date = f"{localtime(value):%b. %d, %y, %-I:%M %p}"
            return format_html('<span title="{}">{}</span>', full_date, partial_date)
        return value

    def resolve_display_field_value(self, obj, key):
        if hasattr(obj, key):
            if callable(getattr(obj, key)):
                return getattr(obj, key)()
            else:
                return getattr(obj, key)
        elif hasattr(self, key):
            if callable(getattr(self, key)):
                return getattr(self, key)(obj)
            else:
                return getattr(self, key)
        elif self.model_admin and hasattr(self.model_admin, key):
            if callable(getattr(self.model_admin, key)):
                return getattr(self.model_admin, key)(obj)
            else:
                return getattr(self.model_admin, key)
        return None

    def get_object_action_links(self, obj):
        object_action_links = []
        if self.model_admin:
            object_action_links += self.model_admin.get_changelist_object_action_links(obj)
        return object_action_links

    def get_panel_action_links(self):
        action_links = []
        if self.model_admin:
            action_links += self.model_admin.get_changelist_action_links()
        return action_links


class FormView(PanelUIMixin, GenericFormView):
    """
    Doesn't support forms that take positional arguments, wrap them in a form
    class that takes kwargs and passes them to `super()` in the needed positions.
    """

    title = None
    supertitle = None
    template_name = "panel-form.html"
    success_message = ""

    def form_valid(self, form):
        success_message = self.get_success_message(form.cleaned_data)
        self.panel_commands += self.get_success_commands()
        if success_message:
            messages.success(self.request, success_message)
        form_class = self.get_form_class()
        fkwargs = self.get_form_kwargs()
        fkwargs.pop("data")
        fkwargs.pop("files")
        new_form = form_class(**fkwargs)
        return self.render_to_response(self.get_context_data(form=new_form))

    def get_success_commands(self):
        return []

    def get_success_message(self, cleaned_data):
        return self.success_message % cleaned_data


class AddView(ModelFormMixin, CreateView):
    supertitle = "Create"
    success_message = "<strong>%(title)s</strong> was successfully created."
    log_action = "Created"

    def get_title(self):
        return self.model._meta.verbose_name

    def get_panel_action_links(self):
        action_links = []
        if self.model_admin:
            action_links += self.model_admin.get_add_action_links()
        return action_links

    def get_success_commands(self):
        return [
            commands.Resolve(
                {
                    "operation": "saved",
                    "info": site.related_info_for(self.object),
                }
            )
        ]


class ChangeView(ModelFormMixin, UpdateView):
    supertitle = "Edit"
    delete_route = None
    success_message = "<strong>%(title)s</strong> was successfully updated."
    log_action = "Properties updated"

    def __init__(self, *args, **kwargs):
        self.delete_route = site.url_for(self.model, "delete")
        self.supertitle = f"Edit {self.model._meta.verbose_name}"
        super().__init__(*args, **kwargs)

    def get_panel_action_links(self):
        action_links = []
        if self.model_admin:
            action_links += self.model_admin.get_change_action_links(self.object)
        return action_links

    def get_success_commands(self):
        return [
            commands.NotifyOpener(
                {
                    "operation": "saved",
                    "info": site.related_info_for(self.object),
                }
            )
        ]


class DeleteView(PanelUIMixin, DetailView):
    title = None
    supertitle = "Delete"
    template_name = "panel-form-delete.html"
    deleted = False
    protected = False
    success_message = "<strong>%(title)s</strong> was successfully deleted."
    protected_error_message = "<strong>%(title)s</strong> is in use and can't be deleted."
    log_action = "Deleted"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object_id = self.object.id
        if "confirmed" in request.GET:
            self.delete()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def delete(self):
        obj_dict = model_to_dict(self.object)
        try:
            # Generate the success message before the object is deleted.
            success_message = self.get_success_message(obj_dict)
            self.object.delete()
            self.deleted = True
            if success_message:
                messages.success(self.request, success_message)

            # Log the event.
            self.model_admin.log(
                actor=self.request.user,
                action=self.log_action,
                obj=self.object,
                message=self.get_log_message(obj_dict),
            )
            self.panel_commands.append(commands.Resolve({"operation": "deleted"}))
        except ProtectedError:
            self.protected = True
            messages.error(self.request, self.get_protected_error_message(obj_dict))

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        if self.object and not self.deleted:
            obj_info = site.related_info_for(self.object)
            kwargs["title"] = obj_info["title"]

        attrs = ("deleted", "object_id")
        for attr in attrs:
            if not attr in kwargs:
                kwargs[attr] = getattr(self, attr)

        return kwargs

    def get_success_message(self, data):
        if not "title" in data:
            data["title"] = str(self.object)
        return self.success_message % data

    def get_log_message(self, cleaned_data):
        return strip_tags(self.get_success_message(cleaned_data))

    def get_protected_error_message(self, data):
        return self.protected_error_message % data


class PreviewView(DetailView):
    title = None
    supertitle = "Preview"
    template_name = "panel-preview.html"

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        attrs = (
            "title",
            "supertitle",
        )
        for attr in attrs:
            if not attr in kwargs:
                kwargs[attr] = getattr(self, attr)
        if self.object and not kwargs["title"]:
            kwargs["title"] = getattr(self.object, "title", getattr(self.object, "name", None))
        return kwargs


class ReorderView(FormView, PanelUIMixin):
    model = None
    title = None
    supertitle = "Reorder"
    template_name = "panel-form-reorder.html"
    form_class = ReorderForm
    queryset = None
    order_field = "order"

    def get_title(self):
        return self.model._meta.verbose_name_plural

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop("prefix")
        kwargs.pop("initial")
        kwargs["order_field"] = self.order_field
        if self.queryset:
            kwargs["choices"] = self.queryset.order_by(self.order_field).all()
        else:
            kwargs["choices"] = self.model.objects.order_by(self.order_field).all()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj_actions = {}
        for obj in context["form"].queryset:
            obj_actions[obj.pk] = self.get_object_action_links(obj)
        context["obj_actions"] = obj_actions
        return context

    def get_object_action_links(self, obj):
        return []

    def get_success_commands(self):
        return [
            commands.Resolve(
                {
                    "operation": "saved",
                }
            )
        ]


class NestedReorderView(PanelUIMixin, TemplateView):
    model = None
    title = None
    supertitle = "Reorder"
    template_name = "panel-nested-reorder.html"
    queryset = None

    def get_title(self):
        return self.model._meta.verbose_name_plural

    def get_queryset(self):
        return self.model.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        objs = self.get_queryset()
        obj_actions = {}
        for obj in objs:
            obj_actions[obj.pk] = self.get_object_action_links(obj)
        context.update(
            {
                "nodes": objs,
                "obj_actions": obj_actions,
            }
        )
        return context

    def get_panel_action_links(self):
        action_links = []
        if self.model_admin:
            action_links += self.model_admin.get_changelist_action_links()
        return action_links

    def get_object_action_links(self, obj):
        object_action_links = []
        if self.model_admin:
            object_action_links += self.model_admin.get_changelist_object_action_links(obj)
        return object_action_links

    def post(self, request):
        try:
            node = self.model.objects.get(pk=request.POST["node_pk"])
            target = self.model.objects.get(pk=request.POST["target_pk"])
            position = request.POST["position"]
            self.model.objects.move_node(node, target, position)
            messages.success(request, f"{self.model._meta.verbose_name} saved!")
            return JsonResponse(
                {
                    "messages": [
                        {
                            "level": m.level_tag,
                            "message": m.message,
                            "extra_tags": m.extra_tags,
                        }
                        for m in messages.get_messages(request)
                    ],
                }
            )
        except Exception:
            pass
        return HttpResponseBadRequest()
