"""
Politique de hachage des mots de passe (ADR-S-04 règle 5, plan Sprint 1 §5.1).

Django fournit `Argon2PasswordHasher`, qui utilise **Argon2id** (`argon2.low_level.Type.ID`)
— la variante recommandée par l'OWASP, résistante à la fois aux attaques par canal auxiliaire
et par compromis temps-mémoire.

Les paramètres par défaut de Django ne sont PAS ceux exigés par le plan : on les fixe
explicitement ici plutôt que de dépendre d'une valeur par défaut qui peut changer d'une
version de Django à l'autre — un durcissement silencieux est aussi indésirable qu'un
affaiblissement silencieux, car il déplacerait la latence de `POST /auth/login` (cible
p95 < 400 ms) sans que personne ne l'ait décidé.

En environnement de test, `config/settings/test.py` substitue un hacheur rapide : le coût
d'Argon2id ferait passer la suite de quelques secondes à plusieurs minutes. La production et
le développement ne sont JAMAIS affaiblis (§12 du prompt d'exécution).
"""

from django.contrib.auth.hashers import Argon2PasswordHasher


class FanIdArgon2PasswordHasher(Argon2PasswordHasher):
    """Argon2id aux paramètres imposés par le plan Sprint 1 §5.1 (OWASP A02)."""

    #: Nombre d'itérations.
    time_cost = 3
    #: Mémoire en **kibioctets** — 65536 Kio = 64 Mio.
    memory_cost = 65536
    #: Nombre de voies parallèles.
    parallelism = 4
