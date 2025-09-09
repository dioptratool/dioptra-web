import inspect
import os

from django.contrib.admin.sites import AlreadyRegistered, NotRegistered
from django.core.exceptions import ImproperlyConfigured
from django.urls import include, path, re_path
from django.urls import reverse
from django.views.generic.base import TemplateView


class AdminCentralBaseView(TemplateView):
    """
    This is a default model list. Subclass ombucore.admin.sites.AdminCentralBaseView and
    register the class with the admin site to overwrite.
    """

    template_name = "admin-central.html"
    groups = None
    admin_site = None
    title = "Admin Central"

    def __init__(self, admin_site=None):
        if admin_site:
            self.admin_site = admin_site

    def get_context_data(self, **kwargs):
        # There is also a prefix_copy context variable that will place help text
        # at the top of admin central
        context = super().get_context_data(**kwargs)
        groups = self.get_groups()
        context["title"] = self.title
        context["groups"] = self._prepare_groups(groups)
        return context

    def get_groups(self):
        model_groups = self.get_default_groups()
        action_group = self.get_action_group()
        return model_groups + action_group

    def get_default_groups(self):
        """
        Return a dict of 'groups', i.e. apps + their models as displayed on the admin panel. For example,
        ImageAsset and VideoAsset from the 'asset' app, when registered with our admin, might return a
        group that looks like...

        [
            {
                'title': 'Assets',
                'items': [
                    {
                        'title': 'Video assets',
                        'links': [
                            {
                                {'url': reverse('manage-video-assets'), 'perm': 'assets.change_video', 'title': 'Manage'}
                            }
                        ]
                    },
                    {
                        'title': 'Image assets',
                        'links': [
                            {
                                {'url': reverse('manage-image-assets'), 'perm': 'assets.change_image', 'title': 'Manage'}
                            }
                        ]
                    }
                ]
            }
        ]
        """

        def modeladmin_tuple_to_group(arg_tuple):
            app_label, modeladmins = arg_tuple
            return {
                "title": app_label,
                "items": list(map(modeladmin_to_items, list(filter(not_add_only, modeladmins)))),
            }

        def not_add_only(modeladmin):
            return not self.admin_site.is_add_only(modeladmin.model)

        def modeladmin_to_items(modeladmin):
            return {
                "title": modeladmin.model._meta.verbose_name_plural,
                "links": modeladmin_to_manage_links(modeladmin),
            }

        def modeladmin_to_manage_links(modeladmin):
            return [
                {
                    "title": "Manage",
                    "url": reverse(
                        f"ombucore.admin:{modeladmin.model._meta.app_label}_{modeladmin.model._meta.model_name}_changelist"
                    ),
                    "perm": modeladmin.permission_codename("change"),
                }
            ]

        model_groups = list(
            map(
                modeladmin_tuple_to_group,
                iter(self.admin_site.modeladmins_by_app().items()),
            )
        )

        model_groups += [
            {
                "title": "System Information",
                "items": [
                    {
                        "title": "Application Version",
                        "description": self._get_application_version(),
                        "nolinks": True,
                    },
                ],
            },
        ]

        return model_groups

    def get_action_group(self):
        """
        Similar to get_default_groups(), but we're reaching into the 'actions' app to get all non-model-based
        actions. i.e. Things we want on the admin panel that aren't backed up by actual db models.

        This just makes a group called "Actions" and dipslays the actions there.
        """
        action_group = [{"title": "Actions", "items": []}]
        for action_name, action in self.admin_site._action_registry.items():
            action_group[0]["items"].append(
                {
                    "title": action_name,
                    "links": [
                        {
                            "title": action.link_text,
                            "url": reverse(f"ombucore.admin:{action.url}"),
                            "perm": action.perm,
                        },
                    ],
                },
            )
        return action_group

    def _prepare_groups(self, groups):
        def group_is_empty(group):
            return len(group["items"]) > 0

        def user_has_link_perm(link):
            return self.request.user.has_perm(link["perm"])

        def item_is_empty(group):
            return "nolinks" in group or len(group["links"]) > 0

        for group in groups:
            for item in group["items"]:
                if "links" in item:
                    item["links"] = list(filter(user_has_link_perm, item["links"]))
            group["items"] = list(filter(item_is_empty, group["items"]))
        groups = list(filter(group_is_empty, groups))
        return groups

    def _get_application_version(self):
        return os.getenv("APPLICATION_VERSION", "Not Available")


