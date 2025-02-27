"""
Serializers for the integrations app.
"""

from rest_framework import serializers
from .models import (
    ExternalSystem,
    UserIntegration,
    IntegrationLog,
    WebhookEndpoint,
    WebhookEvent,
)


class ExternalSystemSerializer(serializers.ModelSerializer):
    """
    Serializer for the ExternalSystem model.
    """

    integration_type_display = serializers.CharField(
        source="get_integration_type_display", read_only=True
    )

    class Meta:
        model = ExternalSystem
        fields = [
            "id",
            "name",
            "description",
            "base_url",
            "documentation_url",
            "integration_type",
            "integration_type_display",
            "config_schema",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserIntegrationSerializer(serializers.ModelSerializer):
    """
    Serializer for the UserIntegration model.
    """

    system_details = ExternalSystemSerializer(source="system", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = UserIntegration
        fields = [
            "id",
            "user",
            "system",
            "system_details",
            "config",
            "status",
            "status_display",
            "last_error",
            "last_synced_at",
            "sync_count",
            "error_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "last_error",
            "last_synced_at",
            "sync_count",
            "error_count",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "config": {
                "write_only": True
            }  # For security, don't expose config in responses
        }

    def validate(self, attrs):
        """
        Validate that the config matches the system's schema.
        """
        if "system" in attrs and "config" in attrs:
            system = attrs["system"]
            config = attrs["config"]
            schema = system.config_schema

            # This is a simple validation, for production you would use a JSON schema validator
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in config:
                    raise serializers.ValidationError(
                        f"Missing required field: {field}"
                    )

        return attrs


class IntegrationLogSerializer(serializers.ModelSerializer):
    """
    Serializer for the IntegrationLog model.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = IntegrationLog
        fields = [
            "id",
            "integration",
            "action",
            "request_data",
            "response_data",
            "status",
            "status_display",
            "error_message",
            "duration_ms",
            "created_at",
        ]
        read_only_fields = fields


class WebhookEndpointSerializer(serializers.ModelSerializer):
    """
    Serializer for the WebhookEndpoint model.
    """

    system_details = ExternalSystemSerializer(source="system", read_only=True)
    webhook_url = serializers.SerializerMethodField()

    class Meta:
        model = WebhookEndpoint
        fields = [
            "id",
            "user",
            "system",
            "system_details",
            "name",
            "description",
            "endpoint_path",
            "webhook_url",
            "event_types",
            "is_active",
            "last_called_at",
            "call_count",
            "error_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "endpoint_path",
            "secret_key",
            "last_called_at",
            "call_count",
            "error_count",
            "created_at",
            "updated_at",
        ]

    def get_webhook_url(self, obj):
        """
        Build the full webhook URL.
        """
        request = self.context.get("request")
        if request is None:
            return None

        domain = request.get_host()
        scheme = "https" if request.is_secure() else "http"
        return f"{scheme}://{domain}/api/integrations/webhooks/{obj.endpoint_path}/"


class WebhookEventSerializer(serializers.ModelSerializer):
    """
    Serializer for the WebhookEvent model.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    endpoint_name = serializers.CharField(source="endpoint.name", read_only=True)
    system_name = serializers.CharField(source="endpoint.system.name", read_only=True)

    class Meta:
        model = WebhookEvent
        fields = [
            "id",
            "endpoint",
            "endpoint_name",
            "system_name",
            "event_type",
            "payload",
            "headers",
            "status",
            "status_display",
            "error_message",
            "processed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CreateUserIntegrationSerializer(serializers.Serializer):
    """
    Serializer for creating a new integration.
    """

    system_id = serializers.UUIDField(required=True)
    config = serializers.JSONField(required=True)


class UpdateUserIntegrationSerializer(serializers.Serializer):
    """
    Serializer for updating an existing integration.
    """

    config = serializers.JSONField(required=True)


class TestIntegrationSerializer(serializers.Serializer):
    """
    Serializer for testing an integration.
    """

    integration_id = serializers.UUIDField(required=True)
    test_action = serializers.CharField(required=True)
    test_data = serializers.JSONField(required=False, default=dict)


class CreateWebhookEndpointSerializer(serializers.Serializer):
    """
    Serializer for creating a new webhook endpoint.
    """

    system_id = serializers.UUIDField(required=True)
    name = serializers.CharField(required=True, max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    event_types = serializers.ListField(child=serializers.CharField(), required=True)
