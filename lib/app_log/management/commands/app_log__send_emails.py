from django.core.management.base import BaseCommand

from app_log.notifiers import SendEmailNotifier


class Command(BaseCommand):
    help = "Sends any emails queued for sending by SendEmailNotifier."

    def handle(self, *args, **kwargs):
        notifier = SendEmailNotifier()
        result = notifier.send_emails()
        if result["sent"] > 0:
            self.stdout.write(self.style.SUCCESS(f"Emails sent: {result['sent']}"))
        if result["not_sent"] > 0:
            self.stdout.write(self.style.ERROR(f"Emails failed to send: {result['not_sent']}"))
        if result["sent"] == result["not_sent"] == 0:
            self.stdout.write(self.style.SUCCESS("No emails to send."))
