"""
Service for interacting with external APIs.
"""

import logging
import time
import uuid
import requests
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from integrations.models import UserIntegration, IntegrationLog

logger = logging.getLogger(__name__)


class ExternalAPIService:
    """
    Service for interacting with external APIs.
    """

    @staticmethod
    def make_api_call(
        integration, action, request_data=None, method="GET", endpoint=None
    ):
        """
        Make an API call to an external system.

        Args:
            integration: UserIntegration model instance
            action: Description of the action being performed
            request_data: Optional data to send with the request
            method: HTTP method to use (GET, POST, etc.)
            endpoint: Optional endpoint to append to the base URL

        Returns:
            dict: API response data
        """
        # Default request data
        if request_data is None:
            request_data = {}

        # Get configuration
        system = integration.system
        config = integration.config

        # Build URL
        base_url = system.base_url
        if not base_url and config.get("base_url"):
            base_url = config.get("base_url")

        if not base_url:
            raise ValueError("No base URL provided for API call")

        if endpoint:
            url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        else:
            url = base_url

        # Set up authentication
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add authentication based on config
        auth = None
        if config.get("auth_type") == "basic":
            auth = (config.get("username", ""), config.get("password", ""))
        elif config.get("auth_type") == "api_key":
            headers[config.get("api_key_header", "X-API-Key")] = config.get(
                "api_key", ""
            )
        elif config.get("auth_type") == "bearer":
            headers["Authorization"] = f"Bearer {config.get('token', '')}"

        # Add custom headers from config
        custom_headers = config.get("headers", {})
        headers.update(custom_headers)

        # Start timer
        start_time = time.time()

        # Create log entry
        log = IntegrationLog.objects.create(
            integration=integration,
            action=action,
            request_data={
                "url": url,
                "method": method,
                "data": request_data,
                "headers": {
                    k: v
                    for k, v in headers.items()
                    if k.lower() not in ["authorization", "api-key"]
                },
            },
            status="error",  # Default to error, update on success
            duration_ms=0,
        )

        try:
            # Make the request
            response = None
            if method.upper() == "GET":
                response = requests.get(
                    url, params=request_data, headers=headers, auth=auth, timeout=30
                )
            elif method.upper() == "POST":
                response = requests.post(
                    url, json=request_data, headers=headers, auth=auth, timeout=30
                )
            elif method.upper() == "PUT":
                response = requests.put(
                    url, json=request_data, headers=headers, auth=auth, timeout=30
                )
            elif method.upper() == "PATCH":
                response = requests.patch(
                    url, json=request_data, headers=headers, auth=auth, timeout=30
                )
            elif method.upper() == "DELETE":
                response = requests.delete(
                    url, json=request_data, headers=headers, auth=auth, timeout=30
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Check for successful response
            response.raise_for_status()

            # Try to parse JSON response
            try:
                response_data = response.json()
            except ValueError:
                response_data = {"text": response.text}

            # Update log with response
            log.response_data = response_data
            log.status = "success"
            log.duration_ms = duration_ms
            log.save()

            # Update integration statistics
            with transaction.atomic():
                integration.refresh_from_db()
                integration.last_synced_at = timezone.now()
                integration.sync_count += 1
                integration.save(update_fields=["last_synced_at", "sync_count"])

            return response_data

        except requests.exceptions.RequestException as e:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Get response data if available
            response_data = {}
            if response:
                try:
                    response_data = response.json()
                except ValueError:
                    response_data = {"text": response.text}

            # Update log with error
            log.error_message = str(e)
            log.duration_ms = duration_ms
            log.response_data = response_data
            log.save()

            # Update integration statistics
            with transaction.atomic():
                integration.refresh_from_db()
                integration.error_count += 1
                integration.last_error = str(e)
                integration.save(update_fields=["error_count", "last_error"])

            logger.error(f"API call error for {integration}: {str(e)}")
            raise

    @staticmethod
    def test_connection(integration):
        """
        Test the connection to an external system.

        Args:
            integration: UserIntegration model instance

        Returns:
            dict: Test result data
        """
        try:
            system = integration.system

            # Use test endpoint if provided in system config
            test_endpoint = system.config_schema.get("test_endpoint", "")

            # Make test API call
            response = ExternalAPIService.make_api_call(
                integration=integration,
                action="test_connection",
                method="GET",
                endpoint=test_endpoint,
            )

            return {
                "success": True,
                "message": "Connection successful",
                "data": response,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "data": {},
            }

    @staticmethod
    def register_webhook(integration, webhook_url, event_types=None):
        """
        Register a webhook with the external system.

        Args:
            integration: UserIntegration model instance
            webhook_url: URL for the webhook
            event_types: List of event types to subscribe to

        Returns:
            dict: Registration result data
        """
        if event_types is None:
            event_types = []

        system = integration.system

        # Check if system supports webhooks
        if system.integration_type != "webhook":
            raise ValueError(f"System {system.name} does not support webhooks")

        # Prepare request data
        request_data = {
            "webhook_url": webhook_url,
            "event_types": event_types,
            "description": f"Webhook for {integration.user.email}",
        }

        # Add any system-specific data
        webhook_config = integration.config.get("webhook", {})
        if webhook_config:
            request_data.update(webhook_config)

        # Make API call to register webhook
        try:
            response = ExternalAPIService.make_api_call(
                integration=integration,
                action="register_webhook",
                method="POST",
                endpoint="webhooks",
                request_data=request_data,
            )

            return {
                "success": True,
                "message": "Webhook registered successfully",
                "data": response,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Webhook registration failed: {str(e)}",
                "data": {},
            }
