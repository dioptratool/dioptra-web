from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from app_log.logger import log


def get_username(user):
    return getattr(user, user.USERNAME_FIELD)


@receiver(user_logged_in)
def user_logged_in_callback(sender, **kwargs):
    user = kwargs.get("user")
    log("System", "Logged In", user, f"{get_username(user)} logged in.")


@receiver(user_logged_out)
def user_logged_out_callback(sender, **kwargs):
    user = kwargs.get("user")
    log("System", "Logged Out", user, f"{get_username(user)} logged out.")


@receiver(user_login_failed)
def user_login_failed_callback(sender, **kwargs):
    sanitized_credentials = kwargs.get("credentials")
    credentials_string = str(sanitized_credentials)
    User = get_user_model()
    log("System", "Login Failed", User, f"Login failed for {credentials_string}.")
