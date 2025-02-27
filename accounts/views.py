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

from rest_framework import status, viewsets, generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import UserVerification
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    CustomTokenObtainPairSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user accounts.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """
        Return appropriate serializer class.
        """
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        """
        Instantiate and return the list of permissions that this view requires.
        """
        if self.action == "create" or self.action == "verify_email":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """
        Return the queryset based on user permissions.
        """
        user = self.request.user

        if user.is_staff:
            return User.objects.all()

        # Regular users can only see their own data
        return User.objects.filter(id=user.id)

    @swagger_auto_schema(
        responses={201: UserSerializer()},
        request_body=UserCreateSerializer,
        operation_description="Register a new user account.",
    )
    def create(self, request, *args, **kwargs):
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

    @swagger_auto_schema(
        method="post",
        responses={200: "Email verified successfully", 400: "Invalid token"},
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
        operation_description="Verify user email address with token.",
    )
    @action(detail=False, methods=["post"], url_path="verify-email")
    def verify_email(self, request):
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

    @swagger_auto_schema(
        method="post",
        responses={200: "Password changed successfully", 400: "Invalid password"},
        request_body=PasswordChangeSerializer,
        operation_description="Change user password.",
    )
    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        """
        Change user password.
        """
        user = request.user
        serializer = PasswordChangeSerializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            if not user.check_password(serializer.validated_data["old_password"]):
                return Response(
                    {"old_password": ["Wrong password."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Set new password
            user.set_password(serializer.validated_data["new_password"])
            user.save()

            return Response(
                {"message": "Password changed successfully"}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        method="get",
        responses={200: UserSerializer()},
        operation_description="Get the profile of the current user.",
    )
    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """
        Get the profile of the current user.
        """
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @swagger_auto_schema(
        method="post",
        responses={200: "Password reset email sent", 400: "Invalid email"},
        request_body=PasswordResetRequestSerializer,
        operation_description="Request a password reset.",
    )
    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def request_password_reset(self, request):
        """
        Request a password reset.
        """
        serializer = PasswordResetRequestSerializer(data=request.data)

        if serializer.is_valid():
            email = serializer.validated_data["email"]

            try:
                user = User.objects.get(email=email)

                # Create reset token
                expiration = timezone.now() + timedelta(hours=24)
                verification = UserVerification.objects.create(
                    user=user, expires_at=expiration
                )

                # Send reset email
                self._send_password_reset_email(user, verification.token)

                return Response(
                    {"message": "Password reset email sent if the email exists"},
                    status=status.HTTP_200_OK,
                )
            except User.DoesNotExist:
                # Return success even if user doesn't exist for security
                return Response(
                    {"message": "Password reset email sent if the email exists"},
                    status=status.HTTP_200_OK,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        method="post",
        responses={200: "Password reset successful", 400: "Invalid token or password"},
        request_body=PasswordResetConfirmSerializer,
        operation_description="Confirm password reset with token.",
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        url_path="reset-password-confirm",
    )
    def reset_password_confirm(self, request):
        """
        Confirm password reset with token.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)

        if serializer.is_valid():
            token = serializer.validated_data["token"]

            try:
                verification = UserVerification.objects.filter(
                    token=token, is_used=False, expires_at__gt=timezone.now()
                ).first()

                if not verification:
                    return Response(
                        {"error": "Invalid or expired token"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Reset password
                user = verification.user
                user.set_password(serializer.validated_data["new_password"])
                user.save()

                # Mark token as used
                verification.is_used = True
                verification.save()

                return Response(
                    {"message": "Password reset successfully"},
                    status=status.HTTP_200_OK,
                )

            except Exception as e:
                logger.error(f"Password reset error: {str(e)}")
                return Response(
                    {"error": "An error occurred during password reset"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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

    def _send_password_reset_email(self, user, token):
        """
        Send password reset email to user.
        """
        try:
            reset_url = f"https://scraping.co.il/reset-password?token={token}"

            message = f"""
            Hello {user.first_name},
            
            We received a request to reset your password. Click the link below to reset your password:
            
            {reset_url}
            
            This link will expire in 24 hours. If you didn't request a password reset, please ignore this email.
            
            Best regards,
            The Scraping.co.il Team
            """

            send_mail(
                "Reset your password - Scraping.co.il",
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            logger.info(f"Password reset email sent to {user.email}")

        except Exception as e:
            logger.error(
                f"Failed to send password reset email to {user.email}: {str(e)}"
            )


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view that returns user data with tokens.
    """

    serializer_class = CustomTokenObtainPairSerializer
