import datetime
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django_otp.oath import hotp
from django_otp.plugins.otp_hotp.models import HOTPDevice

logger = logging.getLogger(__name__)


class HOTPEmailDevice(HOTPDevice):
    token_creation_datetime = models.DateTimeField(auto_now=True)
    token_validity_time = models.IntegerField(
        default=60 * 60, help_text="Number of seconds token is valid for."
    )

    def verify_token(self, token):
        token_expired = (
            datetime.datetime.now(datetime.UTC) - self.token_creation_datetime
        ).total_seconds() > self.token_validity_time
        verified = super().verify_token(token)
        return verified and not token_expired

    def generate_challenge(self):
        self.counter += 1
        token = hotp(self.bin_key, self.counter)
        self.save()
        text = render_to_string("email/token.txt", {"token": token, "domain": settings.DOMAIN})
        html = render_to_string("email/token.html", {"token": token, "domain": settings.DOMAIN})
        subject = f"Account notification: Verification code: {token:06d}"
        from_email = settings.DEFAULT_FROM_EMAIL

        send_mail(
            subject,
            message=text,
            html_message=html,
            from_email=from_email,
            recipient_list=[self.user.email],
        )

        message = "sent by email"
        logger.debug(f"Your 2FA code is: {token:06d}")

        return message
