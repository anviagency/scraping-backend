"""
URL configuration for the API app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

urlpatterns = [
    # Include app-specific URLs
    path('auth/', include('accounts.urls')),
    path('payments/', include('payments.urls')),
]