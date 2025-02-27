"""
Admin configuration for the payments app.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import TokenPackage, Payment, Invoice


class TokenPackageAdmin(admin.ModelAdmin):
    """
    Admin interface for the TokenPackage model.
    """
    list_display = ('name', 'token_amount', 'price', 'currency', 'is_active', 'created_at')
    list_filter = ('is_active', 'currency', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'stripe_product_id', 'stripe_price_id')
    fieldsets = (
        (None, {'fields': ('name', 'description')}),
        (_('Tokens and Pricing'), {'fields': ('token_amount', 'price', 'currency')}),
        (_('Stripe'), {'fields': ('stripe_product_id', 'stripe_price_id')}),
        (_('Status'), {'fields': ('is_active',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


class PaymentAdmin(admin.ModelAdmin):
    """
    Admin interface for the Payment model.
    """
    list_display = ('id', 'user', 'token_package', 'amount', 'currency', 'token_amount', 'status', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('user__email', 'user__username', 'description')
    readonly_fields = ('created_at', 'updated_at', 'stripe_payment_intent_id', 'stripe_charge_id')
    fieldsets = (
        (None, {'fields': ('user', 'token_package')}),
        (_('Payment Details'), {'fields': ('amount', 'currency', 'payment_method', 'token_amount')}),
        (_('Status'), {'fields': ('status', 'description')}),
        (_('Stripe'), {'fields': ('stripe_payment_intent_id', 'stripe_charge_id')}),
        (_('Metadata'), {'fields': ('metadata',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


class InvoiceAdmin(admin.ModelAdmin):
    """
    Admin interface for the Invoice model.
    """
    list_display = ('invoice_number', 'user', 'status', 'invoice_date', 'due_date', 'created_at')
    list_filter = ('status', 'invoice_date', 'due_date')
    search_fields = ('user__email', 'user__username', 'invoice_number', 'billing_name', 'billing_email')
    readonly_fields = ('created_at', 'updated_at', 'stripe_invoice_id')
    fieldsets = (
        (None, {'fields': ('user', 'payment', 'invoice_number')}),
        (_('Dates'), {'fields': ('invoice_date', 'due_date')}),
        (_('Status'), {'fields': ('status',)}),
        (_('Billing Information'), {'fields': ('billing_name', 'billing_address', 'billing_email')}),
        (_('Stripe'), {'fields': ('stripe_invoice_id', 'pdf_url')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )


# Register models
admin.site.register(TokenPackage, TokenPackageAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Invoice, InvoiceAdmin)