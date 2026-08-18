from __future__ import annotations

from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel

EVENT_DRAFT = "DRAFT"
EVENT_PUBLISHED = "PUBLISHED"
EVENT_ARCHIVED = "ARCHIVED"

EVENT_STATUSES = (
    EVENT_DRAFT,
    EVENT_PUBLISHED,
    EVENT_ARCHIVED,
)


class Category(UUIDModel, TimeStampedModel, VersionedModel):
    """
    Catégorie d'événement éditable.

    VersionedModel prépare le verrouillage optimiste pour les éditions
    administrateur (Sprint 2).
    """

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "catalog_category"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="uq_category_name_ci",
            ),
        ]
        indexes = [
            models.Index(
                fields=["name"],
                name="ix_category_name",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Event(UUIDModel, TimeStampedModel, VersionedModel):
    """
    Événement du catalogue.

    Le catalogue ne gère pas encore la vente :
    il expose uniquement la ressource éditable.
    """

    DRAFT = EVENT_DRAFT
    PUBLISHED = EVENT_PUBLISHED
    ARCHIVED = EVENT_ARCHIVED

    STATUSES = EVENT_STATUSES

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="events",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        default=DRAFT,
        choices=[(status, status) for status in STATUSES],
    )

    class Meta:
        db_table = "catalog_event"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="uq_event_name_ci",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="ck_event_dates_coherent",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(EVENT_STATUSES)),
                name="ck_event_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status"],
                name="ix_event_status",
            ),
            models.Index(
                fields=["starts_at"],
                name="ix_event_starts_at",
            ),
        ]

    def __str__(self) -> str:
        return self.name
