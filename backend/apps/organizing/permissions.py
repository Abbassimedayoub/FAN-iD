"""
Adaptateurs d autorisation du contexte `organizing`.

**Ce module est le seul point du contexte qui franchit la frontiere.** Il
importe `apps.identity.api`, et rien d autre d `identity` — c est ce que le
contrat `organizing-reaches-identity-through-api-only` verifie a chaque commit
(ADR-S1-05).

Aucune decision n est prise ici. La classe ci-dessous designe la ressource ;
le verdict reste rendu par le moteur d `identity`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from apps.identity.api import OrganizerResourcePermission, Resource


class OrganizerRecordPermission(OrganizerResourcePermission):
    """
    Portee `OWN_ORGANIZER` quand la ressource EST le dossier d organisateur.

    `organizer_lookup = "pk"` parce que l objet ne PORTE pas un organisateur :
    il en est un. Meme raisonnement que `owner_lookup = "pk"` cote `identity`
    pour un point de terminaison dont l objet est l utilisateur.

    `state` est renseigne des maintenant. Aucune portee ne le lit au Sprint 1 —
    `engine._check_scope` ne compare que `organizer_id` — mais le champ existe
    sur `Resource` precisement pour que le lot S1-A.8b y branche les
    transitions sans modifier la signature du moteur.
    """

    organizer_lookup: ClassVar[str] = "pk"

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource(
            organizer_id=getattr(obj, self.organizer_lookup, None),
            state=getattr(obj, "validation_status", None),
        )
