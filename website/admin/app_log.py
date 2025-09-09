from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.forms import Form
from django.urls import reverse
from django.utils.html import format_html

from app_log.models import AppLogEntry, Subscription
from ombucore.admin.sites import site
from ombucore.admin.views import FormView
from ombucore.app_log_admin import modeladmin
from ombucore.app_log_admin.modeladmin import SubscriptionModelAdmin
from ombucore.assets.models import DocumentAsset, ImageAsset
from website.models import (
    Analysis,
    CostType,
    CostTypeCategoryMapping,
    Country,
    InsightComparisonData,
    Intervention,
    Region,
)

User = get_user_model()


class AppLogEntryModelAdmin(modeladmin.AppLogEntryModelAdmin):
    def display_object(self, log_entry):
        if log_entry.content_type:
            if log_entry.content_type.model_class() is None:
                out = "Unknown"
            else:
                out = log_entry.content_type.model_class()._meta.verbose_name.title()
                if log_entry.obj:
                    object_url = self.get_object_url(log_entry.obj)
                    if object_url:
                        if object_url.startswith("/panels/"):
                            out = format_html('<a href="{}" data-panels-trigger>{}</a>', object_url, out)
                        else:
                            out = format_html('<a href="{}" target="_blank">{}</a>', object_url, out)
            return out
        return None

    def get_object_url(self, obj):
        if getattr(obj, "app_log_entry_link_name", None):
            return reverse(obj.app_log_entry_link_name, kwargs={"pk": obj.pk})

        if isinstance(obj, CostTypeCategoryMapping):
            return reverse(
                "ombucore.admin:website_costtypecategorymapping_change",
                kwargs={"pk": obj.pk},
            )

        if isinstance(obj, CostType):
            return reverse("ombucore.admin:website_costtype_change", kwargs={"pk": obj.pk})

        if isinstance(obj, Country):
            return reverse("ombucore.admin:website_country_change", kwargs={"pk": obj.pk})

        if isinstance(obj, Region):
            return reverse("ombucore.admin:website_region_change", kwargs={"pk": obj.pk})

        if isinstance(obj, InsightComparisonData):
            return reverse(
                "ombucore.admin:website_insightcomparisondata_change",
                kwargs={"pk": obj.pk},
            )

        if isinstance(obj, InsightComparisonData):
            return reverse(
                "ombucore.admin:website_insightcomparisondata_change",
                kwargs={"pk": obj.pk},
            )

        if isinstance(obj, Intervention):
            return reverse("ombucore.admin:website_intervention_change", kwargs={"pk": obj.pk})

        if isinstance(obj, Analysis):
            return reverse("analysis", kwargs={"pk": obj.pk})

        if isinstance(obj, User):
            return reverse("ombucore.admin:users_user_change", kwargs={"pk": obj.pk})

        if isinstance(obj, ImageAsset):
            return reverse("ombucore.admin:assets_imageasset_change", kwargs={"pk": obj.pk})

        if isinstance(obj, DocumentAsset):
            return reverse("ombucore.admin:assets_documentasset_change", kwargs={"pk": obj.pk})


site.register(AppLogEntry, AppLogEntryModelAdmin)
site.register(Subscription, SubscriptionModelAdmin)


class SendPendingNotificationsForm(Form):
    pass


class SendPendingNotificationsView(FormView):
    title = None
    supertitle = "Sending pending subscription notifications"
    template_name = "panel-form-send-notifications.html"
    success_message = "Notifications have been sent."
    form_class = SendPendingNotificationsForm

    def form_valid(self, form):
        response = super().form_valid(form)
        call_command("app_log__send_emails")
        return response
