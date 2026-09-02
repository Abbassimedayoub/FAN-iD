from __future__ import annotations

from rest_framework import serializers

from apps.core.adapters.storage import build_object_storage

from .models import Category, Event


EVENT_IMAGE_URL_TTL_SECONDS = 300


class FanCatalogCategorySerializer(serializers.Serializer):
    """
    Contrat de lecture du Catalogue Fan.

    Les informations d'ownership Organizer ne sont pas exposées.
    """

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)


class FanCatalogEventSerializer(serializers.Serializer):
    """
    Contrat de lecture d'un événement pour le Fan.

    Le statut réel et ses informations associées restent visibles afin
    que le Mobile puisse représenter correctement tous les états métier.
    """

    id = serializers.UUIDField(read_only=True)
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
    lifecycle_reason = serializers.CharField(read_only=True)
    lifecycle_changed_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
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


class FanCatalogEventQuerySerializer(serializers.Serializer):
    category_id = serializers.UUIDField(required=True)
