"""
Traduction `HttpRequest -> Subject`. Seul endroit du code qui connait Django ET
le moteur d autorisation.

Deux exigences ont guide ce module.

**Aucune requete SQL.** Le role est resolu depuis `user.role_id`, une colonne
deja chargee avec l utilisateur, en la faisant passer par la table d identifiants
figes de `constants.py`. Ecrire `user.role.name` couterait UNE REQUETE PAR
CONTROLE D AUTORISATION — donc plusieurs par requete HTTP, sur le chemin le plus
chaud de l API, et invisible en test unitaire. Les identifiants de role sont des
UUIDv5 deterministes precisement pour permettre cette resolution hors base.

**Aucun silence.** Un role absent du referentiel ne produit pas un sujet
anonyme — ce qui donnerait le motif `UNAUTHENTICATED` et enverrait le lecteur
des journaux chercher un probleme de jeton inexistant — mais un role sentinelle
qui declenche `UNKNOWN_ROLE`. Le refus est le meme ; le diagnostic ne l est pas.
"""

from __future__ import annotations

import uuid
from typing import Any, Final

from ..constants import AUTH_LEVEL_PASSWORD, ROLE_IDS
from .subject import ANONYMOUS, Subject

#: Table inverse `UUID -> nom de role`, construite une fois au chargement.
ROLE_NAMES_BY_ID: Final[dict[uuid.UUID, str]] = {role_id: name for name, role_id in ROLE_IDS.items()}

#: Role attribue quand `role_id` ne correspond a aucun role connu du code.
#: Il n est present dans aucune politique, donc il n accorde rien.
UNKNOWN_ROLE: Final = "__unknown__"


def _organizer_id_from(request: Any) -> uuid.UUID | None:
    """
    Organisateur de rattachement, LU SUR LA REQUETE.

    `identity` ignore qu `organizing` existe (ADR-S1-05) : c est le contexte
    proprietaire qui pose ce primitif avant que DRF ne controle les
    permissions. Le mecanisme est exactement celui d `auth_level`, quelques
    lignes plus bas.

    Le controle de type n est pas une concession au verificateur : une valeur
    inattendue doit produire l ABSENCE de droit, pas une exception au milieu
    d un controle d autorisation. Une requete non enrichie donne donc `None`,
    et le moteur refuse toute portee `OWN_ORGANIZER` avec
    `RESOURCE_ATTRIBUTE_MISSING`.

    Remplace `resolve_organizer_id()`, supprimee au lot S1-A.8a : la remplir
    aurait coute une requete SQL par controle d autorisation, sur le chemin le
    plus chaud de l API.
    """
    value = getattr(request, "organizer_id", None)
    return value if isinstance(value, uuid.UUID) else None


def _organizer_is_approved_from(request: Any) -> bool:
    """
    Etat d approbation LU SUR LA REQUETE, sans dependance vers `organizing`.

    Seul un booleen explicite est accepte. Une valeur absente ou d un autre type
    devient False : le contexte incomplet reste fail-closed.
    """
    value = getattr(request, "organizer_approved", False)
    return value if isinstance(value, bool) else False


def subject_from_request(request: Any) -> Subject:
    """Construit le sujet d autorisation a partir de la requete entrante."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return ANONYMOUS

    # `role_id` est lu en `Any` : le sujet peut etre un vrai `User` comme un
    # double de test. Le controle de type n est donc pas une concession a
    # mypy — c est ce qui garantit qu une valeur inattendue (chaine, None,
    # entier) donne UNKNOWN_ROLE, donc AUCUN droit, au lieu de lever une
    # exception au milieu d un controle d autorisation.
    role_id: Any = getattr(user, "role_id", None)
    role = ROLE_NAMES_BY_ID.get(role_id, UNKNOWN_ROLE) if isinstance(role_id, uuid.UUID) else UNKNOWN_ROLE

    # Un compte anonymise (RGPD) reste techniquement authentifiable tant que ses
    # jetons courent. Il est traite comme inactif : plus aucun droit, y compris
    # sur ses propres donnees, puisqu il n y a plus de donnees a lui.
    is_active = bool(getattr(user, "is_active", False)) and getattr(user, "anonymized_at", None) is None

    return Subject(
        user_id=user.pk,
        role=role,
        is_active=is_active,
        # Extension du lot S1-A.4 : le middleware de session posera le niveau
        # reel porte par le jeton. En son absence, on retient le niveau le plus
        # BAS — un contexte incomplet refuse les actions renforcees au lieu de
        # les accorder.
        auth_level=int(getattr(request, "auth_level", AUTH_LEVEL_PASSWORD)),
        organizer_id=_organizer_id_from(request),
        organizer_is_approved=_organizer_is_approved_from(request),
    )
