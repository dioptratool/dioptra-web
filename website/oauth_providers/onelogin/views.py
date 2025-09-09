import logging

import requests
from allauth.socialaccount import app_settings
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2CallbackView,
    OAuth2LoginView,
)
from django.conf import settings as django_settings
from django.http import HttpResponseRedirect
from django.utils.http import urlencode

from .provider import OneLoginProvider

logger = logging.getLogger(__name__)


_root_url = f"https://{django_settings.ONELOGIN_APP}.onelogin.com"


class OneLoginOAuth2Adapter(OAuth2Adapter):
    provider_id = OneLoginProvider.id
    settings = app_settings.PROVIDERS.get(provider_id, {})

    authorize_url = f"{_root_url}/oidc/2/auth"
    access_token_url = f"{_root_url}/oidc/2/token"
    logout_url = f"{_root_url}/oidc/2/logout"
    profile_url = f"{_root_url}/oidc/2/me"

    redirect_uri_protocol = settings.get("PROTOCOL", "https")

    @staticmethod
    def _get_user_logout_url(user_id):
        return f"{_root_url}/api/1/users/{user_id}/logout"

    def complete_login(self, request, app, access_token, **kwargs):
        # Store provider data for later use in complete logout
        request.session["sso_provider"] = "onelogin"

        # Store id_token for later use in complete_logout
        id_token = kwargs.get("response", {}).get("id_token")
        request.session["sso_id_token"] = id_token

        headers = {"Authorization": f"Bearer {access_token.token}"}
        profile_data = requests.get(self.profile_url, headers=headers, timeout=25)
        profile_json = profile_data.json()
        return self.get_provider().sociallogin_from_response(request, profile_json)

    def complete_logout(self, id_token, redirect_uri, **kwargs):
        """
        Handles logging out of the OneLogin SSO provider

        The workflow is as follows
        1) Get the Id Token stored during complete_login
        2) Log the user out of OneLogin using the associated Id Token
        """
        params = {"id_token_hint": id_token, "post_logout_redirect_uri": redirect_uri}
        logout_redirect_url = f"{self.logout_url}?{urlencode(params)}"
        return HttpResponseRedirect(logout_redirect_url)


oauth2_login = OAuth2LoginView.adapter_view(OneLoginOAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(OneLoginOAuth2Adapter)
