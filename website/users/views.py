from allauth.account.forms import UserTokenForm
from allauth.account.views import LoginView, PasswordResetFromKeyView, _ajax_response
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from django.views.generic import FormView

from ombucore.admin.views import ChangeView
from website.app_log.loggers import log_user_made_active, log_user_made_inactive
from website.users.forms import (
    AdminEditUserForm,
    AdminOnlyLoginForm,
    AdminSelfEditUserForm,
    SelfEditUserForm,
)


class UserChangeView(ChangeView):
    template_name = "user/edit.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("users.change_any_user"):
            if request.user.pk != int(kwargs["pk"]):
                return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        if self.request.user.has_perm("users.change_any_user"):
            if self.request.user == self.object:
                return AdminSelfEditUserForm
            else:
                return AdminEditUserForm

        return SelfEditUserForm

    def form_valid(self, form):
        response = super().form_valid(form)
        if "is_active" in form.changed_data:
            if self.object.is_active:
                log_user_made_active(self.object, self.request.user)
            else:
                log_user_made_inactive(self.object, self.request.user)
        return response


class CustomPasswordResetFromKeyView(PasswordResetFromKeyView):
    template_name = "account/password_set.html"

    @property
    def success_url(self):
        return reverse_lazy("account_login")

    def dispatch(self, request, uidb36, key, **kwargs):
        self.request = request
        self.key = key
        token_form = UserTokenForm(data={"uidb36": uidb36, "key": self.key})
        if token_form.is_valid():
            # Store the key in the session and redirect to the
            # password reset form at a URL without the key. That
            # avoids the possibility of leaking the key in the
            # HTTP Referer header.
            # (Ab)using forms here to be able to handle errors in XHR #890
            token_form = UserTokenForm(data={"uidb36": uidb36, "key": self.key})
            if token_form.is_valid():
                self.reset_user = token_form.reset_user
                # This super call is an intentional jump over the inherited form
                return super(FormView, self).dispatch(request, uidb36, self.key, **kwargs)
        self.reset_user = None
        response = self.render_to_response(self.get_context_data(token_fail=True))
        return _ajax_response(self.request, response, form=token_form)


class AdminLoginView(LoginView):
    template_name = "account/adminlogin.html"
    form_class = AdminOnlyLoginForm
