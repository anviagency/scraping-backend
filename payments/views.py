"""
Views for the payments app in the Scraping-backend project.
For scraping.co.il
"""

import logging
from django.utils import timezone
from django.http import HttpResponse
from django.conf import settings

from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

import stripe
from .models import Plan, Subscription, Payment, Invoice
from .serializers import (
    PlanSerializer,
    SubscriptionSerializer,
    PaymentSerializer,
    InvoiceSerializer,
    CreateSubscriptionSerializer,
    CancelSubscriptionSerializer,
    UpdatePaymentMethodSerializer,
    CreateCheckoutSessionSerializer,
)
from .services.stripe_service import StripeService

logger = logging.getLogger(__name__)


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing plans.
    """

    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing subscriptions.
    """

    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset based on user permissions.
        """
        user = self.request.user

        if user.is_staff:
            return Subscription.objects.all()

        # Regular users can only see their own subscriptions
        return Subscription.objects.filter(user=user)

    @swagger_auto_schema(
        method="post",
        request_body=CreateSubscriptionSerializer,
        responses={201: SubscriptionSerializer()},
        operation_description="Create a new subscription.",
    )
    @action(detail=False, methods=["post"], url_path="create")
    def create_subscription(self, request):
        """
        Create a new subscription.
        """
        serializer = CreateSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            plan = Plan.objects.get(id=serializer.validated_data["plan_id"])

            # Call Stripe to create subscription
            stripe_subscription = StripeService.create_subscription(
                request.user,
                plan,
                serializer.validated_data["payment_method_id"],
                serializer.validated_data.get("coupon"),
            )

            # Create subscription record
            start_date = timezone.datetime.fromtimestamp(
                stripe_subscription["current_period_start"]
            )
            end_date = timezone.datetime.fromtimestamp(
                stripe_subscription["current_period_end"]
            )
            trial_end = None
            if stripe_subscription.get("trial_end"):
                trial_end = timezone.datetime.fromtimestamp(
                    stripe_subscription["trial_end"]
                )

            subscription = Subscription.objects.create(
                user=request.user,
                plan=plan,
                status=stripe_subscription["status"],
                start_date=start_date,
                end_date=end_date,
                trial_end=trial_end,
                stripe_subscription_id=stripe_subscription["id"],
            )

            return Response(
                SubscriptionSerializer(subscription).data,
                status=status.HTTP_201_CREATED,
            )

        except Plan.DoesNotExist:
            return Response(
                {"error": "Plan not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except stripe.error.CardError as e:
            return Response(
                {"error": f"Card error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return Response(
                {"error": "An error occurred while creating the subscription"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        method="post",
        request_body=CancelSubscriptionSerializer,
        responses={200: SubscriptionSerializer()},
        operation_description="Cancel a subscription.",
    )
    @action(detail=False, methods=["post"], url_path="cancel")
    def cancel_subscription(self, request):
        """
        Cancel a subscription.
        """
        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            subscription = Subscription.objects.get(
                id=serializer.validated_data["subscription_id"], user=request.user
            )

            # Call Stripe to cancel subscription
            stripe_subscription = StripeService.cancel_subscription(
                subscription, serializer.validated_data.get("at_period_end", True)
            )

            # Update subscription status
            if not serializer.validated_data.get("at_period_end", True):
                subscription.status = "canceled"
                subscription.save()

            return Response(
                SubscriptionSerializer(subscription).data, status=status.HTTP_200_OK
            )

        except Subscription.DoesNotExist:
            return Response(
                {"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return Response(
                {"error": "An error occurred while cancelling the subscription"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        method="post",
        request_body=UpdatePaymentMethodSerializer,
        responses={200: "Payment method updated successfully"},
        operation_description="Update payment method.",
    )
    @action(detail=False, methods=["post"], url_path="update-payment-method")
    def update_payment_method(self, request):
        """
        Update payment method.
        """
        serializer = UpdatePaymentMethodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Call Stripe to update payment method
            StripeService.update_payment_method(
                request.user, serializer.validated_data["payment_method_id"]
            )

            return Response(
                {"message": "Payment method updated successfully"},
                status=status.HTTP_200_OK,
            )

        except stripe.error.CardError as e:
            return Response(
                {"error": f"Card error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating payment method: {str(e)}")
            return Response(
                {"error": "An error occurred while updating the payment method"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        method="post",
        request_body=CreateCheckoutSessionSerializer,
        responses={200: "Checkout session created successfully"},
        operation_description="Create a checkout session.",
    )
    @action(detail=False, methods=["post"], url_path="create-checkout-session")
    def create_checkout_session(self, request):
        """
        Create a checkout session.
        """
        serializer = CreateCheckoutSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            plan = Plan.objects.get(id=serializer.validated_data["plan_id"])

            # Call Stripe to create checkout session
            checkout_session = StripeService.create_checkout_session(
                request.user,
                plan,
                serializer.validated_data["success_url"],
                serializer.validated_data["cancel_url"],
            )

            return Response(
                {"session_id": checkout_session.id}, status=status.HTTP_200_OK
            )

        except Plan.DoesNotExist:
            return Response(
                {"error": "Plan not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            return Response(
                {"error": "An error occurred while creating the checkout session"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing payments.
    """

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset based on user permissions.
        """
        user = self.request.user

        if user.is_staff:
            return Payment.objects.all()

        # Regular users can only see their own payments
        return Payment.objects.filter(user=user)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing invoices.
    """

    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset based on user permissions.
        """
        user = self.request.user

        if user.is_staff:
            return Invoice.objects.all()

        # Regular users can only see their own invoices
        return Invoice.objects.filter(user=user)


class StripeWebhookView(generics.GenericAPIView):
    """
    View for handling Stripe webhooks.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        Handle webhook events from Stripe.
        """
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            # Process the webhook
            event_data = StripeService.handle_webhook_event(payload, sig_header)

            return Response(event_data, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return Response(
                {"error": "An error occurred while processing the webhook"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
