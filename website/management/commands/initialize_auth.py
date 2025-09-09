import os

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from website.management.commands.utils import get_cli_option


class Command(BaseCommand):
    help = (
        "Add a social login to the django app. "
        "OAuth client ID and secret for the auth provider can be passed "
        "through options or the environment."
    )

    def add_arguments(self, parser):
        parser.add_argument("--provider", help="Name of the OAuth provider, if added: okta, onelogin")
        parser.add_argument("--client-id", help="Client ID of the app created in the OIDC provider")
        parser.add_argument("--secret", help="Client secret of the app created in the OIDC provider")
        parser.add_argument(
            "--reset",
            help="If given, delete all social apps, rather than creating a new one",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):
        self._shim_legacy_env_vars()
        reset = options.get("reset")
        if reset:
            self.remove_all_social_apps()
            return

        provider = get_cli_option(options, "provider", envvar="OAUTH_PROVIDER", required=True)
        client_id = get_cli_option(options, "client-id", envvar="OAUTH_CLIENT_ID", required=True)
        secret = get_cli_option(options, "secret", envvar="OAUTH_SECRET", required=True)
        self.create_socialapp(provider, client_id, secret)

    def _shim_legacy_env_vars(self):
        """Previously, Okta support was much more explicitly handled.
        We shim those explicit env vars into more general ones.
        """
        legacy_provider = os.environ.get("AUTHENTICATION_PROVIDER")
        if legacy_provider and legacy_provider.lower() != "okta":
            # Only shim legacy vars in the legacy context
            return

        os.environ["OAUTH_PROVIDER"] = "okta"
        if os.environ.get("OKTA_CLIENT_ID"):
            os.environ.setdefault("OAUTH_CLIENT_ID", os.environ["OKTA_CLIENT_ID"])
        if os.environ.get("OKTA_CLIENT_SECRET"):
            os.environ.setdefault("OAUTH_SECRET", os.environ["OKTA_CLIENT_SECRET"])

    def create_socialapp(self, provider, client_id, secret):
        tprovider = provider.title()
        if SocialApp.objects.filter(provider=provider).exists():
            self.stdout.write(f"Updating {tprovider} connection...")
            s = SocialApp.objects.filter(provider=provider).first()
            s.client_id = client_id
            s.secret = secret
            s.save()
        else:
            self.stdout.write(f"Creating {tprovider} connection...")
            s = SocialApp.objects.create(
                provider=provider,
                name=f"{tprovider} Connector",
                client_id=client_id,
                secret=secret,
            )
            # Set the first and only Site.
            s.sites.add(Site.objects.first())
        self.stdout.write("Success!")

    def remove_all_social_apps(self):
        self.stdout.write("Removing all Social Apps")
        SocialApp.objects.all().delete()
