"""
URL configuration for the API app.
"""

from django.urls import path, include

urlpatterns = [
    # Include app-specific URLs
    path('auth/', include('accounts.urls')),
    path('payments/', include('payments.urls')),
]