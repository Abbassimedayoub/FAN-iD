from rest_framework import serializers


class ScannerPortalEventSerializer(
    serializers.Serializer,
):
    assignment_id = serializers.UUIDField(
        read_only=True,
    )
    assigned_at = serializers.DateTimeField(
        read_only=True,
    )

    id = serializers.UUIDField(
        read_only=True,
    )
    organizer_id = serializers.UUIDField(
        read_only=True,
    )

    name = serializers.CharField(
        read_only=True,
    )
    starts_at = serializers.DateTimeField(
        read_only=True,
    )
    ends_at = serializers.DateTimeField(
        read_only=True,
    )
    postponed_from_starts_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    postponed_from_ends_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    postponed_to_starts_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    postponed_to_ends_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    venue = serializers.CharField(
        read_only=True,
    )

    status = serializers.CharField(
        read_only=True,
    )
    lifecycle_reason = serializers.CharField(
        read_only=True,
    )
    lifecycle_changed_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
