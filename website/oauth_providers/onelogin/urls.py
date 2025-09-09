from allauth.socialaccount.providers.oauth2.urls import default_urlpatterns

from .provider import OneLoginProvider

urlpatterns = default_urlpatterns(OneLoginProvider)
