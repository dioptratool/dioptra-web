import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from ombucore.admin.views import AddView, ChangeView, DeleteView
from website.models import AccountCodeDescription


class AccountCodeDescriptionDeleteView(DeleteView):
    success_message = "Account code description for <strong>%(title)s</strong> was successfully deleted."


class AccountCodeDescriptionAddView(AddView):
    success_message = "Account code description for <strong>%(title)s</strong> was successfully created."


class AccountCodeDescriptionChangeView(ChangeView):
    success_message = "Account code description for <strong>%(title)s</strong> was successfully updated."


class AccountCodeDescriptionFilterSet(FilterSet):
    search = django_filters.CharFilter(method="keyword_search")

    order_by = django_filters.OrderingFilter(
        choices=(
            ("account_code", _("Account Code (A-Z)")),
            ("-account_code", _("Account Code (Z-A)")),
        ),
        empty_label=None,
    )

    def keyword_search(self, queryset, name, value):
        return queryset.filter(Q(account_code__icontains=value) | Q(account_description__icontains=value))

    class Meta:
        fields = [
            "search",
        ]


class AccountCodeDescriptionAdmin(ModelAdmin):
    filterset_class = AccountCodeDescriptionFilterSet
    list_display = (
        ("account_code", _("Account Code")),
        ("account_description", _("Description")),
        ("sensitive_data", _("Sensitive Data?")),
    )

    delete_view = AccountCodeDescriptionDeleteView
    add_view = AccountCodeDescriptionAddView
    change_view = AccountCodeDescriptionChangeView


site.register(AccountCodeDescription, AccountCodeDescriptionAdmin)
