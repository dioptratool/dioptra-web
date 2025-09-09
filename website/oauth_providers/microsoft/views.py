import json
import logging

import requests
from allauth.core import context
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2CallbackView,
    OAuth2LoginView,
)
from django.http import HttpResponseRedirect
from django.utils.http import urlencode


def _check_errors(response):
    try:
        data = response.json()
    except json.decoder.JSONDecodeError:
        raise OAuth2Error(f"Invalid JSON from Microsoft GraphAPI: {response.text}")

    if "id" not in data:
        error_message = "Error retrieving Microsoft profile"
        microsoft_error_message = data.get("error", {}).get("message")
        if microsoft_error_message:
            error_message = ": ".join((error_message, microsoft_error_message))
        raise OAuth2Error(error_message)

    return data


class MicrosoftGraphOAuth2Adapter(OAuth2Adapter):
    provider_id = "microsoft"

    def _build_tenant_url(self, path):
        settings = app_settings.PROVIDERS.get(self.provider_id, {})
        # Lower case "tenant" for backwards compatibility
        tenant = settings.get("TENANT", settings.get("tenant", "common"))
        # Prefer app based tenant setting.
        app = get_adapter().get_app(context.request, provider=self.provider_id)
        tenant = app.settings.get("tenant", tenant)

        return f"https://login.microsoftonline.com/{tenant}{path}"

    @property
    def access_token_url(self):
        return self._build_tenant_url("/oauth2/v2.0/token")

    @property
    def authorize_url(self):
        return self._build_tenant_url("/oauth2/v2.0/authorize")

    profile_url = "https://graph.microsoft.com/v1.0/me"

    user_properties = (
        "businessPhones",
        "displayName",
        "givenName",
        "id",
        "jobTitle",
        "mail",
        "mobilePhone",
        "officeLocation",
        "preferredLanguage",
        "surname",
        "userPrincipalName",
        "mailNickname",
        "companyName",
    )
    profile_url_params = {"$select": ",".join(user_properties)}

    def complete_login(self, request, app, token, **kwargs):
        # Store provider data for later use in complete logout
        request.session["sso_provider"] = "microsoft"

        # Store id_token for later use in complete_logout
        id_token = kwargs.get("response", {}).get("id_token")
        request.session["sso_id_token"] = id_token

        headers = {"Authorization": f"Bearer {token.token}"}
        logging.debug(f"DEBUG ONLY REQUEST HEADERS: {headers}")
        response = requests.get(
            self.profile_url,
            params=self.profile_url_params,
            headers=headers,
            timeout=25,
        )
        extra_data = _check_errors(response)
        return self.get_provider().sociallogin_from_response(request, extra_data)

    def complete_logout(self, id_token, redirect_uri, **kwargs):
        """
        Handles logging out of the Microsoft SSO provider

        The workflow is as follows
        1) Get the Id Token stored during complete_login
        2) Log the user out of Microsoft using the associated Id Token
        """
        params = {"id_token_hint": id_token, "post_logout_redirect_uri": redirect_uri}
        logout_redirect_url = f"{self.logout_url}?{urlencode(params)}"
        return HttpResponseRedirect(logout_redirect_url)

    @property
    def logout_url(self):
        return self._build_tenant_url("/oauth2/v2.0/logout")


oauth2_login = OAuth2LoginView.adapter_view(MicrosoftGraphOAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(MicrosoftGraphOAuth2Adapter)
