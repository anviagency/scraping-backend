"""
Service for interacting with the Stripe API.
"""

import logging
import stripe
from django.conf import settings
from django.utils import timezone
from datetime import datetime

from accounts.models import User
from payments.models import Plan, Subscription, Payment, Invoice

logger = logging.getLogger(__name__)

# Configure Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """
    Service for interacting with the Stripe API.
    """

    @staticmethod
    def create_product_and_price(plan):
        """
        Create a product and price in Stripe for a plan.

        Args:
            plan: Plan model instance

        Returns:
            tuple: (stripe_product_id, stripe_price_id)
        """
        try:
            # Create product
            product = stripe.Product.create(
                name=plan.name,
                description=plan.description,
                metadata={"plan_id": str(plan.id)},
            )

            # Create price
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(plan.price * 100),  # Convert to cents
                currency=plan.currency.lower(),
                recurring={
                    "interval": plan.interval,
                },
                metadata={"plan_id": str(plan.id)},
            )

            return product.id, price.id

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating product and price: {str(e)}")
            raise

    @staticmethod
    def create_subscription(user, plan, payment_method_id, coupon=None):
        """
        Create a subscription in Stripe.

        Args:
            user: User model instance
            plan: Plan model instance
            payment_method_id: Stripe payment method ID
            coupon: Optional coupon code

        Returns:
            stripe.Subscription: Stripe subscription object
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

            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id, customer=user.stripe_customer_id
            )

            # Set as default payment method
            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={"default_payment_method": payment_method_id},
            )

            # Create subscription
            subscription_data = {
                "customer": user.stripe_customer_id,
                "items": [{"price": plan.stripe_price_id}],
                "default_payment_method": payment_method_id,
                "metadata": {"user_id": str(user.id), "plan_id": str(plan.id)},
                "expand": ["latest_invoice.payment_intent"],
            }

            # Add coupon if provided
            if coupon:
                subscription_data["coupon"] = coupon

            # Create the subscription
            stripe_subscription = stripe.Subscription.create(**subscription_data)

            return stripe_subscription

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating subscription: {str(e)}")
            raise

    @staticmethod
    def cancel_subscription(subscription, at_period_end=True):
        """
        Cancel a subscription in Stripe.

        Args:
            subscription: Subscription model instance
            at_period_end: Whether to cancel at the end of the billing period

        Returns:
            stripe.Subscription: Updated Stripe subscription object
        """
        try:
            stripe_subscription = stripe.Subscription.modify(
                subscription.stripe_subscription_id, cancel_at_period_end=at_period_end
            )

            if not at_period_end:
                stripe_subscription = stripe.Subscription.delete(
                    subscription.stripe_subscription_id
                )

            return stripe_subscription

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error cancelling subscription: {str(e)}")
            raise

    @staticmethod
    def update_payment_method(user, payment_method_id):
        """
        Update the default payment method for a customer.

        Args:
            user: User model instance
            payment_method_id: New Stripe payment method ID

        Returns:
            stripe.Customer: Updated Stripe customer object
        """
        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id, customer=user.stripe_customer_id
            )

            # Set as default payment method
            customer = stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={"default_payment_method": payment_method_id},
            )

            return customer

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error updating payment method: {str(e)}")
            raise

    @staticmethod
    def create_checkout_session(user, plan, success_url, cancel_url):
        """
        Create a Stripe checkout session for subscription.

        Args:
            user: User model instance
            plan: Plan model instance
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
                        "price": plan.stripe_price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"user_id": str(user.id), "plan_id": str(plan.id)},
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

            # Handle the event
            if event["type"] == "customer.subscription.created":
                StripeService._handle_subscription_created(event)
            elif event["type"] == "customer.subscription.updated":
                StripeService._handle_subscription_updated(event)
            elif event["type"] == "customer.subscription.deleted":
                StripeService._handle_subscription_deleted(event)
            elif event["type"] == "invoice.payment_succeeded":
                StripeService._handle_payment_succeeded(event)
            elif event["type"] == "invoice.payment_failed":
                StripeService._handle_payment_failed(event)

            return {"status": "success", "event_type": event["type"]}

        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}")
            raise

    @staticmethod
    def _handle_subscription_created(event):
        """
        Handle a subscription.created event.
        """
        subscription_data = event["data"]["object"]
        user_id = subscription_data["metadata"].get("user_id")
        plan_id = subscription_data["metadata"].get("plan_id")

        try:
            user = User.objects.get(id=user_id)
            plan = Plan.objects.get(id=plan_id)

            # Create subscription record
            start_date = datetime.fromtimestamp(
                subscription_data["current_period_start"]
            )
            end_date = datetime.fromtimestamp(subscription_data["current_period_end"])
            trial_end = None
            if subscription_data.get("trial_end"):
                trial_end = datetime.fromtimestamp(subscription_data["trial_end"])

            Subscription.objects.create(
                user=user,
                plan=plan,
                status=subscription_data["status"],
                start_date=start_date,
                end_date=end_date,
                trial_end=trial_end,
                stripe_subscription_id=subscription_data["id"],
            )

            logger.info(
                f"Created subscription for user {user.email} to plan {plan.name}"
            )

        except User.DoesNotExist:
            logger.error(f"User not found for subscription: {user_id}")
        except Plan.DoesNotExist:
            logger.error(f"Plan not found for subscription: {plan_id}")
        except Exception as e:
            logger.error(f"Error creating subscription record: {str(e)}")

    @staticmethod
    def _handle_subscription_updated(event):
        """
        Handle a subscription.updated event.
        """
        subscription_data = event["data"]["object"]

        try:
            subscription = Subscription.objects.get(
                stripe_subscription_id=subscription_data["id"]
            )

            # Update subscription record
            subscription.status = subscription_data["status"]
            subscription.end_date = datetime.fromtimestamp(
                subscription_data["current_period_end"]
            )

            if subscription_data.get("trial_end"):
                subscription.trial_end = datetime.fromtimestamp(
                    subscription_data["trial_end"]
                )

            subscription.save()

            logger.info(
                f"Updated subscription {subscription.id} status to {subscription.status}"
            )

        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found: {subscription_data['id']}")
        except Exception as e:
            logger.error(f"Error updating subscription: {str(e)}")

    @staticmethod
    def _handle_subscription_deleted(event):
        """
        Handle a subscription.deleted event.
        """
        subscription_data = event["data"]["object"]

        try:
            subscription = Subscription.objects.get(
                stripe_subscription_id=subscription_data["id"]
            )

            # Update subscription record
            subscription.status = "canceled"
            subscription.end_date = datetime.fromtimestamp(
                subscription_data["ended_at"] or subscription_data["current_period_end"]
            )
            subscription.save()

            logger.info(f"Subscription {subscription.id} cancelled")

        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found: {subscription_data['id']}")
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")

    @staticmethod
    def _handle_payment_succeeded(event):
        """
        Handle an invoice.payment_succeeded event.
        """
        invoice_data = event["data"]["object"]

        try:
            # Get subscription
            subscription = None
            if invoice_data.get("subscription"):
                subscription = Subscription.objects.filter(
                    stripe_subscription_id=invoice_data["subscription"]
                ).first()

            # Get or create user
            user = User.objects.get(stripe_customer_id=invoice_data["customer"])

            # Create payment record
            payment = Payment.objects.create(
                user=user,
                subscription=subscription,
                amount=invoice_data["amount_paid"] / 100,  # Convert from cents
                currency=invoice_data["currency"].upper(),
                payment_method="card",  # Default, could be updated later
                payment_type="subscription" if subscription else "one_time",
                status="completed",
                stripe_payment_intent_id=invoice_data["payment_intent"],
                description=f"Invoice {invoice_data['number']}",
                metadata={
                    "invoice_id": invoice_data["id"],
                    "invoice_number": invoice_data["number"],
                },
            )

            # Create invoice record
            Invoice.objects.create(
                user=user,
                payment=payment,
                invoice_number=invoice_data["number"],
                invoice_date=datetime.fromtimestamp(invoice_data["created"]),
                due_date=datetime.fromtimestamp(
                    invoice_data["due_date"] or invoice_data["created"]
                ),
                status=invoice_data["status"],
                billing_name=f"{user.first_name} {user.last_name}",
                billing_email=user.email,
                billing_address=user.address or "",
                stripe_invoice_id=invoice_data["id"],
                pdf_url=invoice_data["invoice_pdf"],
            )

            logger.info(f"Payment recorded for invoice {invoice_data['number']}")

        except User.DoesNotExist:
            logger.error(f"User not found for customer: {invoice_data['customer']}")
        except Exception as e:
            logger.error(f"Error recording payment: {str(e)}")

    @staticmethod
    def _handle_payment_failed(event):
        """
        Handle an invoice.payment_failed event.
        """
        invoice_data = event["data"]["object"]

        try:
            # Get subscription
            subscription = None
            if invoice_data.get("subscription"):
                subscription = Subscription.objects.filter(
                    stripe_subscription_id=invoice_data["subscription"]
                ).first()

                if subscription:
                    # Update subscription status
                    subscription.status = "past_due"
                    subscription.save()

            # Get user
            user = User.objects.get(stripe_customer_id=invoice_data["customer"])

            # Create payment record for failed payment
            Payment.objects.create(
                user=user,
                subscription=subscription,
                amount=invoice_data["amount_due"] / 100,  # Convert from cents
                currency=invoice_data["currency"].upper(),
                payment_method="card",  # Default
                payment_type="subscription" if subscription else "one_time",
                status="failed",
                stripe_payment_intent_id=invoice_data.get("payment_intent"),
                description=f"Failed payment for invoice {invoice_data['number']}",
                metadata={
                    "invoice_id": invoice_data["id"],
                    "invoice_number": invoice_data["number"],
                    "failure_message": invoice_data.get("failure_message", ""),
                },
            )

            logger.info(f"Failed payment recorded for invoice {invoice_data['number']}")

        except User.DoesNotExist:
            logger.error(f"User not found for customer: {invoice_data['customer']}")
        except Exception as e:
            logger.error(f"Error recording failed payment: {str(e)}")
