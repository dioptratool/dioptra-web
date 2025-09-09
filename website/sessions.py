import time

from django.conf import settings
from django.contrib.auth import logout


class SessionIdleMiddleware:
    """
    Used automatically logout the user from Dioptra when they close the browser session,
    as well as after 1 hour of inactivity
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if "last_request" in request.session:
                elapsed = time.time() - request.session["last_request"]
                if elapsed > settings.SESSION_IDLE_TIMEOUT:
                    del request.session["last_request"]
                    logout(request)

            # Reset inactivity time counter
            request.session["last_request"] = time.time()

            # This causes the session cookie to expire when the user's web browser is closed
            # https://docs.djangoproject.com/en/4.0/topics/http/sessions/#django.contrib.sessions.backends.base.SessionBase.set_expiry
            request.session.set_expiry(0)
        else:
            if "last_request" in request.session:
                del request.session["last_request"]

        response = self.get_response(request)

        return response
