"""
Interface publique du contexte `identity` (regle §1.4.3.2, ADR-S1-05).

**Tout ce qui traverse la frontiere passe par ce module, et rien d autre.**
`import-linter` le verifie : `apps.organizing` a interdiction d importer
`apps.identity` sous toute autre forme, avec une exception unique et explicite
pour `apps.identity.api`.

La liste ci-dessous est donc un CONTRAT. Y ajouter un symbole est une decision
d architecture — pas une commodite d ecriture. Un contexte qui a besoin de plus
a probablement besoin d autre chose.

Ce module ne contient AUCUNE logique : il re-expose, et il expose une seule
operation d ecriture, dont le corps tient en une requete.
"""

from __future__ import annotations

import logging
import uuid

from .authz import Action, Resource, Subject, authorize, may_attempt
from .constants import ROLE_IDS, ROLE_ORGANIZER
from .models import User
from .permissions import (
    ActionPermission,
    IsApprovedOrganizer,
    MethodScopedActionPermission,
    OrganizerResourcePermission,
)

logger = logging.getLogger("fanid.identity")

__all__ = [
    "Action",
    "ActionPermission",
    "IsApprovedOrganizer",
    "MethodScopedActionPermission",
    "OrganizerResourcePermission",
    "Resource",
    "Subject",
    "authorize",
    "grant_organizer_role",
    "may_attempt",
]


def grant_organizer_role(*, user_id: uuid.UUID) -> bool:
    """
    Attribue le role `ORGANIZER` a un compte. Renvoie `True` si une ligne a change.

    **Aucune session n est revoquee, et ce n est pas un oubli.** Le lot S1-A.6a
    a fait de la relecture de session la regle : le serveur lit `user.role_id`
    en base a chaque requete, et le claim `role` du jeton n autorise rien. Le
    changement prend donc effet IMMEDIATEMENT cote serveur. Seul l affichage du
    client reste perime jusqu a son prochain rafraichissement, ce qui est une
    question d interface et non de securite.

    L identifiant du role est resolu depuis la table d UUID figes de
    `constants.py` : aucune requete sur `identity_role`. C est la meme raison
    qui a fait choisir des UUIDv5 deterministes au lot S1-A.1a.
    """
    changed = User.objects.filter(pk=user_id).update(role_id=ROLE_IDS[ROLE_ORGANIZER])
    logger.info("identity.role.granted", extra={"role": ROLE_ORGANIZER, "changed": bool(changed)})
    return bool(changed)
