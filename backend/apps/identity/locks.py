"""
Verrou d appareil : implementation PostgreSQL et composition resiliente.

## Redis n est pas la source de verite

C est la decision qui structure tout ce module. L appareil actif d un compte est
defini par la contrainte `UNIQUE(user_id) WHERE revoked_at IS NULL` posee au lot
S1-A.1b. Redis n est qu un **cache de decision** : il evite une requete SQL sur
le chemin le plus chaud de la plateforme — l ouverture des portes d un stade,
quand des milliers d applications se reveillent en meme temps.

Le corollaire est ce qui rend le « jamais fail-open » realisable sans acrobatie :
si Redis tombe, on ne perd RIEN. On retombe sur la verite, plus lente mais
exacte. Le piege inverse — traiter Redis comme la verite et PostgreSQL comme un
repli approximatif — obligerait, le jour d une panne, a choisir entre bloquer
tout le monde et laisser tout passer.

## Pourquoi ce module vit dans `identity` et non dans `core`

Le PORT (`DeviceLockBackend`) appartient a `core`, avec son implementation Redis
generique. Le repli, lui, doit lire `identity_device` : le placer dans `core`
ferait dependre le socle d un contexte borne et briserait ADR-S-01, verifie par
import-linter. `identity` a le droit de dependre de `core` — jamais l inverse.

La composition (`ResilientDeviceLock`) suit le repli : decider ce qui est
principal, ce qui est secondaire et ce qui compte comme une panne est une
decision du contexte qui possede la regle metier.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.core.interfaces import DeviceLockBackend

from .models import Device

logger = logging.getLogger("fanid.identity")

try:  # pragma: no cover - depend de l environnement d execution
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - Redis absent : le repli reste utilisable

    class RedisError(Exception):  # type: ignore[no-redef]
        """Repli de type si le client Redis n est pas installe."""


#: Pannes considerees comme TRANSITOIRES, donc justifiant le repli.
#:
#: Volontairement etroit. Attraper `Exception` ferait passer une faute de frappe
#: dans le code du verrou pour une panne d infrastructure : le repli
#: fonctionnerait, personne ne verrait rien, et le bug survivrait des mois.
TRANSIENT_FAILURES: tuple[type[BaseException], ...] = (RedisError, OSError, TimeoutError)


class PostgresDeviceLock(DeviceLockBackend):
    """
    Repli : la source de verite elle-meme.

    Aucune table de verrou dediee. La question « cet appareil peut-il etre lie a
    ce compte ? » a deja une reponse en base — l unicite partielle sur
    `identity_device`. Ajouter une table de verrous creerait un second etat a
    maintenir coherent avec le premier, donc une occasion de divergence, pour
    aucun gain.
    """

    def acquire(self, user_id: str, device_id: str, ttl_seconds: int) -> bool:
        """
        `ttl_seconds` est IGNORE, et ce n est pas un oubli.

        Un verrou Redis expire parce qu il pourrait rester orphelin si le
        processus qui le detient meurt. La verite en base, elle, n expire pas :
        un appareil reste lie tant qu il n a pas ete revoque, ce qui est une
        operation metier tracee. Faire expirer ce lien au bout de quelques
        minutes delierait silencieusement les comptes.
        """
        active = self.get_active(user_id)
        return active is None or active == str(device_id)

    def get_active(self, user_id: str) -> Any | None:
        device_id = Device.objects.active().filter(user_id=user_id).values_list("id", flat=True).first()
        return str(device_id) if device_id is not None else None

    def release(self, user_id: str) -> None:
        """
        Sans effet, deliberement.

        Le verrou n est pas une ressource distincte qu on rendrait : il EST la
        ligne `device`. La liberer signifierait revoquer l appareil — une
        operation metier qui exige un motif, laisse une trace d audit et passe
        par `DeviceBindingService.revoke()`. Un `release()` silencieux offrirait
        un chemin de deliaison sans motif ni trace.
        """
        return None


class ResilientDeviceLock(DeviceLockBackend):
    """
    Verrou principal avec repli sur panne transitoire.

    **Jamais fail-open.** Si le principal echoue, on interroge le repli. Si le
    repli echoue AUSSI, l exception remonte : la requete part en erreur et
    l acces est refuse. Une panne d infrastructure ne doit jamais se traduire
    par un assouplissement de la securite — c est le sens de la regle, et le
    chemin le plus tentant a coder est precisement l inverse (`except: return
    True`).
    """

    def __init__(self, primary: DeviceLockBackend, fallback: DeviceLockBackend) -> None:
        self._primary = primary
        self._fallback = fallback

    def _with_fallback(self, operation: str, *args: Any) -> Any:
        try:
            return getattr(self._primary, operation)(*args)
        except TRANSIENT_FAILURES as exc:
            # Niveau AVERTISSEMENT et non ERREUR : le service continue de
            # fonctionner correctement, plus lentement. Une alerte de niveau
            # erreur sur un repli qui marche use l attention de l equipe.
            logger.warning(
                "device_lock.fallback_engaged",
                extra={"lock_operation": operation, "failure": type(exc).__name__},
            )
            return getattr(self._fallback, operation)(*args)

    def acquire(self, user_id: str, device_id: str, ttl_seconds: int) -> bool:
        return bool(self._with_fallback("acquire", user_id, device_id, ttl_seconds))

    def get_active(self, user_id: str) -> Any | None:
        return self._with_fallback("get_active", user_id)

    def release(self, user_id: str) -> None:
        self._with_fallback("release", user_id)


def build_device_lock() -> DeviceLockBackend:
    """
    Assemble le verrou reel : Redis en principal, PostgreSQL en repli.

    Construit a la demande plutot qu au demarrage : un client Redis fabrique a
    l import empecherait le processus de demarrer quand Redis est indisponible —
    exactement la panne que ce module est cense absorber.
    """
    import redis

    client = redis.Redis.from_url(settings.REDIS_LOCK_URL)
    from apps.core.adapters.device_lock import RedisDeviceLock

    return ResilientDeviceLock(primary=RedisDeviceLock(client), fallback=PostgresDeviceLock())
