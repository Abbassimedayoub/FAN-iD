"""
Interface publique minimale du contexte organizing.

Les autres bounded contexts ne doivent pas importer directement les modèles
internes d organizing pour résoudre le propriétaire courant.
"""

from __future__ import annotations

import uuid

from .constants import ORGANIZER_APPROVED
from .models import Organizer

__all__ = [
    "resolve_organizer_context",
]


def resolve_organizer_context(
    *,
    user_id: uuid.UUID,
) -> tuple[uuid.UUID | None, bool]:
    """
    Retourne l organisateur du compte et son état d approbation.

    Un seul SELECT fournit les deux primitives nécessaires au moteur
    d autorisation.
    """

    row = (
        Organizer.objects
        .filter(user_id=user_id)
        .values_list(
            "pk",
            "validation_status",
        )
        .first()
    )

    if row is None:
        return None, False

    organizer_id, validation_status = row

    return (
        organizer_id,
        validation_status == ORGANIZER_APPROVED,
    )
