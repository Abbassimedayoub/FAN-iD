"""
Public events emitted by the `organizing` context.

Only decisions explicitly modeled as Outbox events live here.
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
    Minimal payload with no business name, email address, rejection reason, or other personal data
    duplicated into the Outbox.
    """
    return {"status": status}


SCANNER_INVITED_EVENT: Final = "organizing.scanner.invited"

AGGREGATE_SCANNER: Final = "scanner"


def scanner_invited_payload() -> dict[str, Any]:
    """No email address or secret is placed in the Outbox."""

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
    """No password enters the Outbox; the generation number is not a secret."""

    return {
        "generation": generation,
    }


SCANNER_LEAVE_REQUESTED_EVENT: Final = "organizing.scanner.leave_requested"
SCANNER_LEAVE_REJECTED_EVENT: Final = "organizing.scanner.leave_rejected"


def scanner_leave_request_payload() -> dict[str, Any]:
    """No name, email address, or other personal data is placed in the Outbox."""

    return {}


def scanner_leave_rejected_payload() -> dict[str, Any]:
    """The event type carries the decision; no personal data is duplicated."""

    return {}
