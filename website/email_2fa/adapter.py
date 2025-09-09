import re
from urllib.parse import urlencode

import structlog
from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import HOTPEmailDevice

logger = structlog.get_logger(__name__)


class OTPAdapter(DefaultAccountAdapter):
    def login(self, request, user):
        # If AUTH_2FA is not enabled we can ignore all of this.
        if not settings.AUTH_2FA:
            return super().login(request, user)

        # TODO this is a very manual way of skipping 2FA for socialaccount logins.
        #  There should be a better way of detecting this
        if re.match(r"/accounts/[a-z0-9]+/login/callback/", request.path):
            return super().login(request, user)

        # Send the email token
        two_fa_device = HOTPEmailDevice.objects.filter(user=user).first()
        two_fa_device.generate_challenge()

        request.session["email_2fa_user_id"] = str(user.id)

        redirect_url = reverse("two-factor-authenticate")
        # Add GET parameters to the URL if they exist.
        if request.GET:
            redirect_url += f"?{urlencode(request.GET)}"

        raise ImmediateHttpResponse(response=HttpResponseRedirect(redirect_url))

    def respond_user_inactive(self, request, user):
        logger.bind(sso_error_reason="user_inactive").error("sso_error")
        messages.warning(
            request,
            "SSO Login attempt unsuccessful.  Please consult your system administrator.",
        )
        redirect_url = reverse("dashboard")
        raise ImmediateHttpResponse(response=HttpResponseRedirect(redirect_url))
