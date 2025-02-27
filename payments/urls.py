from django.urls import path
from .views import (
    TokenPackageListView, 
    PaymentHistoryView, 
    CreatePaymentIntentView, 
    ConfirmPaymentView,
    StripeWebhookView
)

urlpatterns = [
    # Token packages
    path('token-packages/', TokenPackageListView.as_view(), name='token-packages'),
    
    # Payments
    path('history/', PaymentHistoryView.as_view(), name='payment-history'),
    path('create-payment-intent/', CreatePaymentIntentView.as_view(), name='create-payment-intent'),
    path('confirm-payment/', ConfirmPaymentView.as_view(), name='confirm-payment'),
    
    # Webhook
    path('webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
]