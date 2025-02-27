"""
Service for interacting with the Stripe API.
"""

import logging
import stripe
from django.conf import settings
from django.utils import timezone
from datetime import datetime

logger = logging.getLogger(__name__)

# Configure Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """
    Service for interacting with the Stripe API.
    """

    @staticmethod
    def create_product_and_price(token_package):
        """
        Create a product and price in Stripe for a token package.

        Args:
            token_package: TokenPackage model instance

        Returns:
            tuple: (stripe_product_id, stripe_price_id)
        """
        try:
            # Create product
            product = stripe.Product.create(
                name=token_package.name,
                description=token_package.description or f"{token_package.token_amount} tokens",
                metadata={"token_package_id": str(token_package.id)},
            )

            # Create price
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(token_package.price * 100),  # Convert to cents
                currency=token_package.currency.lower(),
                metadata={"token_package_id": str(token_package.id)},
            )

            return product.id, price.id

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating product and price: {str(e)}")
            raise

    @staticmethod
    def create_payment_intent(user, token_package):
        """
        Create a payment intent in Stripe.

        Args:
            user: User model instance
            token_package: TokenPackage model instance

        Returns:
            stripe.PaymentIntent: Stripe payment intent object
        """
        try:
            # Ensure user has a Stripe customer ID
            if not user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=f"{user.first_name} {user.last_name}",
                    metadata={"user_id": str(user.id)},
                )
                user.stripe_customer_id = customer.id
                user.save(update_fields=["stripe_customer_id"])

            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=int(token_package.price * 100),  # Convert to cents
                currency=token_package.currency.lower(),
                customer=user.stripe_customer_id,
                metadata={
                    "user_id": str(user.id),
                    "token_package_id": str(token_package.id),
                    "token_amount": token_package.token_amount,
                },
                description=f"Purchase of {token_package.name} ({token_package.token_amount} tokens)",
            )

            return payment_intent

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise

    @staticmethod
    def create_checkout_session(user, token_package, success_url, cancel_url):
        """
        Create a Stripe checkout session for token purchase.

        Args:
            user: User model instance
            token_package: TokenPackage model instance
            success_url: URL to redirect to on success
            cancel_url: URL to redirect to on cancel

        Returns:
            stripe.checkout.Session: Checkout session object
        """
        try:
            # Ensure user has a Stripe customer ID
            if not user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=f"{user.first_name} {user.last_name}",
                    metadata={"user_id": str(user.id)},
                )
                user.stripe_customer_id = customer.id
                user.save(update_fields=["stripe_customer_id"])

            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=user.stripe_customer_id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": token_package.currency.lower(),
                            "product_data": {
                                "name": token_package.name,
                                "description": token_package.description or f"{token_package.token_amount} tokens",
                            },
                            "unit_amount": int(token_package.price * 100),
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user.id),
                    "token_package_id": str(token_package.id),
                    "token_amount": token_package.token_amount,
                },
            )

            return checkout_session

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {str(e)}")
            raise

    @staticmethod
    def handle_webhook_event(payload, sig_header):
        """
        Handle a webhook event from Stripe.

        Args:
            payload: Raw body of the webhook request
            sig_header: Stripe signature header

        Returns:
            dict: Processed webhook event data
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )

            # Handle the event based on type
            if event.type == "payment_intent.succeeded":
                logger.info(f"Payment intent succeeded: {event.data.object.id}")
            elif event.type == "payment_intent.payment_failed":
                logger.info(f"Payment intent failed: {event.data.object.id}")
            elif event.type == "checkout.session.completed":
                logger.info(f"Checkout session completed: {event.data.object.id}")

            return {"status": "success", "event_type": event.type}

        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}")
            raise