from rest_framework import serializers
from .models import TokenPackage, Payment, Invoice


class TokenPackageSerializer(serializers.ModelSerializer):
    """
    Serializer for the TokenPackage model.
    """
    class Meta:
        model = TokenPackage
        fields = [
            'id', 'name', 'description', 'token_amount', 
            'price', 'currency', 'is_active'
        ]
        read_only_fields = ['id']


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for the Payment model.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    package_details = TokenPackageSerializer(source='token_package', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'token_package', 'package_details',
            'amount', 'currency', 'payment_method', 'token_amount',
            'status', 'status_display', 'description', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for the Invoice model.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_details = PaymentSerializer(source='payment', read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'user', 'payment_details', 'invoice_number',
            'invoice_date', 'due_date', 'status', 'status_display',
            'billing_name', 'billing_address', 'billing_email',
            'pdf_url', 'created_at'
        ]
        read_only_fields = fields


class CreatePaymentIntentSerializer(serializers.Serializer):
    """
    Serializer for creating a Stripe payment intent.
    """
    token_package_id = serializers.UUIDField(required=True)


class ConfirmPaymentSerializer(serializers.Serializer):
    """
    Serializer for confirming a payment.
    """
    payment_intent_id = serializers.CharField(required=True)