"""
Référentiel des rôles (plan S1 §3.1, table `role`).

Les identifiants sont **fixes et dérivés de façon déterministe** (UUIDv5) plutôt
que générés à la volée. Trois raisons :

1. La migration qui ajoute `user.role_id` en NOT NULL a besoin d'une valeur par
   défaut connue à l'écriture de la migration — un UUID tiré au hasard au moment
   du seed ne le permettrait pas.
2. Les identifiants sont identiques en développement, en test, en CI et en
   production : une fixture ou un jeu de données de démonstration reste valide
   partout.
3. Le seed devient réellement idempotent : rejouer la migration ne crée pas de
   doublon sous un nouvel identifiant.

ADR-02 : `Role.permissions` (jsonb) est **descriptif**, affiché dans la console
d'administration. Il n'est JAMAIS la source de vérité de l'autorisation — c'est
le `PolicyEngine`, en code, qui fait foi (master prompt §10).
"""

import uuid

ROLE_FAN = "FAN"
ROLE_ORGANIZER = "ORGANIZER"
ROLE_SCANNER = "SCANNER"
ROLE_ADMIN = "ADMIN"

#: Ordre stable, utilisé par la contrainte CHECK et par les tests de matrice.
ROLE_NAMES: tuple[str, ...] = (ROLE_FAN, ROLE_ORGANIZER, ROLE_SCANNER, ROLE_ADMIN)

#: Rôle attribué à toute inscription publique (master prompt §11 : l'inscription
#: publique ne permet aucune attribution arbitraire de privilège).
DEFAULT_ROLE = ROLE_FAN

ROLE_IDS: dict[str, uuid.UUID] = {
    ROLE_FAN: uuid.UUID("80d63969-f419-5bd6-b682-653e21e74a65"),
    ROLE_ORGANIZER: uuid.UUID("ea173779-0ab3-56b8-9924-23915ef7fc29"),
    ROLE_SCANNER: uuid.UUID("91e56bcb-d23e-5169-a1f3-655e1e44f277"),
    ROLE_ADMIN: uuid.UUID("58d71579-cab7-576e-b233-27c1c424b8bd"),
}
