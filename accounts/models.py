"""
Models for the accounts app.
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom user model that extends Django's AbstractUser.

    Adds additional fields needed for the fintech application.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    phone_number = models.CharField(
        _("phone number"), max_length=15, blank=True, null=True
    )
    is_verified = models.BooleanField(_("verified"), default=False)
    date_of_birth = models.DateField(_("date of birth"), blank=True, null=True)

    # Profile information
    address = models.CharField(_("address"), max_length=255, blank=True, null=True)
    city = models.CharField(_("city"), max_length=100, blank=True, null=True)
    state = models.CharField(_("state"), max_length=100, blank=True, null=True)
    postal_code = models.CharField(
        _("postal code"), max_length=20, blank=True, null=True
    )
    country = models.CharField(_("country"), max_length=100, blank=True, null=True)

    # Stripe customer ID
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Make email the required field for login
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.email


class UserVerification(models.Model):
    """
    Stores verification tokens for user email verification.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="verifications"
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - {self.token}"
