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
ORGANIZER_REOPENED_EVENT: Final = "organizing.organizer.reopened"

AGGREGATE_ORGANIZER: Final = "organizer"


def organizer_decision_payload(*, status: str) -> dict[str, Any]:
    """
    Charge utile minimale.

    Aucun nom commercial, courriel, motif de rejet ni autre donnee personnelle
    n est duplique dans l outbox.
    """
    return {"status": status}


SCANNER_INVITED_EVENT: Final = "organizing.scanner.invited"

AGGREGATE_SCANNER: Final = "scanner"


def scanner_invited_payload() -> dict[str, Any]:
    """
    Aucun e-mail et aucun secret dans l'Outbox.
    """

    return {}


SCANNER_REVOKED_EVENT: Final = "organizing.scanner.revoked"


def scanner_revoked_payload(
    *,
    organizer_id: Any,
    status: str,
    sessions_revoked: int,
) -> dict[str, Any]:
    return {
        "organizer_id": str(organizer_id),
        "status": status,
        "sessions_revoked": sessions_revoked,
    }


SCANNER_PASSWORD_HELP_REQUESTED_EVENT: Final = "organizing.scanner.password_help_requested"

SCANNER_TEMP_PASSWORD_REISSUED_EVENT: Final = "organizing.scanner.temporary_password_reissued"


def scanner_password_help_requested_payload(
    *,
    request_id: Any,
) -> dict[str, Any]:
    return {
        "request_id": str(request_id),
    }


def scanner_temp_password_reissued_payload(
    *,
    request_id: Any,
    generation: int,
) -> dict[str, Any]:
    return {
        "request_id": str(request_id),
        "generation": generation,
    }


SCANNER_INVITATION_REISSUED_EVENT: Final = "organizing.scanner.invitation_reissued"


def scanner_invitation_reissued_payload(
    *,
    generation: int,
) -> dict[str, Any]:
    """
    Aucun mot de passe n'entre dans l'Outbox.
    La génération n'est pas un secret.
    """

    return {
        "generation": generation,
    }


SCANNER_LEAVE_REQUESTED_EVENT: Final = "organizing.scanner.leave_requested"
SCANNER_LEAVE_REJECTED_EVENT: Final = "organizing.scanner.leave_rejected"


def scanner_leave_request_payload() -> dict[str, Any]:
    """
    Aucun nom, e-mail ou autre donnée personnelle dans l'Outbox.
    """

    return {}


def scanner_leave_rejected_payload() -> dict[str, Any]:
    """
    La décision est portée par le type d'événement.
    Aucune donnée personnelle n'est dupliquée.
    """

    return {}
