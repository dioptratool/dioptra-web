import django_filters
from django.utils.translation import gettext_lazy as _

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import AddView, ChangeView
from website.forms.intervention import InterventionForm
from website.intervention_metadata import MetadataDraftError
from website.models import Intervention, InterventionGroup


class InterventionFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
    )

    class Meta:
        fields = [
            "search",
        ]


class MetadataDraftErrorMixin:
    """
    A metadata persistence conflict rolls the whole save back; show it on the Metadata tab with
    the draft intact instead of a server error.
    """

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except MetadataDraftError as error:
            form.add_error("metadata_draft", str(error))
            return self.form_invalid(form)


class InterventionAddView(MetadataDraftErrorMixin, AddView):
    pass


class InterventionChangeView(MetadataDraftErrorMixin, ChangeView):
    pass


class InterventionAdmin(ModelAdmin):
    filterset_class = InterventionFilterSet
    form_class = InterventionForm
    add_view = InterventionAddView
    change_view = InterventionChangeView
    list_display = (("name", _("Name")),)


site.register(Intervention, InterventionAdmin)


class InterventionGroupFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
    )

    class Meta:
        fields = [
            "search",
        ]


class InterventionGroupAdmin(ModelAdmin):
    filterset_class = InterventionGroupFilterSet
    list_display = (("name", _("Name")),)


site.register(InterventionGroup, InterventionGroupAdmin)
