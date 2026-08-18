"""
Autorisation : point unique de decision du systeme.

Surface publique volontairement etroite. Le reste du code importe d ici, pas
des sous-modules : cela laisse la liberte de reorganiser l interieur du paquet
sans toucher aux appelants, et rend un import inhabituel visible en revue.

    from apps.identity.authz import Action, Resource, Subject, authorize

Les adaptateurs DRF vivent dans `apps.identity.permissions` : ils dependent de
`rest_framework`, la ou ce paquet ne depend que de la bibliotheque standard.
Cette separation n est pas cosmetique — elle est ce qui rend la matrice
d autorisation testable sans base de donnees ni requete HTTP.
"""

from .actions import Action
from .decisions import ALLOW, Decision, Reason, deny
from .engine import authorize, may_attempt
from .rules import POLICY, Grant, Scope
from .subject import ANONYMOUS, Resource, Subject

__all__ = [
    "ALLOW",
    "ANONYMOUS",
    "POLICY",
    "Action",
    "Decision",
    "Grant",
    "Reason",
    "Resource",
    "Scope",
    "Subject",
    "authorize",
    "deny",
    "may_attempt",
]
