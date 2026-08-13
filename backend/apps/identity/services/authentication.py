"""
`AuthenticationService` — la connexion, et l ordre non negociable.

## L ordre des controles

1. identifiants (mot de passe Argon2id)
2. etat du compte
3. **ensuite seulement** le verrou d appareil
4. emission des jetons

Inverser les etapes 1 et 3 revelerait l existence d un compte a qui n a rien
prouve : presenter un mot de passe faux sur une adresse verrouillee renverrait
`403 DEVICE_LOCKED`, alors que la meme tentative sur une adresse inconnue
renverrait `401`. L attaquant obtient alors un oracle d existence parfait, sans
jamais deviner un seul mot de passe.

C est la raison pour laquelle `DeviceLockedError` n est levee qu apres que le
mot de passe a ete prouve — et un test le fige explicitement.

## Anti-enumeration : le corps ET le temps

Trois situations donnent exactement la meme reponse : adresse inconnue, mot de
passe faux, compte desactive. Meme code, meme message, aucun detail.

Mais un corps identique ne suffit pas. Si l adresse est inconnue, il n y a aucun
hachage a verifier : la reponse revient en une milliseconde au lieu des ~200 ms
que coute Argon2id. Le temps de reponse devient alors l oracle que le corps
refusait de donner. On hache donc un mot de passe FACTICE dans ce cas, pour que
les deux chemins coutent la meme chose.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from apps.core.outbox.publisher import publish_event

from ..events import AGGREGATE_USER, USER_LOGGED_IN, user_logged_in_payload
from ..exceptions import InvalidCredentialsError
from ..models import Device, User
from .devices import DeviceBindingService
from .tokens import IssuedPair, TokenService

logger = logging.getLogger("fanid.identity")


@functools.lru_cache(maxsize=1)
def _decoy_hash() -> str:
    """
    Hachage factice, calcule une seule fois par processus.

    Il sert a faire payer a une adresse INCONNUE le meme cout qu a une adresse
    connue. Le secret hache est tire au hasard au demarrage : personne, pas meme
    le code, ne connait le mot de passe correspondant, donc aucune comparaison
    ne peut reussir par accident.

    Mis en cache parce que `make_password` avec Argon2id coute ~200 ms : le
    calculer a chaque tentative echouee offrirait a un attaquant un moyen de
    saturer le processeur avec des adresses inexistantes.
    """
    return make_password(secrets.token_urlsafe(32))


@dataclasses.dataclass(frozen=True, slots=True)
class LoginCommand:
    """
    Entree du service.

    `fingerprint` est FACULTATIF : un supporter qui se connecte depuis un
    navigateur n en fournit pas, et il n y a alors aucun appareil a lier. Le
    verrou ne s applique qu a partir du moment ou une empreinte existe — c est
    le client mobile qui en fournit une (plan §3.3).
    """

    email: str
    password: str
    fingerprint: str | None = None
    platform: str | None = None
    label: str = ""
    ip: str | None = None
    user_agent: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    device: Device | None
    pair: IssuedPair


class AuthenticationService:
    """Connexion : identifiants, appareil, jetons — dans cet ordre."""

    def __init__(self, binding: DeviceBindingService) -> None:
        self._binding = binding

    def login(self, command: LoginCommand) -> LoginResult:
        """
        Ouvre une session. Leve `InvalidCredentialsError` (401) ou
        `DeviceLockedError` (403), jamais l inverse.
        """
        user = self._verify_credentials(command)

        with transaction.atomic():
            device = self._bind_device(user, command)
            pair = TokenService.issue_pair(
                user=user,
                device=device,
                ip=command.ip,
                user_agent=command.user_agent,
            )
            publish_event(
                event_type=USER_LOGGED_IN,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=user_logged_in_payload(role_name=user.role.name, device_bound=device is not None),
            )

        # Ni adresse, ni empreinte, ni jeton. Le `correlation_id` pose par le
        # middleware relie cette ligne a la requete, qui porte le reste.
        logger.info(
            "auth.login.success",
            extra={"session_id": str(pair.session.pk), "device_bound": device is not None},
        )
        return LoginResult(user=user, device=device, pair=pair)

    # -- etape 1 : les identifiants -----------------------------------------

    def _verify_credentials(self, command: LoginCommand) -> User:
        """
        Trois echecs, une seule reponse : adresse inconnue, mot de passe faux,
        compte desactive ou anonymise.

        La recherche est insensible a la casse sans `LOWER()` : la colonne est
        de type `citext` (lot S1-A.1a), donc l index unique reste utilisable.
        """
        user = User.objects.select_related("role").filter(email=command.email).first()

        if user is None:
            # Le hachage factice n est PAS une precaution theorique : sans lui,
            # une adresse inconnue repond en une milliseconde la ou une adresse
            # connue coute le temps d Argon2id. La difference se mesure depuis
            # l exterieur, et suffit a enumerer les comptes.
            check_password(command.password, _decoy_hash())
            logger.info("auth.login.failed", extra={"reason": "unknown_email"})
            raise InvalidCredentialsError()

        if not user.check_password(command.password):
            logger.info("auth.login.failed", extra={"reason": "bad_password"})
            raise InvalidCredentialsError()

        if not user.is_active or user.anonymized_at is not None:
            # Meme code que ci-dessus, deliberement. Un motif distinct
            # confirmerait que l adresse existe — et qu on a devine le mot de
            # passe, ce qui est encore pire.
            logger.warning("auth.login.failed", extra={"reason": "inactive_account"})
            raise InvalidCredentialsError()

        return user

    # -- etape 2 : l appareil, APRES les identifiants ------------------------

    def _bind_device(self, user: User, command: LoginCommand) -> Device | None:
        """
        Lie l appareil si le client en fournit un.

        Aucune empreinte fournie : aucun appareil lie, et la session s ouvre
        sans `did`. Le verrou ne s applique qu a partir du moment ou une
        empreinte existe — exiger une empreinte du navigateur reviendrait a
        inventer une donnee que le client ne peut pas produire de facon stable.

        Un role exempte (ADR-03) ignore l empreinte meme si elle est fournie :
        le service d appareil s en charge et renvoie `None`.
        """
        if command.fingerprint is None:
            return None
        return self._binding.bind(
            user=user,
            fingerprint=command.fingerprint,
            platform=command.platform or "",
            label=command.label,
        )
