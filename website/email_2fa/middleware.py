from django.urls import resolve


class EmailTwoFactorMiddleware:
    """
    Reset the login flow if another page is loaded halfway through the login.
    (I.e. if the user has logged in with a username/password, but not yet
    entered their two-factor credentials.) This makes sure a user does not stay
    half logged in by mistake.

    """

    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        return self.get_response(request)

    def process_request(self, request):
        match = resolve(request.path)
        if not match.url_name or not match.url_name.startswith("two-factor-authenticate"):
            try:
                del request.session["email_2fa_user_id"]
            except KeyError:
                pass
