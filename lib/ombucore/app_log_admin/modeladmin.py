import django_filters
from django import forms
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.timezone import localtime

from app_log.logger import get_notifier
from app_log.models import AppLogEntry, Subscription
from ombucore.admin import panel_commands as commands
from ombucore.admin.actionlink import ActionLink
from ombucore.admin.buttons import CancelButton, SubmitButton
from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.views import AddView, ChangeView, ChangelistView
from ombucore.admin.widgets import FlatpickrDateTimeWidget
from ombucore.app_log_admin.forms import SubscriptionForm


class AppLogEntryFilterSet(FilterSet):
    search = django_filters.CharFilter(method="keyword_search")

    def keyword_search(self, queryset, name, value):
        return queryset.filter(Q(message__icontains=value) | Q(actor_name__icontains=value))

    actor_name = django_filters.AllValuesFilter(
        label="Actor",
        field_name="actor_name",
        lookup_expr="exact",
        widget=forms.Select,
    )
    action = django_filters.AllValuesFilter(
        label="Action",
        field_name="action",
        lookup_expr="exact",
        widget=forms.Select,
    )
    content_type = django_filters.ModelChoiceFilter(
        label="Object",
        field_name="content_type",
        queryset=AppLogEntry.get_content_type_choices_queryset(),
        widget=forms.Select,
    )
    timestamp_start = django_filters.DateTimeFilter(
        label="After Time",
        widget=FlatpickrDateTimeWidget(
            options={
                "inline": True,
            },
        ),
        field_name="timestamp",
        lookup_expr="gt",
    )
    timestamp_end = django_filters.DateTimeFilter(
        label="Before Time",
        widget=FlatpickrDateTimeWidget(
            options={
                "inline": True,
            },
        ),
        field_name="timestamp",
        lookup_expr="lt",
    )

    order_by = django_filters.OrderingFilter(
        choices=(
            ("-timestamp", "Newest first"),
            ("timestamp", "Oldest first"),
        ),
        empty_label=None,
    )

    class Meta:
        fields = [
            "search",
            "actor_name",
            "action",
            "content_type",
            "timestamp_start",
            "timestamp_end",
        ]


class AppLogEntryChangelistView(ChangelistView):
    paginate_by = 80

    def get_panel_action_links(self):
        action_links = []

        if self.filters_applied():
            subscription_add_route = self.model_admin.admin_site.url_for(Subscription, "add")
            query_string = self.get_subscription_add_query_string()
            subscription_add_url = f"{reverse(subscription_add_route)}?{query_string}"
            action_links.append(
                ActionLink(
                    text="Create Subscription",
                    href=subscription_add_url,
                )
            )

        if Subscription.objects.filter(owner=self.request.user).count() > 0:
            action_links.append(
                ActionLink(
                    text="Manage Your Subscriptions",
                    href=reverse(self.model_admin.admin_site.url_for(Subscription, "changelist")),
                )
            )

        return action_links

    def filters_applied(self):
        filterset = self.filterset
        self.filterset.is_valid()  # Triggers form cleaning.
        if hasattr(self.filterset.form, "cleaned_data"):
            for field_name, field_value in self.filterset.form.cleaned_data.items():
                if field_name != "order_by" and field_value:
                    return True
        return False

    def get_subscription_add_query_string(self):
        """
        Mostly just urlencodes the GET QueryDict.

        Replaces `search` key with `message_keywords` so the subscription form
        picks it up.
        """
        query = self.request.GET.dict()
        if "search" in query:
            query["message_keywords"] = query["search"]
            del query["search"]
        query_string = urlencode(query)
        return query_string


