import django_filters
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.functions import Collate

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin import ModelAdmin
from ombucore.admin.sites import site
from website.models import Country
from website.users.forms import AdminEditUserForm
from website.users.views import UserChangeView


class UserFilterSet(FilterSet):
    search = django_filters.CharFilter(
        method="search_users",
        help_text="",
    )

    primary_countries = django_filters.ModelChoiceFilter(
        queryset=Country.objects.all(),
    )

    secondary_countries = django_filters.ModelChoiceFilter(
        label="Secondary Country",
        queryset=Country.objects.all(),
    )

    role = django_filters.ChoiceFilter(
        label="Application Role",
        field_name="role",
        choices=lambda: get_user_model().ROLE_CHOICES,
    )

    order_by = django_filters.OrderingFilter(
        choices=(
            ("-last_login", "Last Login (oldest first)"),
            ("last_login", "Last Login (recent first)"),
        ),
        empty_label=None,
    )

    def search_users(self, queryset, name, value):
        return queryset.annotate(
            email_deterministic=Collate("email", "und-x-icu"),
            name_deterministic=Collate("name", "und-x-icu"),
        ).filter(Q(name_deterministic__icontains=value) | Q(email_deterministic__icontains=value))

    class Meta:
        fields = [
            "search",
            "primary_countries",
            "secondary_countries",
            "role",
        ]
        model = get_user_model()


class UserAdmin(ModelAdmin):
    filterset_class = UserFilterSet
    add_form_class = AdminEditUserForm
    change_form_config = {}  # Form handled in the change view.
    change_view = UserChangeView
    list_display = (
        ("name", "Name"),
        ("display_role", "Application Role"),
        ("display_primary_countries", "Primary Countries"),
        ("last_login", "Last Login"),
    )

    def display_role(self, obj):
        User = get_user_model()
        return dict(User.ROLE_CHOICES).get(obj.role, None)

    def display_primary_countries(self, obj):
        try:
            countries = [country.name for country in obj.primary_countries.all()]
            countries_sorted = sorted(countries)
            if countries:
                countries_joined = ",".join(countries_sorted).replace(",", ", ")
            else:
                countries_joined = None
            return countries_joined
        except Exception:
            return None


site.register(get_user_model(), UserAdmin)
