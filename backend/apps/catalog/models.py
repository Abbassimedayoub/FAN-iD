from __future__ import annotations

from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel

EVENT_DRAFT = "DRAFT"
EVENT_PUBLISHED = "PUBLISHED"
EVENT_POSTPONED = "POSTPONED"
EVENT_SUSPENDED = "SUSPENDED"
EVENT_CANCELLED = "CANCELLED"
EVENT_ARCHIVED = "ARCHIVED"

EVENT_STATUSES = (
    EVENT_DRAFT,
    EVENT_PUBLISHED,
    EVENT_POSTPONED,
    EVENT_SUSPENDED,
    EVENT_CANCELLED,
    EVENT_ARCHIVED,
)


class Category(UUIDModel, TimeStampedModel, VersionedModel):
    """
    Catégorie d'événement éditable.

    VersionedModel prépare le verrouillage optimiste pour les éditions
    administrateur (Sprint 2).
    """

    # NULL = catégorie système / historique.
    # Une catégorie personnalisée appartient à l'organisateur
    # qui l'a créée. Cet organizer_id permet aussi d'appliquer
    # la permission OWN_ORGANIZER lors de la suppression.
    organizer = models.ForeignKey(
        "organizing.Organizer",
        on_delete=models.PROTECT,
        related_name="event_categories",
        null=True,
        blank=True,
    )

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
    POSTPONED = EVENT_POSTPONED
    SUSPENDED = EVENT_SUSPENDED
    CANCELLED = EVENT_CANCELLED
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

    # Dernière programmation remplacée lors d'un report.
    postponed_from_starts_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    postponed_from_ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Nouvelle programmation annoncée.
    # Null signifie : nouvelle date encore inconnue.
    postponed_to_starts_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    postponed_to_ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )

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

    lifecycle_reason = models.TextField(
        blank=True,
    )

    lifecycle_changed_at = models.DateTimeField(
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
                condition=(models.Q(capacity_total__isnull=True) | models.Q(capacity_total__gt=0)),
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


class EventScannerAssignment(
    UUIDModel,
    TimeStampedModel,
):
    """
    Affectation manuelle d'un scanner à un événement.

    `scanner_id` est volontairement une référence UUID et non
    une ForeignKey Python vers organizing.Scanner :
    catalog ne dépend des règles organizing qu'au travers
    de apps.organizing.api.

    Une désaffectation conserve la ligne pour la traçabilité.
    """

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="scanner_assignments",
    )

    scanner_id = models.UUIDField()

    assigned_by_id = models.UUIDField()

    unassigned_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    unassigned_by_id = models.UUIDField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "catalog_event_scanner_assignment"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "event",
                    "scanner_id",
                ],
                condition=models.Q(
                    unassigned_at__isnull=True,
                ),
                name="uq_event_scanner_active",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        unassigned_at__isnull=True,
                        unassigned_by_id__isnull=True,
                    )
                    | models.Q(
                        unassigned_at__isnull=False,
                        unassigned_by_id__isnull=False,
                    )
                ),
                name="ck_ev_scan_unassign_trace",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "event",
                    "unassigned_at",
                ],
                name="ix_ev_scan_event_active",
            ),
            models.Index(
                fields=[
                    "scanner_id",
                    "unassigned_at",
                ],
                name="ix_ev_scan_scanner_active",
            ),
        ]
