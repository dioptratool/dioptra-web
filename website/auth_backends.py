from allauth.account.auth_backends import AuthenticationBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class DioptraUserAuthenticationBackend(AuthenticationBackend):
    """
    This overwrites the default behaviour of Django AllAuth that
     normally triggers a redirect to an Account Inactive page.
     Instead the user is simply presented with an error as if they
     don't exist.
    """

    def _check_password(self, user: User, password: str) -> bool:
        ret = self.user_can_authenticate(user)
        if ret:
            ret = user.check_password(password)
        return ret
