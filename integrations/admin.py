"""
Admin configuration for the integrations app.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    ExternalSystem,
    UserIntegration,
    IntegrationLog,
    WebhookEndpoint,
    WebhookEvent,
)


class ExternalSystemAdmin(admin.ModelAdmin):
    """
    Admin interface for the ExternalSystem model.
    """

    list_display = ("name", "integration_type", "is_active", "created_at")
    list_filter = ("is_active", "integration_type", "created_at")
    search_fields = ("name", "description", "base_url")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "description", "base_url", "documentation_url")}),
        (_("Integration Type"), {"fields": ("integration_type",)}),
        (_("Configuration Schema"), {"fields": ("config_schema",)}),
        (_("Status"), {"fields": ("is_active",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )


class UserIntegrationAdmin(admin.ModelAdmin):
    """
    Admin interface for the UserIntegration model.
    """

    list_display = ("id", "user", "system", "status", "last_synced_at", "created_at")
    list_filter = ("status", "system", "created_at")
    search_fields = ("user__email", "user__username", "system__name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_synced_at",
        "sync_count",
        "error_count",
    )
    fieldsets = (
        (None, {"fields": ("user", "system")}),
        (_("Configuration"), {"fields": ("config",)}),
        (_("Status"), {"fields": ("status", "last_error")}),
        (_("Statistics"), {"fields": ("last_synced_at", "sync_count", "error_count")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )


class IntegrationLogAdmin(admin.ModelAdmin):
    """
    Admin interface for the IntegrationLog model.
    """

    list_display = (
        "id",
        "integration",
        "action",
        "status",
        "duration_ms",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("integration__user__email", "integration__system__name", "action")
    readonly_fields = ("created_at",)
    fieldsets = (
        (None, {"fields": ("integration", "action")}),
        (_("Request"), {"fields": ("request_data",)}),
        (_("Response"), {"fields": ("status", "response_data", "error_message")}),
        (_("Performance"), {"fields": ("duration_ms",)}),
        (_("Timestamps"), {"fields": ("created_at",)}),
    )


class WebhookEndpointAdmin(admin.ModelAdmin):
    """
    Admin interface for the WebhookEndpoint model.
    """

    list_display = (
        "id",
        "name",
        "user",
        "system",
        "is_active",
        "last_called_at",
        "created_at",
    )
    list_filter = ("is_active", "system", "created_at")
    search_fields = ("name", "user__email", "user__username", "system__name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "endpoint_path",
        "last_called_at",
        "call_count",
        "error_count",
    )
    fieldsets = (
        (None, {"fields": ("user", "system", "name", "description")}),
        (_("Endpoint"), {"fields": ("endpoint_path", "secret_key")}),
        (_("Configuration"), {"fields": ("event_types",)}),
        (_("Status"), {"fields": ("is_active",)}),
        (_("Statistics"), {"fields": ("last_called_at", "call_count", "error_count")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )


class WebhookEventAdmin(admin.ModelAdmin):
    """
    Admin interface for the WebhookEvent model.
    """

    list_display = (
        "id",
        "endpoint",
        "event_type",
        "status",
        "created_at",
        "processed_at",
    )
    list_filter = ("status", "event_type", "created_at")
    search_fields = ("endpoint__name", "endpoint__user__email", "event_type")
    readonly_fields = ("created_at", "updated_at", "processed_at")
    fieldsets = (
        (None, {"fields": ("endpoint", "event_type")}),
        (_("Payload"), {"fields": ("payload", "headers")}),
        (_("Processing"), {"fields": ("status", "error_message", "processed_at")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )


# Register models
admin.site.register(ExternalSystem, ExternalSystemAdmin)
admin.site.register(UserIntegration, UserIntegrationAdmin)
admin.site.register(IntegrationLog, IntegrationLogAdmin)
admin.site.register(WebhookEndpoint, WebhookEndpointAdmin)
admin.site.register(WebhookEvent, WebhookEventAdmin)
