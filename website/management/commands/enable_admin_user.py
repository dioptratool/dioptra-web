from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Activate the test user and set their password."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(email="analytics@dioptratool.org")
        user.set_password("password")
        user.is_active = True
        if user.role != User.ADMIN:
            user.role = User.ADMIN
        user.save()
        self.stdout.write(self.style.SUCCESS("Admin user activated and password set successfully."))
