from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider


class OneLoginAccount(ProviderAccount):
    def to_str(self):
        dflt = super().to_str()
        print(self.account.extra_data, dflt)
        return self.account.extra_data.get("name", dflt)


class OneLoginProvider(OAuth2Provider):
    id = "onelogin"
    name = "OneLogin"
    account_class = OneLoginAccount
    logo_filename = "website/images/onelogin-logo.png"

    def extract_uid(self, data):
        # {
        #     'sub': '145784491',
        #     'email': 'analytics+dioptra@dioptratool.org',
        #     'preferred_username': 'analytics+dioptra@dioptratool.org',
        #     'name': 'Martin Rio',
        #     'updated_at': 1628839124,
        #     'given_name': 'Martin',
        #     'family_name': 'Rio'
        # }
        return str(data["sub"])

    def extract_common_fields(self, data):
        return dict(
            email=data["email"],
            name=data["name"],
        )

    def get_default_scope(self):
        return ["openid", "profile", "email"]


provider_classes = [OneLoginProvider]
