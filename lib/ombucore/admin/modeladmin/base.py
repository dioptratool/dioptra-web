from inspect import isclass

from django import forms
from django.contrib.auth import get_permission_codename
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ImproperlyConfigured
from django.urls import path
from django.urls import reverse

from app_log.logger import log
from ombucore.admin.actionlink import ActionLink
from ombucore.admin.filterset import FilterSet
from ombucore.admin.forms.base import ModelFormBase
from ombucore.admin.views import AddView, ChangeView, ChangelistView, DeleteView
from ombucore.admin.views import ChangelistSelectViewMixin, ReorderView
from ombucore.utils import extend_subclass


class ModelAdmin(metaclass=forms.MediaDefiningClass):
    form_class = ModelFormBase  # For both `add` and `change`.
    form_config = None
    add_form_class = None  # For `add`.
    add_form_config = None
    change_form_class = None  # For `change`.
    change_form_config = None

    add_view = AddView
    change_view = ChangeView
    delete_view = DeleteView
    changelist_view = ChangelistView
    changelist_select_view = None
    reorder_view = ReorderView
    preview_view = False
    clone_view = False

    filterset_class = None
    filterset_config = None
    list_display = None
    list_display_mobile = None
    list_display_grid = False

    form_tabs = None  # No tabs by default.
    app_log = True

    def __init__(self, model, admin_site):
        if not self.form_class:
            raise ImproperlyConfigured(f"{self.__class__.__name__}.form_class is not defined.")
        self.form_config = {} if not self.form_config else self.form_config
        self.add_form_config = self.form_config if not self.add_form_config else self.add_form_config
        self.change_form_config = self.form_config if not self.change_form_config else self.change_form_config
        self.model = model
        self.opts = model._meta
        self.admin_site = admin_site
        self._initialize_form_classes()
        self._initialize_filterset_class()
        self._initialize_views()

    def _initialize_form_classes(self):
        if self.add_view:
            self.add_form_class = (
                self.add_form_class or getattr(self.add_view, "form_class", None) or self.form_class
            )
            self.add_form_config["model"] = self.model
            self.add_form_class = extend_subclass(self.add_form_class, "Meta", self.add_form_config)

        if self.change_view:
            self.change_form_class = (
                self.change_form_class or getattr(self.change_view, "form_class", None) or self.form_class
            )
            self.change_form_config["model"] = self.model
            self.change_form_class = extend_subclass(self.change_form_class, "Meta", self.change_form_config)

    def _initialize_filterset_class(self):
        """
        Auto-generate a filterset class if it isn't set and a config is provided.
        """
        if self.filterset_class is None and self.filterset_config:
            self.filterset_config.update(
                {
                    "__module__": self.model.__module__,
                    "Meta": type(
                        "Meta",
                        (object,),
                        {
                            "model": self.model,
                            "fields": list(self.filterset_config.keys()),
                        },
                    ),
                }
            )
            self.filterset_class = type(
                f"{self.model.__name__}FilterSet",
                (FilterSet,),
                self.filterset_config,
            )

        elif self.filterset_class and not hasattr(self.filterset_class.Meta, "model"):
            # Inject 'model' into the filterset `Meta` class.
            self.filterset_class = extend_subclass(
                self.filterset_class,
                "Meta",
                {
                    "model": self.model,
                },
            )

    def _initialize_views(self):
        """
        Auto-creates views for any views not defined on the ModelAdmin class.
        """
        if self.add_view:
            opts = {
                "__module__": self.model.__module__,
                "model": self.model,
                "model_admin": self,
                "form_class": self.add_form_class,
            }
            self.add_view = type(f"{self.model.__name__}AddView", (self.add_view,), opts)

        if self.change_view:
            opts = {
                "__module__": self.model.__module__,
                "model": self.model,
                "model_admin": self,
                "form_class": self.change_form_class,
            }
            self.change_view = type(f"{self.model.__name__}ChangeView", (self.change_view,), opts)

        if self.delete_view:
            self.delete_view = type(
                f"{self.model.__name__}DeleteView",
                (self.delete_view,),
                {
                    "__module__": self.model.__module__,
                    "model": self.model,
                    "model_admin": self,
                },
            )

        if self.changelist_view:
            opts = {
                "__module__": self.model.__module__,
                "model": self.model,
                "model_admin": self,
                "filterset_class": self.filterset_class,
                "list_display": self.list_display,
                "list_display_mobile": self.list_display_mobile,
            }
            if self.list_display_grid:
                opts["list_template_name"] = "filter-list/_table-grid-media.html"
                opts["paginate_by"] = 24
            self.changelist_view = type(
                f"{self.model.__name__}ChangelistView",
                (self.changelist_view,),
                opts,
            )

        if self.changelist_select_view != False and self.changelist_view:
            self.changelist_select_view = type(
                f"{self.model.__name__}ChangelistSelectView",
                (ChangelistSelectViewMixin, self.changelist_view),
                {},
            )

        if hasattr(self.model, "order"):
            if self.reorder_view:
                self.reorder_view = type(
                    f"{self.model.__name__}ReorderView",
                    (self.reorder_view,),
                    {
                        "__module__": self.model.__module__,
                        "model": self.model,
                        "model_admin": self,
                    },
                )
        else:
            self.reorder_view = None

        if self.preview_view:
            self.preview_view = type(
                f"{self.model.__name__}PreviewView",
                (self.preview_view,),
                {
                    "__module__": self.model.__module__,
                    "model": self.model,
                    "model_admin": self,
                },
            )
        if self.clone_view:
            self.clone_view = type(
                f"{self.model.__name__}CloneView",
                (self.clone_view,),
                {
                    "__module__": self.model.__module__,
                    "model": self.model,
                    "model_admin": self,
                },
            )

    def related_info_for(self, obj):
        from django.contrib.contenttypes.models import ContentType

        info = {}
        info["id"] = obj.id
        info["title"] = getattr(obj, "title", getattr(obj, "name", str(obj)))
        info["ctype_id"] = ContentType.objects.get_for_model(obj).id
        info["verbose_name"] = str(self.opts.verbose_name)
        info["verbose_name_plural"] = str(self.opts.verbose_name_plural)

        # If we deleted an object from its Edit panel, the panel will close
        # and attempt to redirect to the object's changelist view. This function
        # is called to gather related info about the object. However, since all we
        # have is the object's info stored in a variable, and the object
        # itself has been deleted, the following two reverse()'s will error unless
        # we check for object existence first and skip them accordingly.
        change_route = self.url_for("change")
        if change_route and obj.__class__.objects.filter(id=obj.id).exists():
            info["change_url"] = reverse(change_route, args=[obj.id])
        preview_route = self.url_for("preview")
        if preview_route and obj.__class__.objects.filter(id=obj.id).exists():
            info["preview_url"] = reverse(preview_route, args=[obj.id])

        if hasattr(obj, "get_absolute_url"):
            info["view_url"] = obj.get_absolute_url()

        if hasattr(obj, "parent_id"):
            info["parent_id"] = obj.parent_id
        if hasattr(obj, "allowed_children"):
            info["allowed_children"] = []
            for child_class in obj.allowed_children:
                info["allowed_children"].append(child_class._meta.verbose_name)
        if hasattr(obj, "width"):
            info["width"] = obj.width
        return self.modify_related_info(info, obj)

    def admin_overlay_info_for(self, obj, user=None):
        info = self.related_info_for(obj)
        overlay_info = {
            "items": [],
        }
        overlay_info["items"].append(("This", info["verbose_name"]))

        if hasattr(obj, "title"):
            overlay_info["items"].append(("Name", obj.title))
        elif hasattr(obj, "name"):
            overlay_info["items"].append(("Name", obj.name))

        if info["change_url"] and user.has_perm(self.permission_codename("change")):
            overlay_info["change_url"] = info["change_url"]
        return overlay_info

    def modify_related_info(self, info, obj):
        """Override to modify the related info for an object."""
        return info

    def url_for(self, url_name):
        if getattr(self, f"{url_name}_view", None):

            return f"{self.admin_site.name}:{self.model._meta.app_label}_{self.model._meta.model_name}_{url_name}"
        return None

    def get_add_view(self):
        return self.add_view

    def get_change_view(self):
        return self.change_view

    def get_delete_view(self):
        return self.delete_view

    def get_changelist_view(self):
        return self.changelist_view

    def get_changelist_select_view(self):
        return self.changelist_select_view

    def get_reorder_view(self):
        return self.reorder_view

    def get_preview_view(self):
        return self.preview_view

    def get_clone_view(self):
        return self.clone_view

    def get_change_action_links(self, obj):
        action_links = []
        if hasattr(obj, "get_absolute_url"):
            action_links.append(
                ActionLink(
                    text="View",
                    href=obj.get_absolute_url(),
                    panels_trigger=False,
                    attrs={"target": "_blank"},
                )
            )
        elif self.admin_site.url_for(self.model, "preview"):
            preview_url = self.admin_site.url_for(self.model, "preview")
            action_links.append(
                ActionLink(
                    text="Preview",
                    href=reverse(preview_url, args=[obj.id]),
                    reload_on=[],
                )
            )
        return action_links

    def get_add_action_links(self):
        return []

    def get_changelist_action_links(self):
        action_links = []

        add_url = self.admin_site.url_for(self.model, "add")
        if add_url:
            add_url = reverse(add_url)

            action_links.append(
                ActionLink(
                    text="Create",
                    href=add_url,
                )
            )

        reorder_url = self.admin_site.url_for(self.model, "reorder")
        if reorder_url and len(self.model.objects.all()) > 0:
            action_links.append(
                ActionLink(
                    text="Reorder",
                    href=reverse(reorder_url),
                    primary=False,
                )
            )

        return action_links

    def get_changelist_object_action_links(self, obj):
        action_links = []
        change_url = self.admin_site.url_for(obj.__class__, "change")
        if change_url:
            href = reverse(change_url, args=[obj.id])

            action_links.append(
                ActionLink(
                    text="Open",
                    href=href,
                )
            )
        preview_url = self.admin_site.url_for(self.model, "preview")
        if preview_url:
            action_links.append(
                ActionLink(
                    text="Preview",
                    reload_on=[],
                    href=reverse(preview_url, args=[obj.id]),
                )
            )
        if hasattr(obj, "get_absolute_url"):
            action_links.append(
                ActionLink(
                    text="View",
                    href=obj.get_absolute_url(),
                    panels_trigger=False,
                    attrs={"target": "_blank"},
                )
            )
        return action_links

    def get_urls(self):
        urlpatterns = []

        add_view = self.get_add_view()
        if add_view:
            add_view = self._wrap_view_with_permission(self.prepare_view(add_view), "add")
            urlpatterns.append(
                path(
                    "add/", add_view, name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_add"
                ),
            )

        change_view = self.get_change_view()
        if change_view:
            change_view = self._wrap_view_with_permission(self.prepare_view(change_view), "change")
            urlpatterns.append(
                path(
                    "<int:pk>/change/",
                    change_view,
                    name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                ),
            )

        delete_view = self.get_delete_view()
        if delete_view:
            delete_view = self._wrap_view_with_permission(self.prepare_view(delete_view), "delete")
            urlpatterns.append(
                path(
                    "<int:pk>/delete/",
                    delete_view,
                    name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_delete",
                ),
            )

        changelist_view = self.get_changelist_view()
        if changelist_view:
            changelist_view = self._wrap_view_with_permission(self.prepare_view(changelist_view), "change")
            urlpatterns.append(
                path(
                    "",
                    changelist_view,
                    name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_changelist",
                ),
            )

        changelist_select_view = self.get_changelist_select_view()
        if changelist_select_view:
            changelist_select_view = self._wrap_view_with_permission(
                self.prepare_view(changelist_select_view), "change"
            )
            urlpatterns.append(
                path(
                    "select/",
                    changelist_select_view,
                    name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_changelist_select",
                ),
            )

        reorder_view = self.get_reorder_view()
        if reorder_view:
            reorder_view = self._wrap_view_with_permission(self.prepare_view(reorder_view), "change")
            urlpatterns.append(
                path(
                    "reorder/",
                    reorder_view,
                    name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_reorder",
                ),
            )

        preview_view = self.get_preview_view()
        if preview_view:
            preview_view = self._wrap_view_with_permission(self.prepare_view(preview_view), "change")
            urlpatterns.append(
                path(
                    "<int:pk>/preview/",
                    preview_view,
                    name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_preview",
                ),
            )

        return urlpatterns

    def _wrap_view_with_permission(self, view, permission_action):
        return permission_required(self.permission_codename(permission_action), raise_exception=True)(view)

    def permission_codename(self, permission_action):
        return f"{self.opts.app_label}.{get_permission_codename(permission_action, self.opts)}"

    @property
    def urls(self):
        return self.get_urls()

    def prepare_view(self, view, **kwargs):
        """
        Converts Class-based views into view function if needed.
        """
        if isclass(view):
            return view.as_view(**kwargs)
        return view

    def log(self, *args, **kwargs):
        if self.app_log:
            log(*args, **kwargs)


def _form_class_has_model(form_class):
    if hasattr(form_class, "Meta") and hasattr(form_class.Meta, "model"):
        return True
    return False
