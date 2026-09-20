"""
Vocabulary for the `organizing` context.

Values live here instead of inside models so database CHECK constraints and
application code share the same source. Duplicated enumerations eventually
drift and turn into write-path failures.
"""

from __future__ import annotations

from typing import Final

#: Organizer validation state stored in `validation_status`.
#: The four values cover the initial application plus approve, reject, and
#: suspend administration actions.
#:
#: Transitions between these states are not defined here; they belong to the
#: onboarding service. This module only defines the vocabulary.
ORGANIZER_PENDING: Final = "PENDING"
ORGANIZER_APPROVED: Final = "APPROVED"
ORGANIZER_REJECTED: Final = "REJECTED"
ORGANIZER_SUSPENDED: Final = "SUSPENDED"

ORGANIZER_STATUSES: Final[tuple[str, ...]] = (
    ORGANIZER_PENDING,
    ORGANIZER_APPROVED,
    ORGANIZER_REJECTED,
    ORGANIZER_SUSPENDED,
)

#: Maximum trade-name length. The product specification does not define one,
#: while a varchar column requires an explicit bound.
ORG_NAME_MAX_LENGTH: Final = 120


# Possible authors of a structured commission proposal.
ORGANIZER_COMMISSION_NEGOTIATING: Final = "NEGOTIATING"
ORGANIZER_COMMISSION_AGREED: Final = "COMMISSION_AGREED"
ORGANIZER_COMMISSION_CANCELLED: Final = "CANCELLED"

ORGANIZER_COMMISSION_PROPOSER_ORGANIZER: Final = "ORGANIZER"
ORGANIZER_COMMISSION_PROPOSER_ADMIN: Final = "ADMIN"

ORGANIZER_COMMISSION_PROPOSER_ROLES: Final[tuple[str, ...]] = (
    ORGANIZER_COMMISSION_PROPOSER_ORGANIZER,
    ORGANIZER_COMMISSION_PROPOSER_ADMIN,
)


# Invited scanner lifecycle.
SCANNER_INVITED: Final = "INVITED"
SCANNER_EMAIL_SENT: Final = "EMAIL_SENT"
SCANNER_OPENED: Final = "OPENED"
SCANNER_ACTIVE: Final = "ACTIVE"
SCANNER_LEAVE_REQUESTED: Final = "LEAVE_REQUESTED"
SCANNER_INVITATION_CANCELLED: Final = "INVITATION_CANCELLED"
SCANNER_DELETED: Final = "DELETED"

SCANNER_STATUSES: Final[tuple[str, ...]] = (
    SCANNER_INVITED,
    SCANNER_EMAIL_SENT,
    SCANNER_OPENED,
    SCANNER_ACTIVE,
    SCANNER_LEAVE_REQUESTED,
    SCANNER_INVITATION_CANCELLED,
    SCANNER_DELETED,
)


SCANNER_CREDENTIAL_REQUEST_PENDING: Final = "PENDING"
SCANNER_CREDENTIAL_REQUEST_FULFILLED: Final = "FULFILLED"

SCANNER_CREDENTIAL_REQUEST_STATUSES: Final[tuple[str, ...]] = (
    SCANNER_CREDENTIAL_REQUEST_PENDING,
    SCANNER_CREDENTIAL_REQUEST_FULFILLED,
)
