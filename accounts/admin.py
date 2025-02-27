"""
Admin configuration for the accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, UserVerification, Transaction


class UserAdmin(BaseUserAdmin):
    """
    Custom admin for the User model.
    """
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_verified', 'balance', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_verified')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login', 'stripe_customer_id')
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name', 'phone_number', 'date_of_birth')}),
        (_('Address'), {'fields': ('address', 'city', 'state', 'postal_code', 'country')}),
        (_('Balance'), {'fields': ('balance',)}),
        (_('Integration'), {'fields': ('stripe_customer_id',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_verified', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )


class UserVerificationAdmin(admin.ModelAdmin):
    """
    Admin for the UserVerification model.
    """
    list_display = ('user', 'token', 'created_at', 'expires_at', 'is_used')
    list_filter = ('is_used',)
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('token', 'created_at')


class TransactionAdmin(admin.ModelAdmin):
    """
    Admin for the Transaction model.
    """
    list_display = ('user', 'transaction_type', 'amount', 'balance_before', 'balance_after', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__email', 'user__username', 'description', 'reference_id')
    readonly_fields = ('created_at',)


# Register models
admin.site.register(User, UserAdmin)
admin.site.register(UserVerification, UserVerificationAdmin)
admin.site.register(Transaction, TransactionAdmin)