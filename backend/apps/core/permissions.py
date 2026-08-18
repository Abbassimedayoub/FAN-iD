"""
Permission par defaut du projet.

`DenyAll` vit dans `core` et non dans `identity` parce qu il ne consulte AUCUNE
politique : il n y a pas de decision a prendre, l absence de regle EST la
reponse. C est un garde-fou de cadriciel, pas une regle metier — et `core` ne
depend d aucun contexte borne (ADR-S-01), ce qui lui permet de servir de defaut
a tout le projet sans creer de dependance vers `identity`.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework.permissions import BasePermission

logger = logging.getLogger("fanid.authz")


class DenyAll(BasePermission):
    """
    Refus inconditionnel — valeur de `DEFAULT_PERMISSION_CLASSES`.

    Le vrai risque d un systeme d autorisation n est pas la regle fausse : c est
    la vue qui n en porte AUCUNE.

    Le defaut precedent du projet, `IsAuthenticated`, etait deja bien meilleur
    que celui de DRF (`AllowAny`), mais il laisse passer TOUT utilisateur
    authentifie. Sur une plateforme ou un supporter, un organisateur, un scanner
    et un administrateur partagent la meme API, « etre connecte » n est pas une
    autorisation : un point de terminaison d administration dont on aurait
    oublie `permission_classes` serait accessible a n importe quel compte cree
    en trente secondes depuis le formulaire d inscription.

    Avec `DenyAll`, le meme oubli produit un 403 des le premier appel, en
    developpement, avec un journal de niveau ERREUR qui nomme la vue fautive.

    Corollaire assume : toute vue publique doit declarer explicitement
    `permission_classes = [AllowAny]`. C est une ligne de plus, et c est une
    ligne qui se relit en revue de code — contrairement a une absence.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        logger.error(
            "authorization.view_without_policy",
            extra={"authz_view": type(view).__name__},
        )
        return False

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        return False
