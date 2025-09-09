import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q

from app_log.models import AppLogEntry, Subscription
from app_log.notifiers import get_notifier


def log(actor=None, action=None, obj=None, message=None):
    """
    Logs an action.

    :param actor: The user or entity that did the action
    :param action: The short name for the action completed, e.g. "Updated"
    :param obj: The object that the action happened to
    :param message: The full message to log
    :type actor: User model or string
    :type action: string
    :type obj: Model instance or Model class
    :type message: string
    """
    try:
        entry = create_entry(actor=actor, action=action, obj=obj, message=message)
        entry = notify_of_log_entry(entry)
        return entry
    except Exception as e:
        if settings.DEBUG:
            # Re-raise if DEBUG.
            raise
        else:
            # Otherwise log the error with Python.
            logging.exception("Error creating app_log entry")


def create_entry(actor=None, action=None, obj=None, message=None, **kwargs):
    """
    Creates a log entry.

    `actor` can be either a string or a user model instance.
    """
    actor_name = None
    actor_user = None
    if isinstance(actor, str):
        actor_name = actor
        actor_user = None
    elif isinstance(actor, get_user_model()):
        actor_name = str(actor)
        actor_user = actor

    create_kwargs = {
        "actor_user": actor_user,
        "actor_name": actor_name,
        "action": action,
        "message": message,
    }

    if obj:
        if isinstance(obj, models.Model):
            # obj is a model instance.
            create_kwargs["obj"] = obj
        elif isinstance(obj, type):
            # obj is a class, try to wire up the content type:
            create_kwargs["content_type"] = ContentType.objects.get_for_model(obj)

    entry = AppLogEntry.objects.create(**create_kwargs)
    return entry


def notify_of_log_entry(entry):
    subscriptions = get_subscriptions_for_entry(entry)
    for subscription in subscriptions:
        notifier = get_notifier(subscription.notifier)
        if notifier:
            notifier.notify(subscription, entry)
    return entry


def get_subscriptions_for_entry(entry):
    """
    Returns a list of Subscription objects that match the given entry.
    """
    timestamp_start_query = Q(timestamp_start__isnull=True) | Q(timestamp_start__lt=entry.timestamp)

    timestamp_end_query = Q(timestamp_end__isnull=True) | Q(timestamp_end__gt=entry.timestamp)

    actor_name_query = Q(actor_name__isnull=True) | Q(actor_name=entry.actor_name)

    action_query = Q(action__isnull=True) | Q(action=entry.action)

    content_type_query = Q(content_type__isnull=True) | Q(content_type=entry.content_type)

    subscriptions = Subscription.objects.filter(
        timestamp_start_query,
        timestamp_end_query,
        actor_name_query,
        action_query,
        content_type_query,
    )

    subscriptions = filter(make_message_keywords_filter_fn(entry.message), subscriptions)

    return list(subscriptions)


def make_message_keywords_filter_fn(message):
    """
    Returns a function to use with `filter()` that captures the message to
    search in the function scope.
    """

    def filter_fn(subscription):
        if message and subscription.message_keywords:
            return subscription.message_keywords.lower() in message.lower()
        elif subscription.message_keywords and not message:
            return False
        else:
            return True

    return filter_fn
