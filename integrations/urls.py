"""
URL configuration for the integrations app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ExternalSystemViewSet,
    UserIntegrationViewSet,
    IntegrationLogViewSet,
    WebhookEndpointViewSet,
    WebhookEventViewSet,
    WebhookReceiveView,
)

router = DefaultRouter()
router.register(r"systems", ExternalSystemViewSet)
router.register(
    r"user-integrations", UserIntegrationViewSet, basename="user-integration"
)
router.register(r"logs", IntegrationLogViewSet, basename="integration-log")
router.register(
    r"webhook-endpoints", WebhookEndpointViewSet, basename="webhook-endpoint"
)
router.register(r"webhook-events", WebhookEventViewSet, basename="webhook-event")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "webhooks/<uuid:endpoint_path>/",
        WebhookReceiveView.as_view(),
        name="webhook-receive",
    ),
]
