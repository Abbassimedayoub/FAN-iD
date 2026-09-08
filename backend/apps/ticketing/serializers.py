from rest_framework import serializers

from .models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    event_id = serializers.UUIDField(read_only=True)
    event_name = serializers.CharField(source="event.name", read_only=True)
    event_starts_at = serializers.DateTimeField(source="event.starts_at", read_only=True)
    event_status = serializers.CharField(source="event.status", read_only=True)
    postponement_reason = serializers.CharField(
        source="event.lifecycle_reason",
        read_only=True,
        allow_null=True,
    )
    postponed_from_starts_at = serializers.DateTimeField(
        source="event.postponed_from_starts_at",
        read_only=True,
        allow_null=True,
    )
    postponed_to_starts_at = serializers.DateTimeField(
        source="event.postponed_to_starts_at",
        read_only=True,
        allow_null=True,
    )
    ticket_category_name = serializers.CharField(
        source="ticket_category.name",
        read_only=True,
    )

    class Meta:
        model = Ticket
        fields = (
            "id",
            "status",
            "event_id",
            "event_name",
            "event_starts_at",
            "event_status",
            "postponement_reason",
            "postponed_from_starts_at",
            "postponed_to_starts_at",
            "ticket_category_name",
            "created_at",
        )
