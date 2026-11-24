"""
Optional self-service registration.

Disabled by default (ENABLE_REGISTRATION). Because chronoq executes
user-supplied URLs on a schedule, opening signup widens who can schedule
outbound calls — so it's a deliberate, env-gated choice, and it only belongs
on alongside the SSRF guard (see jobs.validators). New accounts are regular
(non-staff) users; admins are provisioned separately. The endpoint rides the
tight "login" throttle scope and enforces Django's password validators.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("That username is taken.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class RegisterView(APIView):
    """POST {username, password, email?} -> 201 {token, username}. 403 when off."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"  # reuse the tight auth-endpoint limit

    def post(self, request):
        if not settings.ENABLE_REGISTRATION:
            return Response(
                {"detail": "Registration is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "username": user.username},
            status=status.HTTP_201_CREATED,
        )


class RegistrationConfigView(APIView):
    """Public: lets the SPA show the 'Create account' link only when enabled."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"registration_enabled": settings.ENABLE_REGISTRATION})
