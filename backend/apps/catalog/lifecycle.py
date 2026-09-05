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
    "ARCHIVED": OPERATIONAL_ARCHIVED,
}


def event_operational_status(
    event: EventLifecycleLike,
    *,
    at: datetime.datetime | None = None,
) -> str:
    """
    Retourne la phase métier visible d'un événement.

    Le statut structurel reste stocké dans Event.status.

    Pour un événement PUBLISHED :
    - avant sales_starts_at : COMING_SOON ;
    - pendant la fenêtre de vente : SALE_OPEN ;
    - après sales_ends_at mais avant starts_at : SALE_CLOSED ;
    - entre starts_at et ends_at : LIVE ;
    - après ends_at : ENDED.

    Compatibilité historique :
    - sales_starts_at NULL => vente ouverte dès publication ;
    - sales_ends_at NULL => vente ouverte jusqu'au début de l'événement.

    SOLD_OUT n'est volontairement pas calculé ici : il dépend du stock
    TicketCategory et sera ajouté dans la couche catalogue/ordering.

    SCAN_OPEN n'est volontairement pas calculé ici non plus : il dépendra
    d'une vraie ouverture opérationnelle par l'Organizer.
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

    if (
        event.sales_starts_at is not None
        and moment < event.sales_starts_at
    ):
        return OPERATIONAL_COMING_SOON

    if (
        event.sales_ends_at is not None
        and moment >= event.sales_ends_at
    ):
        return OPERATIONAL_SALE_CLOSED

    return OPERATIONAL_SALE_OPEN



def event_sales_phase(
    event: EventLifecycleLike,
    *,
    at: datetime.datetime | None = None,
) -> str:
    """
    Phase commerciale utilisée par le catalogue et ordering.

    PUBLISHED et POSTPONED avec nouvelle date connue utilisent la même
    fenêtre de vente.

    Un POSTPONED sans nouvelle programmation reste non vendable tant que
    l'Organizer n'a pas défini sa nouvelle date.
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

    if (
        event.sales_starts_at is not None
        and moment < event.sales_starts_at
    ):
        return OPERATIONAL_COMING_SOON

    if (
        event.sales_ends_at is not None
        and moment >= event.sales_ends_at
    ):
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
    # Le catalogue Fan expose actuellement certains brouillons comme
    # événements à venir. La traduction publique en COMING_SOON doit
    # appartenir au Backend et non être devinée par le Mobile.
    if event.status == "DRAFT":
        return OPERATIONAL_COMING_SOON

    phase = event_sales_phase(
        event,
        at=at,
    )

    if phase == OPERATIONAL_SALE_OPEN and sold_out:
        return CATALOG_SOLD_OUT

    return phase
