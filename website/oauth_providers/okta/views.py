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


class OktaOAuth2Adapter(OAuth2Adapter):
    provider_id = "okta"
    settings = app_settings.PROVIDERS.get(provider_id, {})

    provider_default_url = settings.get("DEFAULT_URL")

    authorize_url = f"{provider_default_url}{django_settings.OKTA_OAUTH2_PATH}/authorize"
    access_token_url = f"{provider_default_url}{django_settings.OKTA_OAUTH2_PATH}/token"
    logout_url = f"{provider_default_url}{django_settings.OKTA_OAUTH2_PATH}/logout"
    profile_url = f"{provider_default_url}{django_settings.OKTA_OAUTH2_PATH}/userinfo"

    redirect_uri_protocol = settings.get("PROTOCOL", "https")

    def complete_login(self, request, app, access_token, **kwargs):
        # Store provider data for later use in complete logout
        request.session["sso_provider"] = "okta"

        # Store id_token for later use in complete_logout
        id_token = kwargs.get("response", {}).get("id_token")
        request.session["sso_id_token"] = id_token

        headers = {"Authorization": f"Bearer {access_token.token}"}
        profile_data = requests.get(self.profile_url, headers=headers, timeout=25)
        profile_json = profile_data.json()

        return self.get_provider().sociallogin_from_response(request, profile_json)

    def complete_logout(self, id_token, redirect_uri, **kwargs):
        """
        Handles logging out of the Okta SSO provider

        The workflow is as follows
        1) Get the Id Token stored during complete_login
        2) Log the user out of Okta using the associated Id Token
        """
        params = {"id_token_hint": id_token, "post_logout_redirect_uri": redirect_uri}
        logout_redirect_url = f"{self.logout_url}?{urlencode(params)}"
        return HttpResponseRedirect(logout_redirect_url)


oauth2_login = OAuth2LoginView.adapter_view(OktaOAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(OktaOAuth2Adapter)
