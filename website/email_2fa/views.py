from allauth.account import signals
from allauth.account.adapter import get_adapter
from allauth.account.utils import get_login_redirect_url
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.views.generic import FormView

from .adapter import OTPAdapter
from .forms import Email2FAAuthenticateForm


class TwoFactorAuthenticate(FormView):
    template_name = f"email_2fa/authenticate.html"
    form_class = Email2FAAuthenticateForm

    def dispatch(self, request, *args, **kwargs):
        # If the user is not about to enter their two-factor credentials,
        # redirect to the login page (they shouldn't be here!). This includes
        # anonymous users.
        if "email_2fa_user_id" not in request.session:
            # Don't use the redirect_to_login here since we don't actually want
            # to include the next parameter.
            return redirect("account_login")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user_id = self.request.session["email_2fa_user_id"]
        kwargs["user"] = get_user_model().objects.get(id=user_id)
        return kwargs

    def form_valid(self, form):
        """
        The allauth 2fa login flow is now done (the user logged in successfully
        with 2FA), continue the logic from allauth.account.utils.perform_login
        since it was interrupted earlier.

        """
        adapter = get_adapter(self.request)

        # Skip over the (already done) 2fa login flow and continue the original
        # allauth login flow.
        super(OTPAdapter, adapter).login(self.request, form.user)

        response = HttpResponseRedirect(get_login_redirect_url(self.request))

        signals.user_logged_in.send(
            sender=form.user.__class__,
            request=self.request,
            response=response,
            user=form.user,
        )

        adapter.add_message(
            self.request,
            messages.SUCCESS,
            "account/messages/logged_in.txt",
            {"user": form.user},
        )

        return response
