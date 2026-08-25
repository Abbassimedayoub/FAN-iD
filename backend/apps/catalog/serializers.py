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
    description = serializers.CharField(
        read_only=True
    )
    version = serializers.IntegerField(
        read_only=True
    )


class EventSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    organizer_id = serializers.UUIDField(
        read_only=True
    )
    category_id = serializers.UUIDField(
        read_only=True
    )

    name = serializers.CharField(read_only=True)
    description = serializers.CharField(
        read_only=True
    )

    starts_at = serializers.DateTimeField(
        read_only=True
    )
    ends_at = serializers.DateTimeField(
        read_only=True
    )

    venue = serializers.CharField(
        read_only=True
    )
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

    version = serializers.IntegerField(
        read_only=True
    )
    created_at = serializers.DateTimeField(
        read_only=True
    )
    updated_at = serializers.DateTimeField(
        read_only=True
    )

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

        if (
            starts_at is not None
            and ends_at is not None
            and ends_at <= starts_at
        ):
            raise serializers.ValidationError(
                {
                    "ends_at": (
                        "La fin doit être strictement "
                        "postérieure au début."
                    )
                }
            )

        if self.partial and not attrs:
            raise serializers.ValidationError(
                "Au moins un champ modifiable est requis."
            )

        return attrs


class TicketCategorySerializer(
    serializers.Serializer
):
    id = serializers.UUIDField(read_only=True)
    event_id = serializers.UUIDField(
        read_only=True
    )

    name = serializers.CharField(read_only=True)

    quota = serializers.IntegerField(
        read_only=True
    )
    sold_count = serializers.IntegerField(
        read_only=True
    )
    available_count = serializers.IntegerField(
        read_only=True
    )

    unit_price_cents = serializers.IntegerField(
        read_only=True
    )

    version = serializers.IntegerField(
        read_only=True
    )
    created_at = serializers.DateTimeField(
        read_only=True
    )
    updated_at = serializers.DateTimeField(
        read_only=True
    )


class TicketCategoryWriteSerializer(
    serializers.Serializer
):
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
        category = self.context.get(
            "ticket_category"
        )

        if category is not None:
            quota = attrs.get(
                "quota",
                category.quota,
            )

            if quota < category.sold_count:
                raise serializers.ValidationError(
                    {
                        "quota": (
                            "Le quota ne peut pas être "
                            "inférieur au nombre déjà vendu."
                        )
                    }
                )

        if self.partial and not attrs:
            raise serializers.ValidationError(
                "Au moins un champ modifiable est requis."
            )

        return attrs
