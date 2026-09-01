"""
Gestionnaires du contexte `organizing` (plan S1 §2.5).

Un filtre de perimetre ecrit dans une vue ne protege que cette vue. Ecrit ici,
il devient reutilisable et surtout RELISIBLE : la question « qui voit quoi »
se lit a un seul endroit.
"""

from __future__ import annotations

from typing import Any

from django.db import models

from .constants import ORGANIZER_APPROVED, ORGANIZER_PENDING


class OrganizerQuerySet(models.QuerySet):
    """Filtres de perimetre, nommes d apres le metier et non d apres la colonne."""

    def approved(self) -> "OrganizerQuerySet":
        """Seuls les organisateurs approuves peuvent vendre (RM-1)."""
        return self.filter(validation_status=ORGANIZER_APPROVED)

    def pending(self) -> "OrganizerQuerySet":
        """File d attente de la console d administration."""
        return self.filter(validation_status=ORGANIZER_PENDING)

    def with_user(self) -> "OrganizerQuerySet":
        """
        Charge le compte rattache en une requete.

        La liste d administration affiche l adresse du demandeur : sans cela,
        une page de vingt lignes declenche vingt et une requetes.
        """
        return self.select_related("user")

    def for_user(self, user: Any) -> "OrganizerQuerySet":
        return self.filter(user=user)
