"""
Evenements publics emis par le contexte `catalog`.

Seules les transitions utiles aux autres contextes sont publiees ici.
"""

from __future__ import annotations

from typing import Any, Final

CATALOG_EVENT_PUBLISHED: Final = "catalog.event.published"
CATALOG_EVENT_POSTPONED: Final = "catalog.event.postponed"
CATALOG_EVENT_SUSPENDED: Final = "catalog.event.suspended"
CATALOG_EVENT_CANCELLED: Final = "catalog.event.cancelled"
CATALOG_EVENT_SCANNER_ASSIGNED: Final = "catalog.event.scanner_assigned"
CATALOG_EVENT_SCANNER_UNASSIGNED: Final = "catalog.event.scanner_unassigned"

AGGREGATE_EVENT: Final = "event"


def event_status_payload(
    *,
    status: str,
) -> dict[str, Any]:
    """
    Charge utile minimale.

    L identifiant de l evenement est deja porte par aggregate_id.
    Les consommateurs recupereront les donnees supplementaires via
    le contrat public du catalogue plutot que dupliquer le modele.
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
    Contrat Outbox sans donnée personnelle.

    Les adresses des acheteurs ne sont jamais copiées dans l événement.
    Le futur consommateur Ordering/Notifying résoudra les destinataires
    à partir de l identifiant aggregate_id.
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
