"""
Views for the payments app in the Scraping-backend project.
For scraping.co.il
"""

import logging
import stripe
from django.utils import timezone
from django.http import HttpResponse
from django.conf import settings
from django.db import transaction

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from accounts.models import User, Transaction
from .models import TokenPackage, Payment, Invoice
from .serializers import (
    TokenPackageSerializer,
    PaymentSerializer,
    InvoiceSerializer,
    CreatePaymentIntentSerializer,
    ConfirmPaymentSerializer,
)
from .services.stripe_service import StripeService

logger = logging.getLogger(__name__)

# Configure Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY


class TokenPackageListView(generics.ListAPIView):
    """
    View for listing available token packages.
    """
    serializer_class = TokenPackageSerializer
    permission_classes = [permissions.AllowAny]
    queryset = TokenPackage.objects.filter(is_active=True)


class PaymentHistoryView(generics.ListAPIView):
    """
    View for listing user payment history.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset of payments for the current user.
        """
        return Payment.objects.filter(user=self.request.user).order_by('-created_at')


class CreatePaymentIntentView(APIView):
    """
    View for creating a Stripe payment intent.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=CreatePaymentIntentSerializer,
        responses={200: "Payment intent created", 400: "Invalid package"},
        operation_description="Create a Stripe payment intent for token purchase.",
    )
    def post(self, request):
        """
        Create a Stripe payment intent for token purchase.
        """
        serializer = CreatePaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Get token package
            token_package = TokenPackage.objects.get(
                id=serializer.validated_data["token_package_id"],
                is_active=True
            )

            # Ensure user has a Stripe customer ID
            if not request.user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=f"{request.user.first_name} {request.user.last_name}",
                    metadata={"user_id": str(request.user.id)},
                )
                request.user.stripe_customer_id = customer.id
                request.user.save(update_fields=["stripe_customer_id"])

            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=int(token_package.price * 100),  # Convert to cents
                currency=token_package.currency.lower(),
                customer=request.user.stripe_customer_id,
                metadata={
                    "user_id": str(request.user.id),
                    "token_package_id": str(token_package.id),
                    "token_amount": token_package.token_amount,
                },
                description=f"Purchase of {token_package.name} ({token_package.token_amount} tokens)",
            )

            # Create pending payment record
            payment = Payment.objects.create(
                user=request.user,
                token_package=token_package,
                amount=token_package.price,
                currency=token_package.currency,
                payment_method="card",
                token_amount=token_package.token_amount,
                status="pending",
                stripe_payment_intent_id=payment_intent.id,
                description=f"Purchase of {token_package.name}",
            )

            return Response({
                "client_secret": payment_intent.client_secret,
                "payment_id": payment.id,
            }, status=status.HTTP_200_OK)

        except TokenPackage.DoesNotExist:
            return Response(
                {"error": "Token package not found or not active"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return Response(
                {"error": "An error occurred while processing your request"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ConfirmPaymentView(APIView):
    """
    View for confirming a payment after Stripe payment is complete.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=ConfirmPaymentSerializer,
        responses={200: "Payment confirmed", 400: "Invalid payment"},
        operation_description="Confirm payment after Stripe payment is complete.",
    )
    def post(self, request):
        """
        Confirm payment after Stripe payment is complete.
        """
        serializer = ConfirmPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Get payment intent
            payment_intent_id = serializer.validated_data["payment_intent_id"]
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # Check payment status
            if payment_intent.status != "succeeded":
                return Response(
                    {"error": "Payment has not been completed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get payment record
            payment = Payment.objects.filter(
                stripe_payment_intent_id=payment_intent_id,
                user=request.user,
                status="pending",
            ).first()

            if not payment:
                return Response(
                    {"error": "Payment not found or already processed"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Process payment with transaction
            with transaction.atomic():
                # Update payment record
                payment.status = "completed"
                payment.stripe_charge_id = payment_intent.charges.data[0].id if payment_intent.charges.data else None
                payment.updated_at = timezone.now()
                payment.save()

                # Update user balance
                user = request.user
                balance_before = user.balance
                user.balance += payment.token_amount
                user.save(update_fields=["balance"])

                # Create transaction record
                Transaction.objects.create(
                    user=user,
                    transaction_type="purchase",
                    amount=payment.token_amount,
                    balance_before=balance_before,
                    balance_after=user.balance,
                    description=f"Purchase of {payment.token_amount} tokens",
                    reference_id=str(payment.id),
                )

                # Generate invoice
                invoice = Invoice.objects.create(
                    user=user,
                    payment=payment,
                    invoice_number=f"INV-{payment.id.hex[:8].upper()}",
                    invoice_date=timezone.now().date(),
                    due_date=timezone.now().date(),
                    status="paid",
                    billing_name=f"{user.first_name} {user.last_name}",
                    billing_address=user.address or "",
                    billing_email=user.email,
                )

                logger.info(f"Payment completed for user {user.email}, added {payment.token_amount} tokens")

            return Response({
                "message": "Payment confirmed successfully",
                "payment": PaymentSerializer(payment).data,
                "new_balance": user.balance,
            }, status=status.HTTP_200_OK)

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error during payment confirmation: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            return Response(
                {"error": "An error occurred while confirming your payment"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StripeWebhookView(APIView):
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
        
        if not sig_header:
            return Response(
                {"error": "Stripe signature header is missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
            
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            
            # Process different webhook events
            if event.type == "payment_intent.succeeded":
                self._handle_payment_intent_succeeded(event.data.object)
            elif event.type == "payment_intent.payment_failed":
                self._handle_payment_intent_failed(event.data.object)
            
            return Response({"status": "success"}, status=status.HTTP_200_OK)
            
        except stripe.error.SignatureVerificationError:
            return Response(
                {"error": "Invalid signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return Response(
                {"error": "An error occurred while processing the webhook"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    def _handle_payment_intent_succeeded(self, payment_intent):
        """
        Handle a payment_intent.succeeded event.
        """
        try:
            # Get payment record
            payment = Payment.objects.filter(
                stripe_payment_intent_id=payment_intent.id,
                status="pending",
            ).first()
            
            if not payment:
                logger.warning(f"Payment not found for intent {payment_intent.id} or already processed")
                return
                
            # Process payment with transaction
            with transaction.atomic():
                # Update payment record
                payment.status = "completed"
                payment.stripe_charge_id = payment_intent.charges.data[0].id if payment_intent.charges.data else None
                payment.updated_at = timezone.now()
                payment.save()
                
                # Update user balance
                user = payment.user
                balance_before = user.balance
                user.balance += payment.token_amount
                user.save(update_fields=["balance"])
                
                # Create transaction record
                Transaction.objects.create(
                    user=user,
                    transaction_type="purchase",
                    amount=payment.token_amount,
                    balance_before=balance_before,
                    balance_after=user.balance,
                    description=f"Purchase of {payment.token_amount} tokens",
                    reference_id=str(payment.id),
                )
                
                # Generate invoice
                invoice = Invoice.objects.create(
                    user=user,
                    payment=payment,
                    invoice_number=f"INV-{payment.id.hex[:8].upper()}",
                    invoice_date=timezone.now().date(),
                    due_date=timezone.now().date(),
                    status="paid",
                    billing_name=f"{user.first_name} {user.last_name}",
                    billing_address=user.address or "",
                    billing_email=user.email,
                )
                
                logger.info(f"Payment completed via webhook for user {user.email}, added {payment.token_amount} tokens")
                
        except Exception as e:
            logger.error(f"Error processing payment_intent.succeeded webhook: {str(e)}")
            raise
    
    def _handle_payment_intent_failed(self, payment_intent):
        """
        Handle a payment_intent.payment_failed event.
        """
        try:
            # Get payment record
            payment = Payment.objects.filter(
                stripe_payment_intent_id=payment_intent.id,
                status="pending",
            ).first()
            
            if not payment:
                logger.warning(f"Payment not found for intent {payment_intent.id} or already processed")
                return
                
            # Update payment record
            payment.status = "failed"
            payment.updated_at = timezone.now()
            payment.save()
            
            logger.info(f"Payment failed for user {payment.user.email}")
            
        except Exception as e:
            logger.error(f"Error processing payment_intent.payment_failed webhook: {str(e)}")
            raise