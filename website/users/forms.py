from allauth.account.forms import LoginForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from ombucore.admin.buttons import CancelButton, LinkButton, SubmitButton
from ombucore.admin.forms.base import ModelFormBase
from website.models import Country

User = get_user_model()


class SelfEditUserForm(ModelFormBase):
    buttons = [
        SubmitButton(
            text="Save",
            style="primary",
            disable_when_form_unchanged=True,
            align="left",
        ),
        CancelButton(
            align="left",
        ),
        LinkButton(
            text="Change Password",
            href=reverse_lazy("account_change_password"),
            style="primary",
            align="right",
        ),
    ]

    class Meta:
        model = get_user_model()
        fields = [
            "name",
        ]


class AdminEditUserBase(ModelFormBase):
    def clean(self):
        primary_countries = self.cleaned_data.get("primary_countries")
        if primary_countries and len(primary_countries) > 10:
            raise ValidationError("Choose up to ten primary countries.")


class AdminEditUserForm(AdminEditUserBase):
    class Meta:
        model = get_user_model()
        fields = [
            "name",
            "email",
            "role",
            "primary_countries",
            "secondary_countries",
            "is_active",
        ]
        help_texts = {
            "is_active": _("Inactive users cannot log in."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        country = Country.get_default_country()
        self.fields["primary_countries"].initial = [country] if country else None


class AdminSelfEditUserForm(AdminEditUserBase):
    buttons = [
        SubmitButton(
            text="Save",
            style="primary",
            disable_when_form_unchanged=True,
            align="left",
        ),
        CancelButton(
            align="left",
        ),
        LinkButton(
            text="Change Password",
            href=reverse_lazy("account_change_password"),
            style="success",
            align="right",
        ),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].disabled = True

    class Meta:
        model = get_user_model()
        fields = [
            "name",
            "email",
            "role",
            "primary_countries",
            "secondary_countries",
        ]


class AdminOnlyLoginForm(LoginForm):
    def clean(self):
        super().clean()
        if self.user.role != User.ADMIN:
            raise ValidationError(self.error_messages["account_inactive"])
