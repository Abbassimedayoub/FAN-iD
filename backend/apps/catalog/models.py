from __future__ import annotations

from typing import cast

from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel

EVENT_DRAFT = "DRAFT"
EVENT_PUBLISHED = "PUBLISHED"
EVENT_POSTPONED = "POSTPONED"
EVENT_SUSPENDED = "SUSPENDED"
EVENT_CANCELLED = "CANCELLED"
EVENT_COMPLETED = "COMPLETED"
EVENT_ARCHIVED = "ARCHIVED"

EVENT_STATUSES = (
    EVENT_DRAFT,
    EVENT_PUBLISHED,
    EVENT_POSTPONED,
    EVENT_SUSPENDED,
    EVENT_CANCELLED,
    EVENT_COMPLETED,
    EVENT_ARCHIVED,
)


class Category(UUIDModel, TimeStampedModel, VersionedModel):
    """Editable event category using VersionedModel for optimistic-locking support."""

    # NULL denotes a system or legacy category.
    # A custom category belongs to the organizer that created it; organizer_id also
    # supports OWN_ORGANIZER authorization on deletion.
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
    """Editable catalog event resource; ticket sales remain owned by other contexts."""

    DRAFT = EVENT_DRAFT
    PUBLISHED = EVENT_PUBLISHED
    POSTPONED = EVENT_POSTPONED
    SUSPENDED = EVENT_SUSPENDED
    CANCELLED = EVENT_CANCELLED
    COMPLETED = EVENT_COMPLETED
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

    # Previous schedule replaced by a postponement.
    postponed_from_starts_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    postponed_from_ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Newly announced schedule.
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

    # Commercial sales window.
    #
    # NULL retains legacy behavior:
    # - null sales_starts_at means sales may start at publication;
    # - null sales_ends_at means sales may continue until the event begins.
    #
    # Actual sale eligibility rules remain centralized in apps.catalog.lifecycle
    # and are shared with ordering.
    sales_starts_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    sales_ends_at = models.DateTimeField(
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
            models.CheckConstraint(
                condition=(
                    models.Q(sales_starts_at__isnull=True)
                    | models.Q(sales_ends_at__isnull=True)
                    | models.Q(sales_ends_at__gt=models.F("sales_starts_at"))
                ),
                name="ck_event_sales_window_coherent",
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

    @property
    def operational_status(self) -> str:
        """
        Compute the current business phase.

        `status` remains the structural source of truth; temporal phases are
        derived rather than persisted to avoid stale scheduled transitions.
        """
        from .lifecycle import EventLifecycleLike, event_operational_status

        return event_operational_status(cast(EventLifecycleLike, self))

    def __str__(self) -> str:
        return self.name


class TicketCategory(UUIDModel, TimeStampedModel, VersionedModel):
    """
    Sale category for an event.

    Catalog owns what may be sold and available capacity, while ticketing owns
    issued tickets. `sold_count` is materialized to support atomic inventory
    updates without recounting orders on every request.
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
        """Ownership primitive for ABAC, derived through Event without storing a redundant organizer_id."""
        return self.event.organizer_id

    def __str__(self) -> str:
        return f"{self.event} - {self.name}"


class EventScannerAssignment(
    UUIDModel,
    TimeStampedModel,
):
    """
    Manual scanner assignment to an event.

    `scanner_id` is a UUID reference rather than a Python ForeignKey to keep
    catalog dependent on organizing only through its public API. Unassignment
    keeps the row for traceability.
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
