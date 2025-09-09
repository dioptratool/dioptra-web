from django.contrib import admin
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import CharField, EmailField, Q
from django.utils.translation import gettext_lazy as _

from ombucore.admin.fields import ForeignKey, ManyToManyField
from website.models import Analysis
from website.models import Country


class LowerEmailField(EmailField):
    def to_python(self, value):
        """
        Convert email to lowercase on retrieval
        """
        value = super().to_python(value)
        # Value can be None so check that it's a string before lowercasing.
        if isinstance(value, str):
            return value.lower().strip()
        return value


class MinimalUserManager(BaseUserManager):
    """
    A custom user manager to deal with emails as unique identifiers for auth
    instead of usernames. The default that's used is "UserManager"
    """

    def _create_user(self, email, password, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError("The Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    app_log_entry_link_name = "ombucore.admin:users_user_change"
    BASIC_USER = "BASIC"
    ADMIN = "ADMIN"

    ROLE_CHOICES = ((BASIC_USER, "Basic User"), (ADMIN, "Administrator"))

    email = LowerEmailField(db_collation="case_insensitive_email", unique=True)

    # First Name and Last Name do not cover name patterns
    # around the globe.
    name = CharField(_("Name"), blank=True, max_length=255, help_text="First and last name")

    primary_country = ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="primary_country_users",
        null=True,
        help_text="User has write access to any analyses for this country.",
    )
    primary_countries = ManyToManyField(
        Country,
        related_name="primary_countries_users",
        blank=True,
        help_text="User has write access to any analyses for these countries.",
    )
    secondary_countries = ManyToManyField(
        Country,
        related_name="secondary_countries_users",
        blank=True,
        help_text="User has read access to any analyses in these countries.",
    )

    role = CharField(
        _("System Role"),
        max_length=255,
        choices=ROLE_CHOICES,
        default=BASIC_USER,
        help_text=_("Designates whether the user can perform admin " "functionality within the app.  "),
    )

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )

    is_first_login = models.BooleanField(_("First Login Flag"), default=True, help_text=_("Used internally."))
    USERNAME_FIELD = "email"

    objects = MinimalUserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    @property
    def associated_countries(self):
        if self.role == self.ADMIN:
            return Country.objects.all()
        else:
            countries = Country.objects.filter(primary_countries_users=self)
            countries |= Country.objects.filter(secondary_countries_users=self)
            return countries.distinct()

    def all_analyses(self):
        qs = Analysis.objects.all()
        qs = qs.order_by("-updated")
        if self.role != User.ADMIN:
            # A user can see all the analyses that meet the following criteria:
            qs = qs.filter(
                # They are the owner
                Q(owner=self)
                |
                # The Analysis country is in the secondary countries for the User
                Q(country__in=self.secondary_countries.all())
                |
                # The Analysis country is the the same as the User's primary Countries
                Q(country__in=self.primary_countries.all())
            )

        return qs

    def has_analyses(self) -> bool:
        return self.all_analyses().count() > 0


admin.site.register(User)
