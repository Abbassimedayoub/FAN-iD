"""
Serializers for the `identity` context.

Serializers validate input shape such as type, length, format, and presence.
Business rules such as age, consent, and uniqueness remain in services so they
apply consistently outside a single HTTP serializer.
"""

from __future__ import annotations

import datetime
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .constants import CLIENT_MOBILE, CLIENT_WEB, DEVICE_PLATFORMS
from .models import User


class RegistrationSerializer(serializers.Serializer):
    """Closed request body for registration, using Serializer rather than ModelSerializer so new model fields never become writable by default."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
    )
    # Obligatoires (AB-06). Un billet nominatif controle a l entree a besoin
    # Names have an identified use and whitespace trimming stays enabled here,
    # unlike password fields where trimming would change the secret.
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField()
    terms_accepted = serializers.BooleanField()
    phone = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate_date_of_birth(self, value: datetime.date) -> datetime.date:
        """Reject a future date as input-shape validation; minimum-age policy remains in the service."""
        if value > timezone.localdate():
            raise serializers.ValidationError("La date de naissance ne peut pas etre dans le futur.")
        return value

    def validate_password(self, value: str) -> str:
        """Run configured password validators with the candidate user context; password whitespace is never trimmed because that would change the secret."""
        # Seuls `username`, `first_name`, `last_name` et `email` sont lus par
        # `UserAttributeSimilarityValidator`. Passer `date_of_birth=None` ne
        # This field declaration also keeps the type checker aligned with DRF behavior.
        # `DateField` non nul.
        candidate = User(email=str(self.initial_data.get("email", "")))
        try:
            validate_password(value, user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class LoginSerializer(serializers.Serializer):
    """
    Request body for login.

    `client` chooses only refresh-token transport: HttpOnly cookie for web or
    response body for mobile. It is never trusted for authorization.
    `fingerprint` remains optional for clients that cannot provide a stable
    device identifier.
    """

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
    )
    client = serializers.ChoiceField(choices=[CLIENT_WEB, CLIENT_MOBILE])
    fingerprint = serializers.CharField(
        max_length=64,
        required=False,
        allow_null=True,
    )
    platform = serializers.ChoiceField(
        choices=list(DEVICE_PLATFORMS),
        required=False,
        allow_null=True,
    )

    # `label` intentionally shadows DRF Field.label at class declaration time;
    # renaming it would break the public API contract.
    # `label`), d ou l exception locale plutot qu un contournement global.
    label = serializers.CharField(  # type: ignore[assignment]
        max_length=60,
        required=False,
        allow_blank=True,
        default="",
    )


class RefreshSerializer(serializers.Serializer):
    """
    Corps de `POST /api/v1/auth/refresh`.

    **`client` ne sert pas qu a formater la reponse : il designe la SOURCE de
    lecture du jeton.** `web` lit le cookie et IGNORE le corps ; `mobile` lit le
    corps et IGNORE le cookie. Une source non declaree reste non lue, meme
    lorsqu elle porte un jeton parfaitement valide — c est ce qui empeche le
    cumul des deux transports interdit au lot S1-A.6c.

    `refresh` n est donc utile qu au client mobile. Le rendre obligatoire
    casserait le client web, dont le jeton n est pas dans le corps ; sa presence
    reelle est verifiee par la vue, seule a savoir quelle source elle doit lire.

    `fingerprint` est exigee des que la session porte un appareil. C est le
    service qui tranche, pas le serialiseur : la reponse depend de l etat de la
    session, pas de la forme du corps.
    """

    client = serializers.ChoiceField(choices=[CLIENT_WEB, CLIENT_MOBILE])
    # `max_length` bounds input before decoding so unauthenticated callers cannot
    # force signature verification on arbitrarily large bodies.
    # de plusieurs mega-octets. `trim_whitespace=False` parce qu un jeton n a
    # Do not trim whitespace because doing so would hide a malformed client token.
    refresh = serializers.CharField(max_length=4096, required=False, allow_blank=True, trim_whitespace=False)
    fingerprint = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)


class DeviceSerializer(serializers.Serializer):
    """Bound-device representation exposed to the client."""

    id = serializers.UUIDField(read_only=True)
    label = serializers.CharField(read_only=True)  # type: ignore[assignment]  # cf. LoginSerializer.label
    bound_at = serializers.DateTimeField(read_only=True)


class UserPublicSerializer(serializers.Serializer):
    """Closed user representation that exposes only client-relevant fields and the stable role name, never privilege flags or password data."""

    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    phone = serializers.CharField(
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )
    role = serializers.SerializerMethodField()
    must_change_password = serializers.BooleanField(
        read_only=True,
    )
    created_at = serializers.DateTimeField(read_only=True)

    def get_role(self, obj: Any) -> str:
        return str(obj.role.name)

    def to_representation(
        self,
        instance: Any,
    ) -> dict[str, Any]:
        data = super().to_representation(instance)

        if str(instance.role.name) != "SCANNER":
            data.pop(
                "must_change_password",
                None,
            )

        if str(instance.role.name) != "SCANNER":
            data.pop(
                "phone",
                None,
            )

        if str(instance.role.name) != "SCANNER":
            data.pop(
                "phone",
                None,
            )

        return data


class UserMeSerializer(serializers.Serializer):
    """Representation privee du profil de l utilisateur authentifie."""

    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True, allow_null=True, allow_blank=True)
    date_of_birth = serializers.DateField(
        read_only=True,
        allow_null=True,
    )
    role = serializers.SerializerMethodField()
    must_change_password = serializers.BooleanField(
        read_only=True,
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    version = serializers.IntegerField(read_only=True)

    def get_role(self, obj: Any) -> str:
        return str(obj.role.name)

    def to_representation(
        self,
        instance: Any,
    ) -> dict[str, Any]:
        data = super().to_representation(instance)

        if str(instance.role.name) != "SCANNER":
            data.pop(
                "must_change_password",
                None,
            )

        return data


class ProfileUpdateSerializer(serializers.Serializer):
    """Closed PATCH input for the current profile; privileged and identity-defining fields are not writable through this contract."""

    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class SessionSerializer(serializers.Serializer):
    """Session active visible uniquement par son proprietaire."""

    id = serializers.UUIDField(read_only=True)
    device = serializers.SerializerMethodField()
    ip = serializers.IPAddressField(read_only=True, allow_null=True)
    user_agent = serializers.CharField(read_only=True)
    issued_at = serializers.DateTimeField(read_only=True)
    last_used_at = serializers.DateTimeField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    current = serializers.SerializerMethodField()

    def get_device(self, obj: Any) -> dict[str, Any] | None:
        device = getattr(obj, "device", None)
        if device is None:
            return None
        return {
            "id": str(device.pk),
            "label": device.label,
        }

    def get_current(self, obj: Any) -> bool:
        request = self.context.get("request")
        current_session_id = getattr(request, "session_id", None)
        return current_session_id == obj.pk


class DeviceHistorySerializer(serializers.Serializer):
    """Device representation visible in self-service surfaces."""

    id = serializers.UUIDField(read_only=True)
    label = serializers.CharField(read_only=True)  # type: ignore[assignment]
    platform = serializers.CharField(read_only=True)
    bound_at = serializers.DateTimeField(read_only=True)
    last_seen_at = serializers.DateTimeField(read_only=True)
    revoked_at = serializers.DateTimeField(read_only=True, allow_null=True)
    revoked_reason = serializers.CharField(read_only=True, allow_null=True)


class DeviceMeResponseSerializer(serializers.Serializer):
    """Active device and recent history for the current account."""

    active = DeviceHistorySerializer(read_only=True, allow_null=True)
    history = DeviceHistorySerializer(many=True, read_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    """Password-change input validates password shape with the real user context; business checks remain in the service and password whitespace is never trimmed."""

    current_password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        """Applique `AUTH_PASSWORD_VALIDATORS` contre l utilisateur reel."""
        user = getattr(self.context.get("request"), "user", None)
        if not getattr(user, "is_authenticated", False):
            user = None
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    """Anonymous password-recovery request by email address."""

    email = serializers.EmailField(
        max_length=254,
    )


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Accept exactly one proof: a magic-link token or email plus manual fallback code."""

    token = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=2048,
        trim_whitespace=True,
    )

    email = serializers.EmailField(
        required=False,
        max_length=254,
    )

    code = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=16,
        trim_whitespace=True,
    )

    new_password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
    )

    def validate(
        self,
        attrs: dict,
    ) -> dict:
        has_token = bool(attrs.get("token"))

        has_email = bool(attrs.get("email"))

        has_code = bool(attrs.get("code"))

        manual_complete = has_email and has_code

        if has_token and (has_email or has_code):
            raise serializers.ValidationError(
                "Utilisez soit le lien magique, soit l’adresse e-mail et le code."
            )

        if not has_token and not manual_complete:
            raise serializers.ValidationError("Un lien magique ou un code de récupération est requis.")

        return attrs


