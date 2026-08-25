from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import Category, Event


class CategorySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    version = serializers.IntegerField(read_only=True)


class EventSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    organizer_id = serializers.UUIDField(read_only=True)
    category_id = serializers.UUIDField(read_only=True)

    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)

    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)

    status = serializers.CharField(read_only=True)

    version = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class EventWriteSerializer(serializers.Serializer):
    """
    Contrat fermé de création/modification.

    organizer_id n est jamais accepté comme commande métier :
    le propriétaire vient exclusivement de la session.

    status n est pas une entrée de cette phase :
    toute création commence en DRAFT.
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
