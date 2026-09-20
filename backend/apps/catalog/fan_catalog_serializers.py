from __future__ import annotations

from rest_framework import serializers

from apps.core.adapters.storage import build_object_storage

from .lifecycle import event_catalog_status, event_sales_open
from .models import Event, TicketCategory

EVENT_IMAGE_URL_TTL_SECONDS = 300


class FanCatalogCategorySerializer(serializers.Serializer):
    """
    Read contract for the fan catalog.

    Organizer ownership information is not exposed.
    """

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)


class FanCatalogTicketCategorySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    unit_price_cents = serializers.IntegerField(read_only=True)
    available_count = serializers.IntegerField(read_only=True)


class FanCatalogEventSerializer(serializers.Serializer):
    """
    Fan-facing event read contract.

    The actual event status and related information remain visible so clients
    can represent every business state correctly.
    """

    id = serializers.UUIDField(read_only=True)
    category_id = serializers.UUIDField(read_only=True)

    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)

    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)

    sales_starts_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    sales_ends_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
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

    venue = serializers.CharField(read_only=True)
    capacity_total = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )

    image_url = serializers.SerializerMethodField()

    min_price_cents = serializers.SerializerMethodField()
    ticket_category_count = serializers.SerializerMethodField()
    available_ticket_category_count = serializers.SerializerMethodField()
    ticket_categories = serializers.SerializerMethodField()

    sales_open = serializers.SerializerMethodField()
    sold_out = serializers.SerializerMethodField()
    catalog_status = serializers.SerializerMethodField()
    can_add_to_cart = serializers.SerializerMethodField()

    status = serializers.CharField(read_only=True)
    operational_status = serializers.CharField(read_only=True)
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

    def _ticket_categories(
        self,
        obj: Event,
    ) -> list[TicketCategory]:
        cache_name = "_fan_catalog_ticket_categories"
        cached = getattr(obj, cache_name, None)

        if cached is not None:
            return cached

        categories = list(obj.ticket_categories.all())

        categories.sort(
            key=lambda category: (
                category.unit_price_cents,
                category.name.casefold(),
                str(category.pk),
            )
        )

        setattr(
            obj,
            cache_name,
            categories,
        )

        return categories

    def _price_summary(
        self,
        obj: Event,
    ) -> tuple[int | None, int, int]:
        cache_name = "_fan_catalog_price_summary"
        cached = getattr(obj, cache_name, None)

        if cached is not None:
            return cached

        categories = self._ticket_categories(obj)
        available = [category for category in categories if category.sold_count < category.quota]

        summary = (
            min(
                (category.unit_price_cents for category in available),
                default=None,
            ),
            len(categories),
            len(available),
        )

        setattr(obj, cache_name, summary)

        return summary

    def get_min_price_cents(
        self,
        obj: Event,
    ) -> int | None:
        return self._price_summary(obj)[0]

    def get_ticket_category_count(
        self,
        obj: Event,
    ) -> int:
        return self._price_summary(obj)[1]

    def get_available_ticket_category_count(
        self,
        obj: Event,
    ) -> int:
        return self._price_summary(obj)[2]

    def get_ticket_categories(
        self,
        obj: Event,
    ):
        return FanCatalogTicketCategorySerializer(
            self._ticket_categories(obj),
            many=True,
        ).data

    def get_sales_open(
        self,
        obj: Event,
    ) -> bool:
        return event_sales_open(obj)

    def get_sold_out(
        self,
        obj: Event,
    ) -> bool:
        total_categories = self._price_summary(obj)[1]
        available_categories = self._price_summary(obj)[2]

        return total_categories > 0 and available_categories == 0

    def get_catalog_status(
        self,
        obj: Event,
    ) -> str:
        return event_catalog_status(
            obj,
            sold_out=self.get_sold_out(obj),
        )

    def get_can_add_to_cart(
        self,
        obj: Event,
    ) -> bool:
        return self.get_sales_open(obj) and not self.get_sold_out(obj)


class FanCatalogEventQuerySerializer(serializers.Serializer):
    category_id = serializers.UUIDField(required=True)
