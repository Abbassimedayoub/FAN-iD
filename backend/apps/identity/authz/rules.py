"""
La politique : qui a le droit de faire quoi, et sous quelle condition.

CE FICHIER EST LA SOURCE DE VERITE DE L AUTORISATION (ADR-02).

`Role.permissions` en base est une colonne JSONB DESCRIPTIVE : elle sert a
afficher les droits dans une interface d administration, jamais a en decider.
Une politique stockee en base est modifiable sans revue de code, sans test et
sans trace — c est-a-dire exactement ce qu on ne veut pas d un controle
d autorisation. Ici, tout changement passe par un diff, une relecture et la
matrice de test.

Structure retenue : une table `role -> action -> Grant`. L ABSENCE d entree
signifie REFUS. Il n existe volontairement pas d effet `DENY` explicite : un
modele melangeant autorisations et interdictions oblige a definir un ordre de
precedence, et cet ordre est la source d erreur numero un des systemes de
politiques. Ici la question « ce role peut-il ? » se lit d une seule facon.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ..constants import ROLE_ADMIN, ROLE_FAN, ROLE_ORGANIZER, ROLE_SCANNER
from .actions import Action


class Scope(StrEnum):
    """Portee ABAC : sur QUELLES instances le droit s exerce."""

    #: Aucune ressource visee (creation, action de collection).
    NONE = "none"
    #: La ressource doit appartenir au sujet (`resource.owner_id`).
    SELF = "self"
    #: La ressource doit relever de l organisateur du sujet.
    OWN_ORGANIZER = "own_organizer"
    #: Aucune restriction d instance. Reserve aux roles de supervision, et
    #: toujours accompagne d une justification dans la table ci-dessous.
    ANY = "any"


@dataclass(frozen=True, slots=True)
class Grant:
    """Un droit accorde, et ses conditions."""

    scope: Scope
    #: Exige `auth_level >= AUTH_LEVEL_STEP_UP`. Reserve aux actions dont un
    #: usage abusif est IRREVERSIBLE ou permet la prise de controle du compte.
    step_up: bool = False


# --------------------------------------------------------------------------
# Libre-service : identique pour les quatre roles, par conception.
# --------------------------------------------------------------------------
# Tout humain authentifie gere son propre compte, quel que soit son role. Ce
# bloc est factorise parce que le dupliquer quatre fois inviterait a le laisser
# diverger par inadvertance. L exhaustivite reste prouvee : la matrice de test
# reecrit les 56 cellules en clair, sans reutiliser cette table (§ double
# saisie). Factoriser l implementation, jamais la verification.
_SELF_SERVICE: Final[Mapping[Action, Grant]] = MappingProxyType(
    {
        Action.USER_READ_SELF: Grant(Scope.SELF),
        Action.USER_UPDATE_SELF: Grant(Scope.SELF),
        # Suppression de compte : irreversible. Verification renforcee exigee.
        Action.USER_DELETE_SELF: Grant(Scope.SELF, step_up=True),
        Action.DEVICE_LIST_SELF: Grant(Scope.SELF),
        # Revoquer l appareil lie, c est ouvrir le compte a un nouvel appareil.
        # C est le geste que cherche a obtenir un voleur de session : il exige
        # une preuve d identite fraiche, pas un simple jeton valide.
        Action.DEVICE_REVOKE_SELF: Grant(Scope.SELF, step_up=True),
        Action.SESSION_LIST_SELF: Grant(Scope.SELF),
        # Revoquer une session RESTREINT l acces : aucune raison d en durcir
        # l acces. Exiger une verification renforcee pour se deconnecter
        # decouragerait le seul geste utile face a un vol de jeton.
        Action.SESSION_REVOKE_SELF: Grant(Scope.SELF),
    }
)


def _with_self_service(specific: Mapping[Action, Grant]) -> Mapping[Action, Grant]:
    return MappingProxyType({**_SELF_SERVICE, **specific})


POLICY: Final[Mapping[str, Mapping[Action, Grant]]] = MappingProxyType(
    {
        # ------------------------------------------------------------------
        ROLE_FAN: _with_self_service(
            {
                # Un supporter peut deposer une candidature d organisateur.
                # C est le point d entree unique de l onboarding (S1-A.8).
                Action.ORGANIZER_CREATE: Grant(Scope.NONE),
            }
        ),
        # ------------------------------------------------------------------
        ROLE_ORGANIZER: _with_self_service(
            {
                # Pas de ORGANIZER_CREATE : un compte ne porte qu un seul
                # organisateur. La regle est ici, pas seulement dans une
                # contrainte d unicite — sinon l API renverrait une erreur 500
                # de violation d integrite la ou un 403 est la bonne reponse.
                Action.ORGANIZER_READ: Grant(Scope.OWN_ORGANIZER),
                Action.ORGANIZER_UPDATE: Grant(Scope.OWN_ORGANIZER),

                # Catalogue organisateur. L approbation est un prérequis
                # actor-level supplémentaire appliqué par IsApprovedOrganizer.
                Action.CATEGORY_READ: Grant(Scope.NONE),
                Action.EVENT_CREATE: Grant(Scope.NONE),
                Action.EVENT_READ: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_UPDATE: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_PUBLISH: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_ARCHIVE: Grant(Scope.OWN_ORGANIZER),
                Action.TICKET_CATEGORY_CREATE: Grant(Scope.OWN_ORGANIZER),
                Action.TICKET_CATEGORY_READ: Grant(Scope.OWN_ORGANIZER),
                Action.TICKET_CATEGORY_UPDATE: Grant(Scope.OWN_ORGANIZER),
                Action.TICKET_CATEGORY_DELETE: Grant(Scope.OWN_ORGANIZER),
            }
        ),
        # ------------------------------------------------------------------
        ROLE_SCANNER: _with_self_service(
            {
                Action.ORGANIZER_READ: Grant(Scope.OWN_ORGANIZER),
                # Un scanner lit, il ne modifie pas la fiche organisateur.
                Action.TICKET_SCAN: Grant(Scope.OWN_ORGANIZER),
            }
        ),
        # ------------------------------------------------------------------
        ROLE_ADMIN: _with_self_service(
            {
                # `ANY` justifie : la moderation suppose de voir les dossiers
                # d autrui. C est le seul role qui y a droit, et la seule
                # portee `ANY` de la politique.
                Action.ORGANIZER_READ: Grant(Scope.ANY),
                Action.ORGANIZER_UPDATE: Grant(Scope.ANY),
                Action.ORGANIZER_APPROVE: Grant(Scope.ANY, step_up=True),
                Action.ORGANIZER_REJECT: Grant(Scope.ANY, step_up=True),
                Action.ORGANIZER_SUSPEND: Grant(Scope.ANY, step_up=True),
                # Pas de TICKET_SCAN : separation des fonctions. Un
                # administrateur n a aucune raison metier de valider un billet
                # a l entree ; s il doit le faire, on lui attribue le role
                # SCANNER, ce qui laisse une trace. « Administrateur » ne
                # signifie pas « tous les droits » — c est precisement la
                # confusion qui transforme un compte compromis en incident
                # majeur.
            }
        ),
    }
)
