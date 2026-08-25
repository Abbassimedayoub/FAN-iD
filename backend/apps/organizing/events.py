"""
Evenements publics emis par le contexte `organizing`.

Seules les decisions explicitement prevues comme evenements Outbox vivent ici.
La candidature reste un journal applicatif dans ce lot.
"""

from __future__ import annotations

from typing import Any, Final

ORGANIZER_APPROVED_EVENT: Final = "organizing.organizer.approved"
ORGANIZER_REJECTED_EVENT: Final = "organizing.organizer.rejected"
ORGANIZER_SUSPENDED_EVENT: Final = "organizing.organizer.suspended"

AGGREGATE_ORGANIZER: Final = "organizer"


def organizer_decision_payload(*, status: str) -> dict[str, Any]:
    """
    Charge utile minimale.

    Aucun nom commercial, courriel, motif de rejet ni autre donnee personnelle
    n est duplique dans l outbox.
    """
    return {"status": status}
