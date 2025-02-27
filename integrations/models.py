"""
Models for the integrations app in the Scraping-backend project.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class ExternalSystem(models.Model):
    """
    Definition of external systems that can be integrated with.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("system name"), max_length=100)
    description = models.TextField(_("description"))
    base_url = models.URLField(_("base URL"), blank=True, null=True)
    documentation_url = models.URLField(_("documentation URL"), blank=True, null=True)

    # Integration type
    INTEGRATION_TYPE_CHOICES = [
        ("api", _("API")),
        ("webhook", _("Webhook")),
        ("oauth", _("OAuth")),
        ("scraping", _("Web Scraping")),
        ("other", _("Other")),
    ]
    integration_type = models.CharField(
        _("integration type"),
        max_length=20,
        choices=INTEGRATION_TYPE_CHOICES,
        default="api",
    )

    # Configuration schema (JSON schema format)
    config_schema = models.JSONField(
        _("configuration schema"), default=dict, blank=True
    )

    # Status and timestamps
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("external system")
        verbose_name_plural = _("external systems")

    def __str__(self):
        return self.name


class UserIntegration(models.Model):
    """
    User-specific integrations with external systems.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="integrations"
    )
    system = models.ForeignKey(
        ExternalSystem, on_delete=models.PROTECT, related_name="user_integrations"
    )

    # Connection details (encrypted)
    config = models.JSONField(_("configuration"), default=dict)

    # Status
    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("connected", _("Connected")),
        ("failed", _("Failed")),
        ("disconnected", _("Disconnected")),
    ]
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    last_error = models.TextField(_("last error"), blank=True, null=True)

    # Connection statistics
    last_synced_at = models.DateTimeField(_("last synced"), null=True, blank=True)
    sync_count = models.PositiveIntegerField(_("sync count"), default=0)
    error_count = models.PositiveIntegerField(_("error count"), default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("user integration")
        verbose_name_plural = _("user integrations")
        unique_together = [["user", "system"]]

    def __str__(self):
        return f"{self.user.email} - {self.system.name}"


class IntegrationLog(models.Model):
    """
    Log of interactions with external systems.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        UserIntegration, on_delete=models.CASCADE, related_name="logs"
    )

    # Log details
    action = models.CharField(_("action"), max_length=100)
    request_data = models.JSONField(_("request data"), default=dict, blank=True)
    response_data = models.JSONField(_("response data"), default=dict, blank=True)

    # Status
    STATUS_CHOICES = [
        ("success", _("Success")),
        ("error", _("Error")),
    ]
    status = models.CharField(_("status"), max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(_("error message"), blank=True, null=True)

    # Performance metrics
    duration_ms = models.PositiveIntegerField(_("duration (ms)"), default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("integration log")
        verbose_name_plural = _("integration logs")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.integration} - {self.action} ({self.status})"


class WebhookEndpoint(models.Model):
    """
    Webhook endpoints for receiving data from external systems.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="webhook_endpoints"
    )
    system = models.ForeignKey(
        ExternalSystem, on_delete=models.PROTECT, related_name="webhook_endpoints"
    )

    # Endpoint details
    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True, null=True)
    endpoint_path = models.UUIDField(
        _("endpoint path"), default=uuid.uuid4, unique=True
    )

    # Configuration
    event_types = models.JSONField(_("event types"), default=list)
    secret_key = models.CharField(_("secret key"), max_length=100)

    # Status
    is_active = models.BooleanField(_("active"), default=True)

    # Usage statistics
    last_called_at = models.DateTimeField(_("last called"), null=True, blank=True)
    call_count = models.PositiveIntegerField(_("call count"), default=0)
    error_count = models.PositiveIntegerField(_("error count"), default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("webhook endpoint")
        verbose_name_plural = _("webhook endpoints")

    def __str__(self):
        return f"{self.name} ({self.system.name})"


class WebhookEvent(models.Model):
    """
    Events received by webhook endpoints.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="events"
    )

    # Event details
    event_type = models.CharField(_("event type"), max_length=100)
    payload = models.JSONField(_("payload"), default=dict)
    headers = models.JSONField(_("headers"), default=dict)

    # Processing status
    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("processing", _("Processing")),
        ("processed", _("Processed")),
        ("failed", _("Failed")),
    ]
    status = models.CharField(
        _("status"), max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    error_message = models.TextField(_("error message"), blank=True, null=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("webhook event")
        verbose_name_plural = _("webhook events")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.endpoint.name} - {self.event_type} ({self.status})"
