import django_filters
from django.db.models import Q
from django.db.models.functions import Length
from django.utils.translation import gettext_lazy as _

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from website.help.models import HelpItem, HelpPage


class HelpItemFilterSet(FilterSet):
    IN_USE = "in_use"
    NOT_IN_USE = "not_in_use"

    search = django_filters.CharFilter(field_name="title", lookup_expr="icontains")
    in_use = django_filters.ChoiceFilter(
        label="In use?",
        field_name="help_text",
        choices=(
            (IN_USE, "In use"),
            (NOT_IN_USE, "Not in use"),
        ),
        method="filter_in_use",
    )

    def filter_in_use(self, queryset, name, value):
        queryset = queryset.annotate(help_text_length=Length("help_text"))
        if value == self.IN_USE:
            return queryset.filter(help_text_length__gt=0)
        elif value == self.NOT_IN_USE:
            return queryset.filter(help_text_length=0)
        return queryset

    class Meta:
        fields = ["search", "in_use"]


class HelpItemAdmin(ModelAdmin):
    add_view = False
    delete_view = False
    filterset_class = HelpItemFilterSet
    form_config = {"fields": ["help_text", "link"]}

    list_display = (
        ("title", _("Title")),
        ("display_in_use", _("In use")),
    )

    def display_in_use(self, obj):
        return "Y" if len(obj.help_text) else "N"


site.register(HelpItem, HelpItemAdmin)


class HelpPageFilterSet(FilterSet):
    search = django_filters.CharFilter(method="keyword_search")
    published = django_filters.ChoiceFilter(
        field_name="published", choices=((None, "- Choose -"), (1, "Yes"), (0, "No"))
    )

    class Meta:
        fields = ["search", "topic", "published"]

    def keyword_search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(body__icontains=value))


class HelpPageAdmin(ModelAdmin):
    filterset_class = HelpPageFilterSet
    form_config = {"fields": ["title", "body", "path", "topic", "published"]}

    list_display = (
        ("title", _("Title")),
        ("topic", _("Section")),
        ("published", _("Published")),
    )


site.register(HelpPage, HelpPageAdmin)
