from __future__ import annotations

import datetime
from typing import Final, Protocol

from django.utils import timezone

OPERATIONAL_DRAFT: Final = "DRAFT"
OPERATIONAL_COMING_SOON: Final = "COMING_SOON"
OPERATIONAL_SALE_OPEN: Final = "SALE_OPEN"
OPERATIONAL_SALE_CLOSED: Final = "SALE_CLOSED"
OPERATIONAL_LIVE: Final = "LIVE"
OPERATIONAL_ENDED: Final = "ENDED"

OPERATIONAL_POSTPONED: Final = "POSTPONED"
OPERATIONAL_SUSPENDED: Final = "SUSPENDED"
OPERATIONAL_CANCELLED: Final = "CANCELLED"
OPERATIONAL_ARCHIVED: Final = "ARCHIVED"

CATALOG_SOLD_OUT: Final = "SOLD_OUT"


class EventLifecycleLike(Protocol):
    status: str
    starts_at: datetime.datetime
    ends_at: datetime.datetime
    sales_starts_at: datetime.datetime | None
    sales_ends_at: datetime.datetime | None
    postponed_to_starts_at: datetime.datetime | None


STRUCTURAL_OPERATIONAL_STATUSES: Final[dict[str, str]] = {
    "DRAFT": OPERATIONAL_DRAFT,
    "POSTPONED": OPERATIONAL_POSTPONED,
    "SUSPENDED": OPERATIONAL_SUSPENDED,
    "CANCELLED": OPERATIONAL_CANCELLED,
    "COMPLETED": OPERATIONAL_ENDED,
    "ARCHIVED": OPERATIONAL_ARCHIVED,
}


def event_operational_status(
    event: EventLifecycleLike,
    *,
    at: datetime.datetime | None = None,
) -> str:
    """
    Return the business phase currently visible for an event.

    Structural state remains in `Event.status`. Published events derive their
    temporal phase from sales and event timestamps. Null sales boundaries retain
    legacy behavior. SOLD_OUT and SCAN_OPEN are deliberately excluded because
    they depend on inventory and operational admission state.
    """
    structural = STRUCTURAL_OPERATIONAL_STATUSES.get(
        event.status,
    )

    if structural is not None:
        return structural

    if event.status != "PUBLISHED":
        return event.status

    moment = at or timezone.now()

    if moment >= event.ends_at:
        return OPERATIONAL_ENDED

    if moment >= event.starts_at:
        return OPERATIONAL_LIVE

    if event.sales_starts_at is not None and moment < event.sales_starts_at:
        return OPERATIONAL_COMING_SOON

    if event.sales_ends_at is not None and moment >= event.sales_ends_at:
        return OPERATIONAL_SALE_CLOSED

    return OPERATIONAL_SALE_OPEN


def event_sales_phase(
    event: EventLifecycleLike,
    *,
    at: datetime.datetime | None = None,
) -> str:
    """
    Commercial phase shared by catalog and ordering.

    PUBLISHED and rescheduled POSTPONED events use the same sales window. A
    postponed event with no new schedule remains unavailable for sale.
    """
    if event.status == "POSTPONED":
        if event.postponed_to_starts_at is None:
            return OPERATIONAL_POSTPONED
    elif event.status != "PUBLISHED":
        return STRUCTURAL_OPERATIONAL_STATUSES.get(
            event.status,
            event.status,
        )

    moment = at or timezone.now()

    if moment >= event.ends_at:
        return OPERATIONAL_ENDED

    if moment >= event.starts_at:
        return OPERATIONAL_LIVE

    if event.sales_starts_at is not None and moment < event.sales_starts_at:
        return OPERATIONAL_COMING_SOON

    if event.sales_ends_at is not None and moment >= event.sales_ends_at:
        return OPERATIONAL_SALE_CLOSED

    return OPERATIONAL_SALE_OPEN


def event_sales_open(
    event: EventLifecycleLike,
    *,
    at: datetime.datetime | None = None,
) -> bool:
    return (
        event_sales_phase(
            event,
            at=at,
        )
        == OPERATIONAL_SALE_OPEN
    )


def event_catalog_status(
    event: EventLifecycleLike,
    *,
    sold_out: bool,
    at: datetime.datetime | None = None,
) -> str:
    # Some drafts are currently exposed to fans as upcoming events. The backend
    # owns the public COMING_SOON mapping so clients do not have to infer it.
    if event.status == "DRAFT":
        return OPERATIONAL_COMING_SOON

    phase = event_sales_phase(
        event,
        at=at,
    )

    if phase == OPERATIONAL_SALE_OPEN and sold_out:
        return CATALOG_SOLD_OUT

    return phase