class DeviceResetRequestSerializer(serializers.Serializer):
    """Device-reset request body uses credentials because the caller is locked out and no token is issued by this route."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class DeviceResetConfirmSerializer(serializers.Serializer):
    """Device-reset confirmation keeps code shape deliberately loose so bad values count as OTP attempts instead of bypassing the attempt counter through shape validation."""

    challenge_id = serializers.UUIDField()
    code = serializers.CharField(max_length=16, trim_whitespace=True)


class StepUpRequestSerializer(serializers.Serializer):
    """Corps vide de POST /api/v1/auth/step-up/request."""


class StepUpConfirmSerializer(serializers.Serializer):
    """Step-up confirmation keeps code shape loose so invalid values still count as OTP attempts."""

    challenge_id = serializers.UUIDField()
    code = serializers.CharField(max_length=16, trim_whitespace=True)


class PhoneChangeRequestSerializer(serializers.Serializer):
    """Request to replace the phone number."""

    phone = serializers.CharField(
        max_length=32,
        trim_whitespace=True,
    )

    def validate_phone(self, value: str) -> str:
        from .services.phone_change import clean_phone

        try:
            return clean_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(
                str(exc),
            ) from exc


class PhoneChangeConfirmSerializer(serializers.Serializer):
    """OTP confirmation for phone-number replacement."""

    challenge_id = serializers.UUIDField()
    phone = serializers.CharField(
        max_length=32,
        trim_whitespace=True,
    )
    code = serializers.CharField(
        max_length=16,
        trim_whitespace=True,
    )

    def validate_phone(self, value: str) -> str:
        from .services.phone_change import clean_phone

        try:
            return clean_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(
                str(exc),
            ) from exc
