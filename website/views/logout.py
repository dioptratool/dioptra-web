import logging

from allauth.account.views import LogoutView as AllAuthLogoutView
from allauth.socialaccount.models import SocialApp
from django.conf import settings

from website.oauth_providers.microsoft.views import MicrosoftGraphOAuth2Adapter
from website.oauth_providers.okta.views import OktaOAuth2Adapter
from website.oauth_providers.onelogin.views import OneLoginOAuth2Adapter

logger = logging.getLogger(__name__)


class LogoutView(AllAuthLogoutView):
    """
    Used for handling any necessary SSO logouts
    """

    SOCIAL_PROVIDER_ADAPTERS = {
        "microsoft": MicrosoftGraphOAuth2Adapter,
        "okta": OktaOAuth2Adapter,
        "onelogin": OneLoginOAuth2Adapter,
    }

    """
    Handles logout action
    
    If there is no SSO provider in active use, this will be a standard logout
    If there is an SSO provider in use, this method runs logic to handle SLO of the user from the SSO provider
    
    Okta: https://developer.okta.com/docs/reference/api/oidc/#logout
    OneLogin : https://developers.onelogin.com/openid-connect/api/logout
    
    """

    def post(self, *args, **kwargs):
        # Cache SSO values from the session, as they will be cleared during the standard Django Logout method
        sso_provider = self.request.session.get("sso_provider")
        sso_id_token = self.request.session.get("sso_id_token")
        if not (sso_provider and sso_id_token):
            # Early exit if no additional SSO logic is required
            return super().post(*args, **kwargs)

        # Run standard Django logout
        dj_logout_resp = super().post(*args, **kwargs)

        # Get the corresponding Adapter based on the provider
        adapter_class = self.SOCIAL_PROVIDER_ADAPTERS.get(sso_provider)
        if not adapter_class:
            # Early exit if no additional SSO logic is required
            logger.warning(f"Missing {sso_provider} Adapter")
            return dj_logout_resp

        # Construct base url for SSO provider to redirect back to
        domain = settings.BASE_URL
        redirect_uri = f"{domain}/accounts/login/"

        social_app = SocialApp.objects.filter(provider=sso_provider).first()
        return adapter_class(self.request).complete_logout(sso_id_token, redirect_uri, social_app=social_app)
