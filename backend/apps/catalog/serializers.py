from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.core.adapters.storage import build_object_storage

from .models import (
    Category,
    Event,
    TicketCategory,
)

EVENT_IMAGE_URL_TTL_SECONDS = 300


class CategorySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    version = serializers.IntegerField(read_only=True)

    is_owned_by_me = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    def _owned_by_current_organizer(
        self,
        obj: Category,
    ) -> bool:
        organizer_id = self.context.get("organizer_id")

        return organizer_id is not None and obj.organizer_id == organizer_id

    def get_is_owned_by_me(
        self,
        obj: Category,
    ) -> bool:
        return self._owned_by_current_organizer(obj)

    def get_can_delete(
        self,
        obj: Category,
    ) -> bool:
        return self._owned_by_current_organizer(obj) and not obj.events.exists()


class CategoryWriteSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=120,
        trim_whitespace=True,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )


class EventSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    organizer_id = serializers.UUIDField(read_only=True)
    category_id = serializers.UUIDField(read_only=True)

    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)

    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)

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

    venue = serializers.CharField(read_only=True)
    capacity_total = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )

    image_url = serializers.SerializerMethodField()

    status = serializers.CharField(read_only=True)
    published_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    lifecycle_reason = serializers.CharField(
        read_only=True,
    )
    lifecycle_changed_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )

    version = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def _image_storage(self):
        storage = self.context.get("storage")

        if storage is None:
            storage = getattr(
                self,
                "_resolved_image_storage",
                None,
            )

        if storage is None:
            storage = build_object_storage()
            self._resolved_image_storage = storage

        return storage

    def get_image_url(
        self,
        obj: Event,
    ) -> str | None:
        if not obj.image_key:
            return None

        return self._image_storage().presigned_url(
            obj.image_key,
            EVENT_IMAGE_URL_TTL_SECONDS,
        )


class EventWriteSerializer(serializers.Serializer):
    """
    Contrat fermé du brouillon Event.

    organizer_id et status ne sont jamais des commandes
    du client.

    venue/capacity_total peuvent rester incomplets sur un
    brouillon. La publication applique les invariants forts.
    """

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
    )

    name = serializers.CharField(
        max_length=160,
        trim_whitespace=True,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

    venue = serializers.CharField(
        max_length=240,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )

    capacity_total = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )

    def validate(
        self,
        attrs: dict[str, Any],
    ) -> dict[str, Any]:
        event = self.context.get("event")

        starts_at = attrs.get(
            "starts_at",
            getattr(event, "starts_at", None),
        )

        ends_at = attrs.get(
            "ends_at",
            getattr(event, "ends_at", None),
        )

        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise serializers.ValidationError(
                {"ends_at": ("La fin doit être strictement " "postérieure au début.")}
            )

        if self.partial and not attrs:
            raise serializers.ValidationError("Au moins un champ modifiable est requis.")

        return attrs


class TicketCategorySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    event_id = serializers.UUIDField(read_only=True)

    name = serializers.CharField(read_only=True)

    quota = serializers.IntegerField(read_only=True)
    sold_count = serializers.IntegerField(read_only=True)
    available_count = serializers.IntegerField(read_only=True)

    unit_price_cents = serializers.IntegerField(read_only=True)

    version = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class TicketCategoryWriteSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=120,
        trim_whitespace=True,
    )

    quota = serializers.IntegerField(
        min_value=1,
    )

    unit_price_cents = serializers.IntegerField(
        min_value=0,
    )

    def validate(
        self,
        attrs: dict[str, Any],
    ) -> dict[str, Any]:
        category = self.context.get("ticket_category")

        if category is not None:
            quota = attrs.get(
                "quota",
                category.quota,
            )

            if quota < category.sold_count:
                raise serializers.ValidationError(
                    {"quota": ("Le quota ne peut pas être " "inférieur au nombre déjà vendu.")}
                )

        if self.partial and not attrs:
            raise serializers.ValidationError("Au moins un champ modifiable est requis.")

        return attrs


class EventPostponeSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
    ends_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )

    reason = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
        required=False,
        allow_blank=True,
        default="",
    )

    notify_buyers = serializers.BooleanField(
        default=True,
    )

    def validate(
        self,
        attrs: dict[str, Any],
    ) -> dict[str, Any]:
        starts_at = attrs.get("starts_at")
        ends_at = attrs.get("ends_at")

        if (starts_at is None) != (ends_at is None):
            raise serializers.ValidationError(
                {"starts_at": ("Les nouvelles dates doivent être " "renseignées ensemble ou laissées vides.")}
            )

        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise serializers.ValidationError(
                {"ends_at": ("La nouvelle heure de fin doit être " "postérieure à l heure de début.")}
            )

        return attrs


class EventSuspendSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
    )

    notify_buyers = serializers.BooleanField(
        default=True,
    )


class EventCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
    )

    notify_buyers = serializers.BooleanField(
        default=True,
    )

    refund_requested = serializers.BooleanField(
        default=True,
    )


class EventScannerAssignSerializer(
    serializers.Serializer,
):
    scanner_id = serializers.UUIDField()


class EventScannerAssignmentSerializer(
    serializers.Serializer,
):
    assignment_id = serializers.UUIDField(
        read_only=True,
    )

    scanner_id = serializers.UUIDField(
        read_only=True,
    )

    first_name = serializers.CharField(
        read_only=True,
    )

    last_name = serializers.CharField(
        read_only=True,
    )

    email = serializers.EmailField(
        read_only=True,
    )

    status = serializers.CharField(
        read_only=True,
    )

    scanner_version = serializers.IntegerField(
        read_only=True,
    )

    assigned_at = serializers.DateTimeField(
        read_only=True,
    )
