from allauth.account.forms import EmailAwarePasswordResetTokenGenerator
from allauth.account.utils import user_pk_to_url_str
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.urls import reverse

from website.email_2fa.models import HOTPEmailDevice

User = get_user_model()


@receiver(post_save, sender=User)
def send_initial_email(sender, instance, created, **kwargs):
    if hasattr(instance, "created_by_social_login"):
        return
    if created:
        token_generator = EmailAwarePasswordResetTokenGenerator()
        temp_key = token_generator.make_token(instance)

        # send the password reset email
        path = reverse(
            "account_reset_password_from_key",
            kwargs=dict(uidb36=user_pk_to_url_str(instance), key=temp_key),
        )

        url = f"https://{settings.DOMAIN}{path}"

        context = {
            "user": instance,
            "password_reset_url": url,
        }

        msg = render_to_string("email/set-password.html", context=context)
        html_msg = render_to_string("email/set-password.html", context=context)

        send_mail(
            subject="Action needed: Set your Dioptra password",
            message=msg,
            html_message=html_msg,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
        )


@receiver(post_save, sender=User)
def add_email_2fa(sender, instance, created, **kwargs):
    """
    All users have emails and so we are able to add the Email 2FA to them immediately
    """
    if created:
        HOTPEmailDevice.objects.create(user=instance, confirmed=True)
