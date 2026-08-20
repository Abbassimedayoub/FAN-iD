"""
Le sujet et la ressource d une decision d autorisation.

Ces deux structures sont volontairement des dataclasses gelees, sans aucune
dependance a Django. Trois consequences recherchees :

1. le moteur devient une fonction pure, donc testable sans base de donnees —
   la matrice complete des roles et des actions s execute en millisecondes,
   ce qui rend realiste de la tester EXHAUSTIVEMENT plutot que par sondage ;
2. la traduction `HttpRequest -> Subject` est isolee dans un seul module
   (`context.py`), donc auditable d un coup d oeil ;
3. le moteur ne peut pas declencher de requete SQL par inadvertance au milieu
   d une decision d autorisation — une requete implicite dans un chemin
   d autorisation est une source classique de N+1 et d effets de bord.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Subject:
    """
    L acteur d une requete, reduit aux seuls attributs qui portent une decision.

    `frozen=True` interdit qu un maillon intermediaire — serialiseur, vue,
    signal — modifie le role ou le niveau d authentification apres coup. Une
    escalade de privileges par mutation d objet devient structurellement
    impossible, pas seulement improbable.
    """

    user_id: uuid.UUID | None = None
    role: str | None = None
    is_active: bool = False
    # 1 = mot de passe, 2 = verification renforcee. La valeur par defaut est le
    # niveau le PLUS BAS : un contexte incomplet ne doit jamais ouvrir de droit.
    auth_level: int = 0
    # Renseigne pour un ORGANIZER ou un SCANNER rattache a un organisateur.
    organizer_id: uuid.UUID | None = None
    # Primitif pose par le contexte proprietaire. False par defaut : une requete
    # non enrichie ne doit jamais etre consideree comme approuvee par omission.
    organizer_is_approved: bool = False

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None and self.role is not None


#: Sujet de repli pour toute requete non authentifiee. Une constante partagee
#: evite qu un appelant fabrique un anonyme legerement different — par exemple
#: avec `is_active=True` — et ouvre un chemin d autorisation involontaire.
ANONYMOUS = Subject()


@dataclass(frozen=True, slots=True)
class Resource:
    """
    Les attributs de la ressource visee, pour la couche ABAC.

    Tous les champs sont facultatifs et valent `None` par defaut. Un attribut
    absent n est JAMAIS interprete comme « pas de restriction » : le moteur
    refuse avec `DENIED_RESOURCE_ATTRIBUTE_MISSING`. C est le sens de
    « fail-closed » applique a la lettre — une regle qui exige un proprietaire
    et ne trouve pas de proprietaire doit refuser, pas passer.
    """

    owner_id: uuid.UUID | None = None
    organizer_id: uuid.UUID | None = None
    #: Etat de la machine a etats de la ressource, quand elle en a une.
    #: Non exploite au Sprint 1 ; le lot S1-A.8 y branchera les transitions
    #: d `Organizer`. Present des maintenant pour que le branchement n exige
    #: pas de modifier la signature du moteur.
    state: str | None = None
