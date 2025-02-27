"""
Models for the payments app in the Scraping-backend project.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class TokenPackage(models.Model):
    """
    Token packages that users can purchase.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("package name"), max_length=100)
    description = models.TextField(_("description"), blank=True, null=True)
    token_amount = models.IntegerField(_("token amount"))
    price = models.DecimalField(_("price"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    
    # Stripe product and price IDs
    stripe_product_id = models.CharField(_("Stripe product ID"), max_length=100, blank=True, null=True)
    stripe_price_id = models.CharField(_("Stripe price ID"), max_length=100, blank=True, null=True)
    
    # Status and timestamps
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("token package")
        verbose_name_plural = _("token packages")
        
    def __str__(self):
        return f"{self.name} ({self.token_amount} tokens, {self.price} {self.currency})"


class Plan(models.Model):
    """
    Subscription plans for users.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("plan name"), max_length=100)
    description = models.TextField(_("description"))
    price = models.DecimalField(_("price"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    interval = models.CharField(
        _("billing interval"),
        max_length=20,
        choices=[
            ("day", _("Daily")),
            ("week", _("Weekly")),
            ("month", _("Monthly")),
            ("year", _("Yearly")),
        ],
        default="month",
    )

    # Limits and features
    max_api_calls = models.IntegerField(_("max API calls"), default=1000)
    max_scraping_jobs = models.IntegerField(_("max scraping jobs"), default=10)
    has_priority_support = models.BooleanField(_("has priority support"), default=False)

    # Stripe product and price IDs
    stripe_product_id = models.CharField(
        _("Stripe product ID"), max_length=100, blank=True, null=True
    )
    stripe_price_id = models.CharField(
        _("Stripe price ID"), max_length=100, blank=True, null=True
    )

    # Status and timestamps
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("plan")
        verbose_name_plural = _("plans")

    def __str__(self):
        return (
            f"{self.name} ({self.get_interval_display()}: {self.price} {self.currency})"
        )


class Subscription(models.Model):
    """
    User subscriptions to plans.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.SET_NULL, null=True, related_name="subscriptions"
    )

    # Status
    STATUS_CHOICES = [
        ("active", _("Active")),
        ("canceled", _("Canceled")),
        ("past_due", _("Past Due")),
        ("trialing", _("Trialing")),
        ("unpaid", _("Unpaid")),
        ("incomplete", _("Incomplete")),
        ("incomplete_expired", _("Incomplete Expired")),
    ]
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="incomplete"
    )

    # Dates
    start_date = models.DateTimeField(_("start date"))
    end_date = models.DateTimeField(_("end date"), null=True, blank=True)
    trial_end = models.DateTimeField(_("trial end date"), null=True, blank=True)

    # Stripe information
    stripe_subscription_id = models.CharField(
        _("Stripe subscription ID"), max_length=100, blank=True, null=True
    )

    # Usage tracking
    api_calls_used = models.IntegerField(_("API calls used"), default=0)
    scraping_jobs_used = models.IntegerField(_("scraping jobs used"), default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")

    def __str__(self):
        plan_name = self.plan.name if self.plan else "No Plan"
        return f"{self.user.email} - {plan_name} ({self.status})"


class Payment(models.Model):
    """
    Payment records for subscriptions and one-time purchases.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    token_package = models.ForeignKey(
        TokenPackage, on_delete=models.SET_NULL, null=True, blank=True
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    # Payment details
    amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    payment_method = models.CharField(_("payment method"), max_length=50)
    token_amount = models.IntegerField(_("token amount"), default=0)

    # Status
    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("completed", _("Completed")),
        ("failed", _("Failed")),
        ("refunded", _("Refunded")),
    ]
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="pending"
    )

    # Stripe information
    stripe_payment_intent_id = models.CharField(
        _("Stripe payment intent ID"), max_length=100, blank=True, null=True
    )
    stripe_charge_id = models.CharField(
        _("Stripe charge ID"), max_length=100, blank=True, null=True
    )

    # Description and metadata
    description = models.CharField(
        _("description"), max_length=255, blank=True, null=True
    )
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")

    def __str__(self):
        return f"{self.user.email} - {self.amount} {self.currency} ({self.get_status_display()})"


class Invoice(models.Model):
    """
    Invoice records for payments.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invoices")
    payment = models.OneToOneField(
        Payment, on_delete=models.CASCADE, related_name="invoice"
    )

    # Invoice details
    invoice_number = models.CharField(_("invoice number"), max_length=50, unique=True)
    invoice_date = models.DateField(_("invoice date"))
    due_date = models.DateField(_("due date"))

    # Status
    STATUS_CHOICES = [
        ("draft", _("Draft")),
        ("open", _("Open")),
        ("paid", _("Paid")),
        ("uncollectible", _("Uncollectible")),
        ("void", _("Void")),
    ]
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="draft"
    )

    # Billing information
    billing_name = models.CharField(_("billing name"), max_length=255)
    billing_address = models.TextField(_("billing address"))
    billing_email = models.EmailField(_("billing email"))

    # Stripe information
    stripe_invoice_id = models.CharField(
        _("Stripe invoice ID"), max_length=100, blank=True, null=True
    )

    # PDF invoice
    pdf_url = models.URLField(_("PDF URL"), blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.user.email}"