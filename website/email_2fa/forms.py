from django.forms import CharField, Form
from django.utils.translation import gettext_lazy as _
from django_otp.forms import OTPAuthenticationFormMixin


class Email2FAAuthenticateForm(OTPAuthenticationFormMixin, Form):
    otp_token = CharField(label=_("Token"))

    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        self.fields["otp_token"].widget.attrs.update(
            {
                "autofocus": "autofocus",
                "autocomplete": "off",
            }
        )
        self.user = user

    def clean(self):
        self.clean_otp(self.user)
        return self.cleaned_data
