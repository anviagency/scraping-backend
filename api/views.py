"""
Views for the API app in the Scraping-backend project.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions


class APIRootView(APIView):
    """
    Root API view that returns information about the API.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, format=None):
        """
        Return API information.
        """
        return Response(
            {
                "name": "Scraping.co.il API",
                "version": "1.0.0",
                "endpoints": {
                    "accounts": "/api/accounts/",
                    "payments": "/api/payments/",
                    "integrations": "/api/integrations/",
                    "docs": "/swagger/",
                },
            }
        )
