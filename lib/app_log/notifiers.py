from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from app_log.models import Email


def get_notifier(notifier_path):
    app_config = apps.get_app_config("app_log")
    return app_config.get_notifier(notifier_path)


class Notifier:
    display_name = None

    def notify(self, subscription, entry):
        raise NotImplementedError(
            f"Notifier `{self.__class__.__name__}` requires an implementation of the `notify` method."
        )


class SendEmailNotifier(Notifier):
    """
    Queues an email to be sent for a log entry that matches subscription
    criteria.

    Call `send_emails()` or run the `app_log__send_emails` manage command to
    actually send the queued emails.
    """

    display_name = "Email"
    subject_template_name = "app_log/send_email/subject.txt"
    body_template_name = "app_log/send_email/body.txt"
    body_html_template_name = "app_log/send_email/body.html"

    def notify(self, subscription, entry):
        owner = subscription.owner
        if not owner:
            return

        context = {
            "log_entry": entry,
            "subscription": subscription,
        }
        subject = render_to_string(self.subject_template_name, context)
        to_address = owner.email
        body = render_to_string(self.body_template_name, context)
        body_html = render_to_string(self.body_html_template_name, context)

        Email.objects.create(
            subject=subject,
            to_address=to_address,
            body=body,
            body_html=body_html,
        )

    def send_emails(self):
        emails_to_send = Email.objects.all()
        results = {
            "sent": 0,
            "not_sent": 0,
        }
        for email in emails_to_send:
            sent_successfully = send_mail(
                email.subject,
                email.body,
                settings.DEFAULT_FROM_EMAIL,
                [email.to_address],
                html_message=email.body_html,
            )
            if sent_successfully:
                results["sent"] += 1
                email.delete()
            else:
                results["not_sent"] += 1
        return results


def get_notifier_choices():
    app_config = apps.get_app_config("app_log")
    return app_config.get_notifier_choices()
