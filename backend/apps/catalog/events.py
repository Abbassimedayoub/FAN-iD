"""
Evenements publics emis par le contexte `catalog`.

Seules les transitions utiles aux autres contextes sont publiees ici.
"""

from __future__ import annotations

from typing import Any, Final


CATALOG_EVENT_PUBLISHED: Final = "catalog.event.published"

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
