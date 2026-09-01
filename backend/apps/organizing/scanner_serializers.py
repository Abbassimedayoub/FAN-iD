from typing import Any

from rest_framework import serializers


class ScannerInviteSerializer(serializers.Serializer):
    first_name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )

    last_name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )

    email = serializers.EmailField(
        max_length=254,
    )


class ScannerSerializer(serializers.Serializer):
    phone = serializers.CharField(
        source="user.phone",
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )

    id = serializers.UUIDField(
        read_only=True,
    )

    user_id = serializers.UUIDField(
        read_only=True,
    )

    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    status = serializers.CharField(
        read_only=True,
    )

    scanner_email_sent_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )

    organizer_email_sent_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )

    opened_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )

    activated_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )

    removed_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )

    archived_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )

    password_help_pending = serializers.SerializerMethodField()

    password_help_requested_at = serializers.SerializerMethodField()

    created_at = serializers.DateTimeField(
        read_only=True,
    )

    updated_at = serializers.DateTimeField(
        read_only=True,
    )

    version = serializers.IntegerField(
        read_only=True,
    )

    def get_first_name(
        self,
        obj: Any,
    ) -> str:
        return obj.invited_first_name or obj.user.first_name

    def get_last_name(
        self,
        obj: Any,
    ) -> str:
        return obj.invited_last_name or obj.user.last_name

    def get_email(
        self,
        obj: Any,
    ) -> str:
        return obj.invited_email or obj.user.email

    @staticmethod
    def _pending_password_help(
        obj: Any,
    ) -> Any:
        return obj.credential_requests.filter(status="PENDING").order_by("-created_at").first()

    def get_password_help_pending(
        self,
        obj: Any,
    ) -> bool:
        return self._pending_password_help(obj) is not None

    def get_password_help_requested_at(
        self,
        obj: Any,
    ) -> Any:
        request = self._pending_password_help(obj)

        if request is None:
            return None

        return request.created_at


class ScannerPasswordHelpRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(
        max_length=254,
    )


class ScannerCredentialRequestSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        read_only=True,
    )

    status = serializers.CharField(
        read_only=True,
    )

    created_at = serializers.DateTimeField(
        read_only=True,
    )

    resolved_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )

    generation = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
