Application Log
===============

A Django application for logging events that happen in a Django project. It
includes the ability to create subscriptions which will notify users when a
matching log entry is created.


# Installation

Add the `app_log` app to `INSTALLED_APPS` and run `migrate`.

By default, the `SendEmailNotifier` is used for subscriptions. To use different
notifiers, configure your settings with a list of notifiers.

    APP_LOG = {
        'notifiers': [
            'app_log.notifiers.SendEmailNotifier',
            'path.to.your.CustomNotifier',
        ]
    }

Log things:

    from app_log.logger import log
    ...
    log(user, 'Updated', blog_post, f'{user.username} updated {blog_post.title}')

`log()` arguments:

- `actor`: User model | string - The user model or entity name that did the action
- `action`: string - The short name for the action completed, e.g. "Updated"
- `obj`: model instance | model class - The object that the action happened to
- `message`: string - The full message to log

# Subscriptions

Subscriptions match incoming log entries with the subscription criteria to
trigger a notification. See `models.py`.

# Notifiers

## SendEmailNotifier

Sends emails asynchronously when a log entry matches the subscriptions. The
emails are queued up in the database and can be sent with the
`app_log__send_emails` management command.

    $ ./manage.py app_log__send_emails

## Custom notifiers

Custom notifiers should inherit from `notifiers.Notifier` and must implement
the `notify()` method which takes the matching `Subscription` and `AppLogEntry`
as parameters.
