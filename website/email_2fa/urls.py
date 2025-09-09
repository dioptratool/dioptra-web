from django.urls import path

from . import views

urlpatterns = [
    path(
        "two-factor-authenticate/",
        views.TwoFactorAuthenticate.as_view(),
        name="two-factor-authenticate",
    ),
]