class AppLogEntryModelAdmin(ModelAdmin):
    filterset_class = AppLogEntryFilterSet
    form_config = None
    add_view = False
    change_view = False
    delete_view = False
    changelist_view = AppLogEntryChangelistView
    changelist_select_view = False

    list_display = (
        ("actor_name", "Actor"),
        ("action", "Action"),
        ("display_object", "Object"),
        ("message", "Message Detail"),
        ("display_timestamp", "Timestamp"),
    )

    def display_timestamp(self, log_entry):
        return format_timestamp(log_entry.timestamp)

    def display_object(self, log_entry):
        if log_entry.content_type:
            out = log_entry.content_type.model_class()._meta.verbose_name.title()
            if log_entry.obj:
                try:
                    obj_info = self.admin_site.related_info_for(log_entry.obj)
                    object_name = obj_info["title"]
                except Exception:
                    object_name = str(log_entry.obj)
                object_url = self.get_object_url(log_entry.obj)
                if object_url:
                    object_name = format_html('<a href="{}">{}</a>', object_url, object_name)
                out = format_html(
                    "{content_type}: {object_name}",
                    content_type=out,
                    object_name=object_name,
                )
            return out
        return None

    def get_object_url(self, obj):
        """
        A hook to allow modeladmin implementations to link to specific model
        instances.

        Return the desired URL to the object or `None` to not include a link.
        """
        return None


class SubscriptionFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="message_keywords",
        lookup_expr="icontains",
        help_text="",
    )
    content_type = django_filters.ModelChoiceFilter(
        label="Object",
        field_name="content_type",
        queryset=AppLogEntry.get_content_type_choices_queryset(),
        widget=forms.Select,
    )
    action = django_filters.ChoiceFilter(
        label="Action",
        field_name="action",
        lookup_expr="exact",
        choices=AppLogEntry.get_action_choices,
        widget=forms.Select,
    )
    actor = django_filters.ChoiceFilter(
        label="Actor",
        field_name="actor_name",
        lookup_expr="exact",
        choices=AppLogEntry.get_actor_choices,
        widget=forms.Select,
    )

    class Meta:
        fields = ["content_type", "action", "actor"]


class SubscriptionChangelistView(ChangelistView):
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(owner=self.request.user)
        return queryset

    def get_panel_action_links(self):
        return []


class SubscriptionAddView(AddView):
    success_message = "<strong>Subscription</strong> successfully created."

    def get_initial(self):
        """
        Load initial vaues from the query string.
        """
        return self.request.GET.dict()

    def get_buttons(self):
        buttons = [
            SubmitButton(
                text="Save",
                style="primary",
                disable_when_form_unchanged=False,
                align="left",
            ),
            CancelButton(
                align="left",
            ),
        ]
        return buttons

    def get_success_commands(self):
        changelist_route = self.model_admin.url_for("changelist")
        return [commands.Redirect(reverse(changelist_route))]


class SubscriptionChangeView(ChangeView):
    success_message = "<strong>Subscription</strong> updated."

    def get_supertitle(self):
        return "Edit"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.owner != self.request.user:
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get_success_commands(self):
        changelist_route = self.model_admin.url_for("changelist")
        return [commands.CloseCurrentAndRedirectOpener(reverse(changelist_route))]


class SubscriptionModelAdmin(ModelAdmin):
    filterset_class = SubscriptionFilterSet
    form_class = SubscriptionForm
    add_view = SubscriptionAddView
    change_view = SubscriptionChangeView
    changelist_view = SubscriptionChangelistView
    changelist_select_view = False

    list_display = (
        ("display_notifier", "Delivery"),
        ("actor_name", "Actor"),
        ("action", "Action"),
        ("content_type", "Object"),
        ("message_keywords", "Message Contains"),
        ("display_timestamp_start", "After Time"),
        ("display_timestamp_end", "Before Time"),
    )

    def display_timestamp_start(self, subscription):
        if subscription.timestamp_start:
            return format_timestamp(subscription.timestamp_start)
        return None

    def display_timestamp_end(self, subscription):
        if subscription.timestamp_end:
            return format_timestamp(subscription.timestamp_end)
        return None

    def display_notifier(self, subscription):
        notifier = get_notifier(subscription.notifier)
        return notifier.display_name


def format_timestamp(timestamp):
    return f"{localtime(value=timestamp):%d-%b-%Y, %I:%M %p %Z}"
