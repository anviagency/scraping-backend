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

# Stripe API keys
STRIPE_TEST_SECRET_KEY = settings.STRIPE_TEST_SECRET_KEY
STRIPE_LIVE_SECRET_KEY = settings.STRIPE_SECRET_KEY

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
            # Check if this is a test mode request
            test_mode = request.data.get('test_mode', False)
            
            # Configure Stripe with the appropriate key
            if test_mode:
                stripe.api_key = STRIPE_TEST_SECRET_KEY
                logger.info("Using Stripe TEST mode")
            else:
                stripe.api_key = STRIPE_LIVE_SECRET_KEY
                logger.info("Using Stripe LIVE mode")
            
            # Handle custom package
            is_custom = request.data.get('is_custom', False)
            
            if is_custom:
                # Create a custom package or get the generic one
                try:
                    # Try to use the provided token_package_id first
                    token_package_id = serializer.validated_data.get("token_package_id")
                    
                    # Check if the custom package already exists
                    token_package = TokenPackage.objects.filter(id=token_package_id).first()
                    
                    if not token_package:
                        # Create a new custom package
                        token_package = TokenPackage.objects.create(
                            id=token_package_id,
                            name="חבילה מותאמת אישית",
                            token_amount=request.data.get('token_amount', 1000),
                            price=request.data.get('price', 100),
                            currency=request.data.get('currency', 'ILS'),
                            is_active=True
                        )
                        logger.info(f"Created custom token package: {token_package.id}")
                    else:
                        # Update existing package with new values
                        token_package.token_amount = request.data.get('token_amount', token_package.token_amount)
                        token_package.price = request.data.get('price', token_package.price)
                        token_package.save()
                        logger.info(f"Updated custom token package: {token_package.id}")
                    
                except Exception as e:
                    logger.error(f"Error creating custom package: {str(e)}")
                    return Response(
                        {"error": f"Failed to create custom package: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                # Get the standard token package
                try:
                    token_package_id = serializer.validated_data["token_package_id"]
                    token_package = TokenPackage.objects.get(
                        id=token_package_id,
                        is_active=True
                    )
                    logger.info(f"Found token package: {token_package.name}")
                except TokenPackage.DoesNotExist:
                    return Response(
                        {"error": "Token package not found or not active"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # Ensure user has a Stripe customer ID
            if not request.user.stripe_customer_id:
                logger.info(f"Creating Stripe customer for user {request.user.email}")
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=f"{request.user.first_name} {request.user.last_name}",
                    metadata={
                        "user_id": str(request.user.id),
                        "test_mode": "true" if test_mode else "false"
                    },
                )
                request.user.stripe_customer_id = customer.id
                request.user.save(update_fields=["stripe_customer_id"])
            
            # Create metadata for the payment intent
            metadata = {
                "user_id": str(request.user.id),
                "token_package_id": str(token_package.id),
                "token_amount": token_package.token_amount,
                "test_mode": "true" if test_mode else "false",
                "is_custom": "true" if is_custom else "false"
            }
            
            # Decide whether to use Payment Intent or Checkout Session
            use_checkout = request.data.get('use_checkout', False)
            
            if use_checkout:
                # Create a Checkout Session (redirect flow)
                success_url = request.build_absolute_uri('/credits/checkout?payment_status=success&payment_intent={CHECKOUT_SESSION_ID}')
                cancel_url = request.build_absolute_uri('/credits/checkout?payment_status=canceled')
                
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': token_package.currency.lower(),
                            'product_data': {
                                'name': token_package.name,
                                'description': f"{token_package.token_amount} קרדיטים",
                            },
                            'unit_amount': int(float(token_package.price) * 100),  # Convert to cents
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=success_url,
                    cancel_url=cancel_url,
                    customer=request.user.stripe_customer_id,
                    metadata=metadata,
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
                    stripe_payment_intent_id=checkout_session.id,
                    description=f"Purchase of {token_package.name}",
                    metadata={"test_mode": test_mode, "is_custom": is_custom}
                )
                
                return Response({
                    "checkout_url": checkout_session.url,
                    "payment_id": payment.id,
                }, status=status.HTTP_200_OK)
            
            else:
                # Create payment intent (for Elements integration)
                payment_intent = stripe.PaymentIntent.create(
                    amount=int(float(token_package.price) * 100),  # Convert to cents
                    currency=token_package.currency.lower(),
                    customer=request.user.stripe_customer_id,
                    metadata=metadata,
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
                    metadata={"test_mode": test_mode, "is_custom": is_custom}
                )
                
                # Create simulated checkout URL for test mode
                checkout_url = None
                if test_mode:
                    checkout_url = f"/credits/checkout?payment_status=success&payment_intent={payment_intent.id}"
                
                return Response({
                    "client_secret": payment_intent.client_secret,
                    "payment_id": payment.id,
                    "checkout_url": checkout_url,
                }, status=status.HTTP_200_OK)

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
            # Get payment intent ID
            payment_intent_id = serializer.validated_data["payment_intent_id"]
            
            # Look up the payment first to determine test mode
            payment = Payment.objects.filter(
                stripe_payment_intent_id=payment_intent_id,
                status="pending",
            ).first()
            
            if not payment:
                return Response(
                    {"error": "Payment not found or already processed"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Check if this was a test mode payment
            test_mode = payment.metadata.get('test_mode', False)
            
            # Configure Stripe with the appropriate key
            if test_mode:
                stripe.api_key = STRIPE_TEST_SECRET_KEY
                logger.info("Using Stripe TEST mode for confirmation")
            else:
                stripe.api_key = STRIPE_LIVE_SECRET_KEY
                logger.info("Using Stripe LIVE mode for confirmation")
            
            # Check if payment is a Checkout Session
            if payment_intent_id.startswith('cs_'):
                # Retrieve Checkout Session
                checkout_session = stripe.checkout.Session.retrieve(payment_intent_id)
                
                # Check payment status
                if checkout_session.payment_status != "paid":
                    return Response(
                        {"error": "Payment has not been completed"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                    
                # Get associated payment intent for charge ID
                payment_intent_id = checkout_session.payment_intent
                
            # Get payment intent to check its status
            if payment_intent_id:
                try:
                    payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                    
                    # Check payment status
                    if payment_intent.status != "succeeded":
                        # For test mode, allow confirmation without checking Stripe
                        if not test_mode:
                            return Response(
                                {"error": "Payment has not been completed"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                except stripe.error.StripeError as e:
                    logger.error(f"Error retrieving payment intent: {str(e)}")
                    # For test mode, continue even if Stripe call fails
                    if not test_mode:
                        return Response(
                            {"error": f"Error retrieving payment details: {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    payment_intent = None
            else:
                # For test mode, create a simulated payment intent
                payment_intent = None

            # Process payment with transaction
            with transaction.atomic():
                # Update payment record
                payment.status = "completed"
                if payment_intent and hasattr(payment_intent, 'charges') and payment_intent.charges.data:
                    payment.stripe_charge_id = payment_intent.charges.data[0].id
                payment.updated_at = timezone.now()
                payment.save()

                # Update user balance
                user = payment.user
                balance_before = user.balance
                user.balance += payment.token_amount
                user.save(update_fields=["balance"])

                # Create transaction record
                transaction_obj = Transaction.objects.create(
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
                "success": True,
                "message": "Payment confirmed successfully",
                "payment": PaymentSerializer(payment).data,
                "token_amount": payment.token_amount,
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
        
        # Check if this is a test webhook
        test_mode = 'test' in request.path.lower()
        
        # Configure Stripe with the appropriate key
        if test_mode:
            stripe.api_key = STRIPE_TEST_SECRET_KEY
            webhook_secret = settings.STRIPE_TEST_WEBHOOK_SECRET
            logger.info("Using Stripe TEST mode for webhook")
        else:
            stripe.api_key = STRIPE_LIVE_SECRET_KEY
            webhook_secret = settings.STRIPE_WEBHOOK_SECRET
            logger.info("Using Stripe LIVE mode for webhook")
            
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            # Process different webhook events
            if event.type == "payment_intent.succeeded":
                self._handle_payment_intent_succeeded(event.data.object, test_mode)
            elif event.type == "payment_intent.payment_failed":
                self._handle_payment_intent_failed(event.data.object, test_mode)
            elif event.type == "checkout.session.completed":
                self._handle_checkout_session_completed(event.data.object, test_mode)
            
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
    
    def _handle_payment_intent_succeeded(self, payment_intent, test_mode=False):
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
    
    def _handle_payment_intent_failed(self, payment_intent, test_mode=False):
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
    
    def _handle_checkout_session_completed(self, checkout_session, test_mode=False):
        """
        Handle a checkout.session.completed event.
        """
        try:
            # Get payment record (might be stored with checkout session ID or payment intent ID)
            payment = Payment.objects.filter(
                stripe_payment_intent_id__in=[checkout_session.id, checkout_session.payment_intent],
                status="pending",
            ).first()
            
            if not payment:
                logger.warning(f"Payment not found for checkout session {checkout_session.id} or already processed")
                return
                
            # Only process if payment was successful
            if checkout_session.payment_status != "paid":
                logger.warning(f"Checkout session {checkout_session.id} not paid")
                return
                
            # Process payment with transaction
            with transaction.atomic():
                # Update payment record
                payment.status = "completed"
                # If there was a payment intent, update the ID to make webhook handling consistent
                if checkout_session.payment_intent and payment.stripe_payment_intent_id != checkout_session.payment_intent:
                    payment.stripe_payment_intent_id = checkout_session.payment_intent
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
                
                logger.info(f"Payment completed via checkout session webhook for user {user.email}, added {payment.token_amount} tokens")
                
        except Exception as e:
            logger.error(f"Error processing checkout.session.completed webhook: {str(e)}")
            raise