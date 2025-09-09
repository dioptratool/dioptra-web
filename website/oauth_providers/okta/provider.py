from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from django.conf import settings

from website.oauth_providers.okta.views import OktaOAuth2Adapter


class OktaAccount(ProviderAccount):
    def to_str(self):
        dflt = super().to_str()
        return self.account.extra_data.get("name", dflt)


def get_auth_url():
    url = ""
    base_path = getattr(settings, "OKTA_OAUTH2_PATH", None)
    provider = (
        settings.SOCIALACCOUNT_PROVIDERS.get("okta") if hasattr(settings, "SOCIALACCOUNT_PROVIDERS") else None
    )
    if base_path and provider:
        domain = settings.SOCIALACCOUNT_PROVIDERS["okta"].get("DEFAULT_URL")
        if domain:
            url = f"{domain}{base_path}/authorize"
    return url


AUTHORIZE_URL = get_auth_url()


class OktaProvider(OAuth2Provider):
    id = "okta"
    name = "Okta"
    account_class = OktaAccount
    authorize_url = AUTHORIZE_URL
    logo_filename = "website/images/okta-logo.png"

    oauth2_adapter_class = OktaOAuth2Adapter

    def extract_uid(self, data):
        return str(data["sub"])

    def extract_common_fields(self, data):
        return dict(
            email=data["email"],
            name=data["name"],
        )

    def get_default_scope(self):
        return ["openid", "profile", "email"]


provider_classes = [OktaProvider]
