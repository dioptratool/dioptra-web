import django_filters
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ombucore.admin import panel_commands as commands
from ombucore.admin.actionlink import ActionLink
from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import FormView
from website import models as website_models
from website.admin.core import ProtectedDeleteView
from website.forms.category import CategorySetDefaultForm


class CategoryFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
    )

    class Meta:
        fields = [
            "search",
        ]


class CategoryAdmin(ModelAdmin):
    filterset_class = CategoryFilterSet
    form_config = {
        "fields": ["name", "description", "help_text"],
    }

    list_display = (("name_with_default", _("Name")),)

    delete_view = ProtectedDeleteView

    def name_with_default(self, obj):
        name = obj.name
        if obj.default:
            name += " (Default)"
        return name

    def get_changelist_action_links(self):
        action_links = super().get_changelist_action_links()
        action_links.append(
            ActionLink(
                text=_("Set Default"),
                href=reverse("category-set-default"),
            )
        )
        return action_links


site.register(website_models.Category, CategoryAdmin)


class CategorySetDefaultView(PermissionRequiredMixin, FormView):
    supertitle = "Set"
    title = "Default Category"
    success_message = "Updated default category."
    log_action = "Set"
    template_name = "panel-form.html"
    form_class = CategorySetDefaultForm
    permission_required = "website.change_category"

    def get_success_commands(self):
        return [
            commands.Resolve(
                {
                    "operation": "saved",
                }
            )
        ]

    def form_valid(self, form):
        defaultID = form.cleaned_data.get("category").pk
        if defaultID:
            categoryObj = website_models.Category.objects.get(pk=defaultID)
            if categoryObj:
                categoryObj.default = True
                categoryObj.save()

        return super().form_valid(form)
