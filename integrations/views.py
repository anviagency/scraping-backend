"""
Views for the integrations app in the Scraping-backend project.
For scraping.co.il
"""

import logging
import uuid
from django.http import Http404
from django.utils import timezone
from django.db import transaction

from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    ExternalSystem,
    UserIntegration,
    IntegrationLog,
    WebhookEndpoint,
    WebhookEvent,
)
from .serializers import (
    ExternalSystemSerializer,
    UserIntegrationSerializer,
    IntegrationLogSerializer,
    WebhookEndpointSerializer,
    WebhookEventSerializer,
    CreateUserIntegrationSerializer,
    UpdateUserIntegrationSerializer,
    TestIntegrationSerializer,
    CreateWebhookEndpointSerializer,
)
from .services.external_api_service import ExternalAPIService

logger = logging.getLogger(__name__)


class ExternalSystemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing available external systems.
    """

    queryset = ExternalSystem.objects.filter(is_active=True)
    serializer_class = ExternalSystemSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserIntegrationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user integrations.
    """

    serializer_class = UserIntegrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset based on user permissions.
        """
        user = self.request.user

        if user.is_staff:
            return UserIntegration.objects.all()

        # Regular users can only see their own integrations
        return UserIntegration.objects.filter(user=user)

    def perform_create(self, serializer):
        """
        Set the user when creating an integration.
        """
        serializer.save(user=self.request.user)

    @swagger_auto_schema(
        method="post",
        request_body=CreateUserIntegrationSerializer,
        responses={201: UserIntegrationSerializer()},
        operation_description="Create a new integration.",
    )
    @action(detail=False, methods=["post"], url_path="create")
    def create_integration(self, request):
        """
        Create a new integration.
        """
        serializer = CreateUserIntegrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            system = ExternalSystem.objects.get(
                id=serializer.validated_data["system_id"], is_active=True
            )

            # Create integration
            integration = UserIntegration.objects.create(
                user=request.user,
                system=system,
                config=serializer.validated_data["config"],
                status="pending",
            )

            # Test the connection
            test_result = ExternalAPIService.test_connection(integration)

            # Update status based on test result
            integration.status = "connected" if test_result["success"] else "failed"
            if not test_result["success"]:
                integration.last_error = test_result["message"]
            integration.save()

            return Response(
                UserIntegrationSerializer(integration).data,
                status=status.HTTP_201_CREATED,
            )

        except ExternalSystem.DoesNotExist:
            return Response(
                {"error": "System not found or inactive"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error creating integration: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method="post",
        request_body=UpdateUserIntegrationSerializer,
        responses={200: UserIntegrationSerializer()},
        operation_description="Update an integration.",
    )
    @action(detail=True, methods=["post"], url_path="update")
    def update_integration(self, request, pk=None):
        """
        Update an integration.
        """
        try:
            integration = self.get_object()
            serializer = UpdateUserIntegrationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Update config
            integration.config = serializer.validated_data["config"]
            integration.status = "pending"
            integration.save()

            # Test the connection
            test_result = ExternalAPIService.test_connection(integration)

            # Update status based on test result
            integration.status = "connected" if test_result["success"] else "failed"
            if not test_result["success"]:
                integration.last_error = test_result["message"]
            integration.save()

            return Response(
                UserIntegrationSerializer(integration).data, status=status.HTTP_200_OK
            )

        except Http404:
            return Response(
                {"error": "Integration not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating integration: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method="post",
        request_body=TestIntegrationSerializer,
        responses={200: "Test result"},
        operation_description="Test an integration.",
    )
    @action(detail=False, methods=["post"], url_path="test")
    def test_integration(self, request):
        """
        Test an integration.
        """
        serializer = TestIntegrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            integration = UserIntegration.objects.get(
                id=serializer.validated_data["integration_id"], user=request.user
            )

            # Perform test action
            action = serializer.validated_data["test_action"]
            test_data = serializer.validated_data.get("test_data", {})

            if action == "test_connection":
                result = ExternalAPIService.test_connection(integration)
            else:
                # Make custom API call
                response = ExternalAPIService.make_api_call(
                    integration=integration,
                    action=action,
                    request_data=test_data,
                    method=test_data.get("method", "GET"),
                    endpoint=test_data.get("endpoint", ""),
                )
                result = {
                    "success": True,
                    "message": "API call successful",
                    "data": response,
                }

            return Response(result, status=status.HTTP_200_OK)

        except UserIntegration.DoesNotExist:
            return Response(
                {"error": "Integration not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error testing integration: {str(e)}")
            return Response(
                {"success": False, "message": str(e), "data": {}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IntegrationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing integration logs.
    """

    serializer_class = IntegrationLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset based on user permissions.
        """
        user = self.request.user

        if user.is_staff:
            return IntegrationLog.objects.all()

        # Regular users can only see logs for their own integrations
        return IntegrationLog.objects.filter(integration__user=user)


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing webhook endpoints.
    """

    serializer_class = WebhookEndpointSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset based on user permissions.
        """
        user = self.request.user

        if user.is_staff:
            return WebhookEndpoint.objects.all()

        # Regular users can only see their own webhook endpoints
        return WebhookEndpoint.objects.filter(user=user)

    def perform_create(self, serializer):
        """
        Set the user when creating a webhook endpoint.
        """
        serializer.save(
            user=self.request.user,
            endpoint_path=uuid.uuid4(),
            secret_key=uuid.uuid4().hex,
        )

    @swagger_auto_schema(
        method="post",
        request_body=CreateWebhookEndpointSerializer,
        responses={201: WebhookEndpointSerializer()},
        operation_description="Create a new webhook endpoint.",
    )
    @action(detail=False, methods=["post"], url_path="create")
    def create_webhook(self, request):
        """
        Create a new webhook endpoint.
        """
        serializer = CreateWebhookEndpointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            system = ExternalSystem.objects.get(
                id=serializer.validated_data["system_id"], is_active=True
            )

            # Create webhook endpoint
            endpoint = WebhookEndpoint.objects.create(
                user=request.user,
                system=system,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                event_types=serializer.validated_data["event_types"],
                endpoint_path=uuid.uuid4(),
                secret_key=uuid.uuid4().hex,
            )

            # Return with full URL
            return Response(
                WebhookEndpointSerializer(endpoint, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

        except ExternalSystem.DoesNotExist:
            return Response(
                {"error": "System not found or inactive"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error creating webhook endpoint: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing webhook events.
    """

    serializer_class = WebhookEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset based on user permissions.
        """
        user = self.request.user

        if user.is_staff:
            return WebhookEvent.objects.all()

        # Regular users can only see events for their own webhook endpoints
        return WebhookEvent.objects.filter(endpoint__user=user)


class WebhookReceiveView(generics.GenericAPIView):
    """
    View for receiving webhook events.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, endpoint_path):
        """
        Handle incoming webhook events.
        """
        try:
            # Find the webhook endpoint
            endpoint = WebhookEndpoint.objects.get(
                endpoint_path=endpoint_path, is_active=True
            )

            # Update webhook endpoint stats
            with transaction.atomic():
                endpoint.last_called_at = timezone.now()
                endpoint.call_count += 1
                endpoint.save(update_fields=["last_called_at", "call_count"])

            # Get event type from request
            event_type = request.data.get("event", request.data.get("type", "unknown"))

            # Create webhook event record
            event = WebhookEvent.objects.create(
                endpoint=endpoint,
                event_type=event_type,
                payload=request.data,
                headers=dict(request.headers),
                status="pending",
            )

            # Process the event (could be done asynchronously in production)
            try:
                # Add processing logic here

                # Mark as processed
                event.status = "processed"
                event.processed_at = timezone.now()
                event.save()

            except Exception as e:
                # Mark as failed
                event.status = "failed"
                event.error_message = str(e)
                event.save()

                # Update endpoint error count
                endpoint.error_count += 1
                endpoint.save(update_fields=["error_count"])

                logger.error(f"Error processing webhook event {event.id}: {str(e)}")

            # Return success response
            return Response(
                {"status": "success", "event_id": str(event.id)},
                status=status.HTTP_200_OK,
            )

        except WebhookEndpoint.DoesNotExist:
            return Response(
                {"error": "Invalid webhook endpoint"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Webhook receive error: {str(e)}")
            return Response(
                {"error": "An error occurred while processing the webhook"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
