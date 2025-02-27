"""
Signals for the payments app.
"""

import logging
import stripe
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import TokenPackage
from .services.stripe_service import StripeService

logger = logging.getLogger(__name__)

# Configure Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY


@receiver(post_save, sender=TokenPackage)
def create_stripe_product_price(sender, instance, created, **kwargs):
    """
    Create Stripe product and price when a token package is created.
    """
    if created and not instance.stripe_product_id and not instance.stripe_price_id:
        try:
            # Create product and price in Stripe
            product_id, price_id = StripeService.create_product_and_price(instance)

            # Update token package with Stripe IDs
            instance.stripe_product_id = product_id
            instance.stripe_price_id = price_id
            instance.save(update_fields=["stripe_product_id", "stripe_price_id"])

            logger.info(f"Created Stripe product and price for token package {instance.name}")

        except Exception as e:
            logger.error(
                f"Failed to create Stripe product and price for token package {instance.name}: {str(e)}"
            )