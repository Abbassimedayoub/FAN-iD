"""
Public events emitted by the `catalog` context.

Only transitions useful to other contexts are published here.
"""

from __future__ import annotations

from typing import Any, Final

CATALOG_EVENT_PUBLISHED: Final = "catalog.event.published"
CATALOG_EVENT_POSTPONED: Final = "catalog.event.postponed"
CATALOG_EVENT_SUSPENDED: Final = "catalog.event.suspended"
CATALOG_EVENT_CANCELLED: Final = "catalog.event.cancelled"
CATALOG_EVENT_COMPLETED: Final = "catalog.event.completed"
CATALOG_EVENT_SCANNER_ASSIGNED: Final = "catalog.event.scanner_assigned"
CATALOG_EVENT_SCANNER_UNASSIGNED: Final = "catalog.event.scanner_unassigned"

AGGREGATE_EVENT: Final = "event"


def event_status_payload(
    *,
    status: str,
) -> dict[str, Any]:
    """
    Minimal event payload.

    The event identifier is already carried by `aggregate_id`; consumers fetch
    additional data through the public catalog contract rather than duplicating
    the model.
    """

    return {
        "status": status,
    }


def event_lifecycle_payload(
    *,
    status: str,
    reason: str,
    notify_buyers: bool,
    refund_requested: bool = False,
    starts_at: Any = None,
    ends_at: Any = None,
    previous_starts_at: Any = None,
    previous_ends_at: Any = None,
) -> dict[str, Any]:
    """
    Outbox contract without personal data.

    Buyer addresses are never copied into the event. Consumers resolve
    recipients from `aggregate_id` through their own context contracts.
    """

    payload = event_status_payload(
        status=status,
    )

    payload.update(
        {
            "reason": reason,
            "notify_buyers": notify_buyers,
            "refund_requested": refund_requested,
        }
    )

    if starts_at is not None:
        payload["starts_at"] = starts_at.isoformat()

    if ends_at is not None:
        payload["ends_at"] = ends_at.isoformat()

    if previous_starts_at is not None:
        payload["previous_starts_at"] = previous_starts_at.isoformat()

    if previous_ends_at is not None:
        payload["previous_ends_at"] = previous_ends_at.isoformat()

    return payload
