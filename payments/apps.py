"""
AppConfig for the payments app.
"""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """
    Configuration for the payments app.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"

    def ready(self):
        """
        Import signals when the app is ready.
        """
        import payments.signals  # noqa