class AdminSite:
    admin_central_view = AdminCentralBaseView

    def __init__(self, name="ombucore.admin"):
        self._registry = {}
        self._action_registry = {}
        self.name = name

    def register(self, model, admin_class, **options):
        if model._meta.abstract:
            raise ImproperlyConfigured(
                f"The model {model.__name__} is abstract, so it cannot be registered with ombucore.admin."
            )
        if model in self._registry:
            raise AlreadyRegistered(f"The model {model.__name__} is already registered")

        options["model"] = model
        admin_class = type(f"{model.__name__}Admin", (admin_class,), options)

        admin_obj = admin_class(model, self)
        self._registry[model] = admin_obj

    def unregister(self, model):
        if model not in self._registry:
            raise NotRegistered(f"The model {model.__name__} is not registered")
        del self._registry[model]

    def is_registered(self, model):
        return model in self._registry

    def is_add_only(self, model):
        changelist_view = self._registry[model].changelist_view
        return changelist_view in (None, False)

    # Keep track of non-model-based admin elements, like the "send test email" button
    def register_action(self, action):
        self._action_registry[action.name] = action

    def action_is_registered(self, action):
        return action.name in self._action_registry

    def unregister_action(self, action):
        if action.name not in self._action_registry:
            raise NotRegistered(f"This {action.name} action is not registered")
        del self._action_registry[action.name]

    # Generate URLs for all model-based elements; Record URLs for all non-model-based elements;
    def get_urls(self):
        def admin_central(request, *args, **kwargs):
            return self.admin_central_view.as_view(admin_site=self)(request, *args, **kwargs)

        urlpatterns = [path("admin-central/", admin_central, name="admin_central")]

        for model, model_admin in list(self._registry.items()):
            if model_admin.urls:
                urlpatterns += [
                    re_path(
                        rf"^{model._meta.app_label}/{model._meta.model_name}/",
                        include(model_admin.urls),
                    ),
                ]

        for action_name, action in self._action_registry.items():
            urlpatterns += [re_path(rf"^{action.url}/", action.view.as_view(), name=action.url)]

        return urlpatterns

    @property
    def urls(self):
        return self.get_urls(), "ombucore.admin", self.name

    def url_for(self, model_instance_or_class, url_name):
        """
        Accepts either a model class or instance.
        """
        if inspect.isclass(model_instance_or_class):
            model_class = model_instance_or_class
        else:
            model_class = type(model_instance_or_class)

        if not self.is_registered(model_class):
            raise ImproperlyConfigured(f"{model_class} is not registered with the panels admin.")
        return self._registry[model_class].url_for(url_name)

    def related_info_for(self, obj):
        model_class = type(obj)
        if not self.is_registered(model_class):
            raise ImproperlyConfigured(f"{model_class} is not registered with the panels admin.")
        admin_obj = self._registry[model_class]
        return admin_obj.related_info_for(obj)

    def admin_overlay_info_for(self, obj, user=None):
        model_class = type(obj)
        if not self.is_registered(model_class):
            return None
        admin_obj = self._registry[model_class]
        return admin_obj.admin_overlay_info_for(obj, user)

    def register_admin_central_view(self, admin_central_view):
        self.admin_central_view = admin_central_view

    def modeladmins_by_app(self):
        by_app = {}
        for modeladmin in self._registry.values():
            app_label = modeladmin.model._meta.app_label
            if not app_label in by_app:
                by_app[app_label] = []
            by_app[app_label].append(modeladmin)
        return by_app


site = AdminSite()
