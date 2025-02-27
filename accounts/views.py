"""
Views for the accounts app in the Scraping-backend project.
For scraping.co.il
"""

import uuid
import logging
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import UserVerification, Transaction
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    CustomTokenObtainPairSerializer,
    TransactionSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    """
    View for user registration.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = UserCreateSerializer

    def post(self, request, *args, **kwargs):
        """
        Register a new user account.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Create verification token
        expiration = timezone.now() + timedelta(hours=24)
        verification = UserVerification.objects.create(user=user, expires_at=expiration)

        # Send verification email
        self._send_verification_email(user, verification.token)

        # Return user data
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def _send_verification_email(self, user, token):
        """
        Send verification email to user.
        """
        try:
            verification_url = f"https://scraping.co.il/verify-email?token={token}"

            message = f"""
            Hello {user.first_name},
            
            Thank you for registering with Scraping.co.il. Please verify your email address by clicking the link below:
            
            {verification_url}
            
            This link will expire in 24 hours.
            
            Best regards,
            The Scraping.co.il Team
            """

            send_mail(
                "Verify your email - Scraping.co.il",
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            logger.info(f"Verification email sent to {user.email}")

        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view that returns user data with tokens.
    """
    serializer_class = CustomTokenObtainPairSerializer


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View for retrieving and updating user profile.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """
        Return the authenticated user.
        """
        return self.request.user


class VerifyEmailView(APIView):
    """
    View for verifying email address.
    """
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "token",
                openapi.IN_QUERY,
                description="Verification token",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True,
            )
        ],
        responses={200: "Email verified successfully", 400: "Invalid token"},
        operation_description="Verify user email address with token.",
    )
    def get(self, request):
        """
        Verify user email with token.
        """
        token = request.query_params.get("token")
        if not token:
            return Response(
                {"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token_uuid = uuid.UUID(token)
            verification = UserVerification.objects.filter(
                token=token_uuid, is_used=False, expires_at__gt=timezone.now()
            ).first()

            if not verification:
                return Response(
                    {"error": "Invalid or expired token"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Mark user as verified
            user = verification.user
            user.is_verified = True
            user.save()

            # Mark token as used
            verification.is_used = True
            verification.save()

            return Response(
                {"message": "Email verified successfully"}, status=status.HTTP_200_OK
            )

        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid token format"}, status=status.HTTP_400_BAD_REQUEST
            )


class TransactionListView(generics.ListAPIView):
    """
    View for listing user transactions.
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return the queryset of transactions for the current user.
        """
        return Transaction.objects.filter(user=self.request.user)