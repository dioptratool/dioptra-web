import logging
from typing import Any

import structlog
from allauth.account.utils import user_email, user_field, valid_email_or_none
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

from website.email_2fa.adapter import OTPAdapter

User = get_user_model()

logger = structlog.get_logger(__name__)


class AccountAdapter(OTPAdapter):
    def is_open_for_signup(self, request: HttpRequest):
        # Regular Django user signups are disabled for this app.  Only SSO or admin created users are allowed.
        #  You can still create admin users using the cli or the admin interface.
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        user.created_by_social_login = True
        # This is a temporary object property that we use in signals.py to
        # prevent emails being sent out on initial user setup
        if user.id:
            return
        if not user.email:
            return

        try:
            user = User.objects.get(
                email=user.email
            )  # if user exists, connect the account to the existing account and login
            sociallogin.connect(request, user)
        except User.DoesNotExist:
            pass

    def is_open_for_signup(self, request: HttpRequest, sociallogin: Any):
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", False)

    def populate_user(self, request, sociallogin, data):
        """
        Hook that can be used to further populate the user instance.

        Note that the user instance being populated represents a
        suggested User instance that represents the social user that is
        in the process of being logged in.

        The User instance need not be completely valid and conflict
        free. For example, verifying whether or not the username
        already exists, is not a responsibility.
        """
        email = data.get("email")
        name = data.get("name")
        user = sociallogin.user
        user_email(user, valid_email_or_none(email) or "")
        user_field(user, "name", name)
        return user

    def authentication_error(self, request, *args, error=None, exception=None, extra_context=None, **kwargs):
        logger.bind(
            sso_error=error,
            sso_exception=repr(exception),
            sso_extra_context=extra_context,
        ).error("sso_error")
        logging.error("SSO Login error information:")
        logging.error(error)
        logging.error(exception)
        logging.error(extra_context)
        messages.warning(
            request,
            "SSO Login attempt unsuccessful.  Please consult your system administrator.",
        )
        redirect_url = reverse("dashboard")
        raise ImmediateHttpResponse(response=HttpResponseRedirect(redirect_url))
