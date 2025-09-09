from django import forms

from app_log.models import AppLogEntry
from app_log.notifiers import get_notifier_choices
from ombucore.admin.forms.base import ModelFormBase
from ombucore.admin.widgets import FlatpickrDateTimeWidget


class SubscriptionForm(ModelFormBase):
    notifier = forms.ChoiceField(
        label="Delivery Method",
        choices=get_notifier_choices,
    )
    actor_name = forms.TypedChoiceField(
        label="Actor",
        choices=lambda: [(None, "(Any)")] + AppLogEntry.get_actor_choices(),
        empty_value=None,
        required=False,
    )
    action = forms.TypedChoiceField(
        label="Action",
        choices=lambda: [(None, "(Any)")] + AppLogEntry.get_action_choices(),
        empty_value=None,
        required=False,
    )
    content_type = forms.ModelChoiceField(
        label="Object",
        queryset=AppLogEntry.get_content_type_choices_queryset(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["actor_name"].widget.choices = [(None, "(Any)")] + AppLogEntry.get_actor_choices()
        self.fields["action"].widget.choices = [(None, "(Any)")] + AppLogEntry.get_action_choices()
        self.fields["content_type"].widget.choices = [(None, "(Any)")] + AppLogEntry.get_action_choices()

    def save(self, commit=True):
        self.instance.owner = self.user
        return super().save(commit=commit)

    class Meta:
        fields = [
            "notifier",
            "message_keywords",
            "actor_name",
            "action",
            "content_type",
            "timestamp_start",
            "timestamp_end",
        ]
        labels = {
            "message_keywords": "Message Contains",
            "timestamp_start": "After time",
            "timestamp_end": "Before time",
        }
        widgets = {
            "timestamp_start": FlatpickrDateTimeWidget(options={}),
            "timestamp_end": FlatpickrDateTimeWidget(options={}),
        }
