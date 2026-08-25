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

    # Transitional nullable ownership:
    # legacy events created before organizer ownership remain NULL.
    # All new business APIs must always assign an organizer.
    organizer = models.ForeignKey(
        "organizing.Organizer",
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="events",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    # ORG-07 operational information.
    #
    # capacity_total remains nullable only for legacy events created before
    # this field existed. New business APIs will require a positive value.
    venue = models.CharField(
        max_length=240,
        blank=True,
    )
    capacity_total = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    # Object-storage key, never a permanent public URL.
    # URLs are generated on demand by the storage adapter.
    image_key = models.CharField(
        max_length=512,
        blank=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

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
                models.F("organizer"),
                name="uq_event_org_name_ci",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="ck_event_dates_coherent",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(EVENT_STATUSES)),
                name="ck_event_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(capacity_total__isnull=True)
                    | models.Q(capacity_total__gt=0)
                ),
                name="ck_event_capacity_positive",
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
            models.Index(
                fields=["organizer"],
                name="ix_event_organizer",
            ),
        ]

    def __str__(self) -> str:
        return self.name

class TicketCategory(UUIDModel, TimeStampedModel, VersionedModel):
    """
    Catégorie de vente d un événement.

    Elle appartient au catalogue : elle décrit ce qui peut être vendu et
    combien de places existent. Le contexte ticketing restera propriétaire
    des billets effectivement émis.

    `sold_count` est matérialisé pour permettre plus tard l achat atomique
    sous verrou pessimiste sans compter les commandes à chaque requête.
    """

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="ticket_categories",
    )

    name = models.CharField(
        max_length=120,
    )

    quota = models.PositiveIntegerField()

    sold_count = models.PositiveIntegerField(
        default=0,
    )

    unit_price_cents = models.PositiveIntegerField()

    class Meta:
        db_table = "catalog_ticket_category"

        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                models.F("event"),
                name="uq_ticket_category_event_name_ci",
            ),
            models.CheckConstraint(
                condition=models.Q(quota__gt=0),
                name="ck_ticket_category_quota_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    sold_count__lte=models.F("quota"),
                ),
                name="ck_ticket_category_sold_lte_quota",
            ),
        ]

    @property
    def available_count(self) -> int:
        return self.quota - self.sold_count

    @property
    def organizer_id(self):
        """
        Primitive de propriété exposée au moteur ABAC.

        TicketCategory appartient à Event ; Event appartient à Organizer.
        Aucun organizer_id redondant n est stocké en base.
        """
        return self.event.organizer_id

    def __str__(self) -> str:
        return f"{self.event} - {self.name}"
