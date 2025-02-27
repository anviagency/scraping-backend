"""
Signals for the payments app.
"""

import logging
import stripe
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings

from .models import Plan, Subscription
from .services.stripe_service import StripeService

logger = logging.getLogger(__name__)

# Configure Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY


@receiver(post_save, sender=Plan)
def create_stripe_product_price(sender, instance, created, **kwargs):
    """
    Create Stripe product and price when a plan is created.
    """
    if created and not instance.stripe_product_id and not instance.stripe_price_id:
        try:
            # Create product and price in Stripe
            product_id, price_id = StripeService.create_product_and_price(instance)

            # Update plan with Stripe IDs
            instance.stripe_product_id = product_id
            instance.stripe_price_id = price_id
            instance.save(update_fields=["stripe_product_id", "stripe_price_id"])

            logger.info(f"Created Stripe product and price for plan {instance.name}")

        except Exception as e:
            logger.error(
                f"Failed to create Stripe product and price for plan {instance.name}: {str(e)}"
            )


@receiver(pre_save, sender=Subscription)
def update_subscription_usage(sender, instance, **kwargs):
    """
    Update usage statistics if subscription already exists.
    """
    if instance.pk:
        try:
            # Get old subscription data
            old_subscription = Subscription.objects.get(pk=instance.pk)

            # If subscription status changed to cancelled
            if old_subscription.status != "canceled" and instance.status == "canceled":
                logger.info(f"Subscription {instance.pk} status changed to canceled")

                # You could add additional logic here if needed

        except Subscription.DoesNotExist:
            pass
