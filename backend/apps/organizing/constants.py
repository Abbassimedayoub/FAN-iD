"""
Vocabulaire du contexte `organizing`.

Les valeurs vivent ici, pas dans les modeles : la contrainte `CHECK` de la base
et le code applicatif lisent la MEME source. C est la lecon du doublon de
motifs de revocation, corrige entre S1-A.6e et S1-A.7 — deux enumerations aux
memes valeurs finissent par diverger, et la panne tombe alors sur un chemin
d ecriture.
"""

from __future__ import annotations

from typing import Final

#: Etat de validation d un organisateur (plan S1 §3.1, colonne
#: `validation_status`). Les quatre valeurs sont celles qu impliquent les
#: routes d administration du §3.3 — approuver, rejeter, suspendre — plus
#: l etat initial d une candidature.
#:
#: Les TRANSITIONS entre ces etats ne sont PAS definies ici : elles
#: appartiennent a `OrganizerOnboardingService` (lot S1-A.8b). Ce module ne
#: declare que le vocabulaire.
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

#: Longueur maximale du nom commercial. Le plan §3.1 ne la fixe pas ; une
#: colonne `varchar` en exige une. Valeur retenue et consignee comme ecart.
ORG_NAME_MAX_LENGTH: Final = 120


# Auteurs possibles d'une proposition structuree de commission.
ORGANIZER_COMMISSION_PROPOSER_ORGANIZER: Final = "ORGANIZER"
ORGANIZER_COMMISSION_PROPOSER_ADMIN: Final = "ADMIN"

ORGANIZER_COMMISSION_PROPOSER_ROLES: Final[tuple[str, ...]] = (
    ORGANIZER_COMMISSION_PROPOSER_ORGANIZER,
    ORGANIZER_COMMISSION_PROPOSER_ADMIN,
)


# Cycle de vie d'un scanner invité.
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
