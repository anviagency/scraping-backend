"""
Signals for the accounts app.
"""

import logging
import stripe
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

# Configure Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY


@receiver(post_save, sender=User)
def create_stripe_customer(sender, instance, created, **kwargs):
    """
    Create a Stripe customer when a new user is created.
    """
    if created and not instance.stripe_customer_id:
        try:
            # Create a customer in Stripe
            customer = stripe.Customer.create(
                email=instance.email,
                name=f"{instance.first_name} {instance.last_name}",
                phone=instance.phone_number,
                metadata={
                    "user_id": str(instance.id),
                    "username": instance.username,
                },
            )

            # Update user with Stripe customer ID
            instance.stripe_customer_id = customer.id
            instance.save(update_fields=["stripe_customer_id"])

            logger.info(
                f"Created Stripe customer for user {instance.email}: {customer.id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to create Stripe customer for user {instance.email}: {str(e)}"
            )
