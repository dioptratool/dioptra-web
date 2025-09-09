from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone


class AppLogEntry(models.Model):
    timestamp = models.DateTimeField(default=timezone.now)
    actor_user = models.ForeignKey(
        getattr(settings, "AUTH_USER_MODEL", "auth.User"),
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    actor_name = models.CharField(max_length=255)  # A backup in case user is deleted.
    action = models.CharField(max_length=255)
    message = models.TextField(null=True)
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    object_id = models.PositiveIntegerField(null=True)
    obj = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Log Entry"
        verbose_name_plural = "Log Entries"

    @property
    def content_type_name(self):
        return self.content_type.model_class()._meta.verbose_name.title() if self.content_type else ""

    @property
    def link(self):
        return self._get_log_entry_link()

    def _get_log_entry_link(self):
        if (
            self.obj
            and getattr(self.obj, "pk", None)
            and hasattr(self.obj, "app_log_entry_link_name")
            and self.obj.app_log_entry_link_name is not None
        ):
            try:
                return reverse(self.obj.app_log_entry_link_name, args=[self.obj.pk])
            except:
                return None

    @classmethod
    def get_content_type_choices_queryset(cls):
        content_type_pks_used = AppLogEntry.objects.values_list("content_type", flat=True).distinct()
        return ContentType.objects.filter(pk__in=content_type_pks_used)

    @classmethod
    def get_action_choices(cls):
        choices = list(AppLogEntry.objects.order_by("action").values_list("action", flat=True).distinct())
        return list(zip(choices, choices))

    @classmethod
    def get_actor_choices(cls):
        choices = list(
            AppLogEntry.objects.order_by("actor_name").values_list("actor_name", flat=True).distinct()
        )
        return list(zip(choices, choices))


class Subscription(models.Model):
    owner = models.ForeignKey(
        getattr(settings, "AUTH_USER_MODEL", "auth.User"),
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    timestamp_start = models.DateTimeField(null=True, blank=True)
    timestamp_end = models.DateTimeField(null=True, blank=True)
    actor_name = models.CharField(max_length=255, null=True, blank=True)
    action = models.CharField(max_length=255, null=True, blank=True)
    message_keywords = models.CharField(max_length=255, null=True, blank=True)
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notifier = models.CharField(max_length=255)
    notifier_config = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return "App Log Subscription"

    def __repr__(self):
        return "<{}: {} object ({})>".format(
            self.__class__.__name__,
            self.__class__.__name__,
            self.pk,
        )

    def get_notifier(self, notifier_path):
        app_config = apps.get_app_config("app_log")
        return app_config.get_notifier(notifier_path)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "App Log Subscription"
        verbose_name_plural = "App Log Subscriptions"


class Email(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    subject = models.CharField(max_length=255)
    to_address = models.CharField(max_length=255)
    body = models.TextField()
    body_html = models.TextField(null=True)

    class Meta:
        ordering = ["created_at"]
