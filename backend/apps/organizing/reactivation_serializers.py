from rest_framework import serializers

from .models import OrganizerReactivationRequest


class OrganizerReactivationRequestSerializer(
    serializers.ModelSerializer
):
    organizer_id = serializers.UUIDField(
        read_only=True,
    )
    requested_by_id = serializers.UUIDField(
        read_only=True,
    )
    reviewed_by_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = OrganizerReactivationRequest
        fields = (
            "id",
            "organizer_id",
            "requested_by_id",
            "organizer_version",
            "status",
            "reviewed_by_id",
            "reviewed_at",
            "rejection_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrganizerReactivationRejectSerializer(
    serializers.Serializer
):
    reason = serializers.CharField(
        min_length=1,
        max_length=2000,
        trim_whitespace=True,
    )
