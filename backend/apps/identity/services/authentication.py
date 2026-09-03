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
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.observability.metrics import fanid_auth_login_total, fanid_auth_token_refresh_total
from apps.core.outbox.publisher import publish_event

from ..constants import (
    CLIENT_WEB,
    SESSION_REVOKED_LOGOUT,
    SESSION_REVOKED_PASSWORD_CHANGE,
    SESSION_REVOKED_REPLACED,
)
from ..events import (
    AGGREGATE_USER,
    USER_LOGGED_IN,
    USER_PASSWORD_CHANGED,
    user_logged_in_payload,
    user_password_changed_payload,
)
from ..exceptions import (
    DeviceLockedError,
    DeviceMismatchError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    PasswordUnchangedError,
)
from ..models import Device, Session, User
from ..tokens import TokenExpiredError, TokenInvalidError, TokenReuseDetectedError, TokenType, decode_token
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
    client: str | None = None
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


@dataclasses.dataclass(frozen=True, slots=True)
class RefreshCommand:
    """
    Entree du rafraichissement.

    `fingerprint` n est exige que si la session porte un appareil. Une session
    ouverte depuis un navigateur, ou par un role exempte (ADR-03), n en a pas :
    lui en reclamer une reviendrait a inventer une donnee que le client ne peut
    pas produire.
    """

    refresh: str
    fingerprint: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class RefreshResult:
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

        try:
            with transaction.atomic():
                # Deux connexions Web concurrentes du meme compte doivent etre
                # serialisees. Le verrou utilisateur garantit qu une seule
                # nouvelle session Web gagne.
                if command.client == CLIENT_WEB or user.must_change_password:
                    user = User.objects.select_for_update().select_related("role").get(pk=user.pk)

                if command.client == CLIENT_WEB:
                    replaced_at = timezone.now()
                    Session.objects.filter(
                        user=user,
                        revoked_at__isnull=True,
                    ).filter(Q(client=CLIENT_WEB) | Q(client__isnull=True, device__isnull=True)).update(
                        revoked_at=replaced_at,
                        revoked_reason=SESSION_REVOKED_REPLACED,
                    )

                if user.must_change_password:
                    if user.temporary_password_used_at is not None:
                        logger.info(
                            "auth.login.failed",
                            extra={
                                "reason": ("temporary_password_already_used"),
                            },
                        )
                        fanid_auth_login_total.labels(
                            result="bad_credentials",
                        ).inc()
                        raise InvalidCredentialsError()

                if (
                    user.must_change_password
                    and user.temporary_password_expires_at is not None
                    and user.temporary_password_expires_at <= timezone.now()
                ):
                    logger.info(
                        "auth.login.failed",
                        extra={
                            "reason": ("temporary_password_expired"),
                        },
                    )

                    fanid_auth_login_total.labels(
                        result="bad_credentials",
                    ).inc()

                    raise InvalidCredentialsError()

                device = self._bind_device(
                    user,
                    command,
                )

                pair = TokenService.issue_pair(
                    user=user,
                    device=device,
                    client=command.client,
                    ip=command.ip,
                    user_agent=command.user_agent,
                )

                if user.must_change_password:
                    user.temporary_password_used_at = timezone.now()
                    user.save(
                        update_fields=[
                            "temporary_password_used_at",
                        ],
                    )

                publish_event(
                    event_type=USER_LOGGED_IN,
                    aggregate_type=AGGREGATE_USER,
                    aggregate_id=user.pk,
                    actor_id=user.pk,
                    payload=user_logged_in_payload(
                        role_name=user.role.name,
                        device_bound=device is not None,
                    ),
                )
        except DeviceLockedError:
            fanid_auth_login_total.labels(result="device_locked").inc()
            raise

        fanid_auth_login_total.labels(result="success").inc()

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
            fanid_auth_login_total.labels(result="bad_credentials").inc()
            raise InvalidCredentialsError()

        if not user.check_password(command.password):
            logger.info("auth.login.failed", extra={"reason": "bad_password"})
            fanid_auth_login_total.labels(result="bad_credentials").inc()
            raise InvalidCredentialsError()

        if not user.is_active or user.anonymized_at is not None:
            # Meme code que ci-dessus, deliberement. Un motif distinct
            # confirmerait que l adresse existe — et qu on a devine le mot de
            # passe, ce qui est encore pire.
            logger.warning("auth.login.failed", extra={"reason": "inactive_account"})
            fanid_auth_login_total.labels(result="inactive").inc()
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

    # -- rafraichissement ----------------------------------------------------

    def refresh(self, command: RefreshCommand) -> RefreshResult:
        """
        Tourne un refresh et emet une nouvelle paire.

        **L ordre est l inverse de celui de la connexion, et pour la meme
        raison.** A la connexion, l appareil passe APRES le mot de passe pour ne
        pas reveler l existence d un compte. Ici, l appareil passe AVANT la
        rotation pour ne pas CONSOMMER le jeton du porteur legitime : tourner
        d abord puis refuser sur l appareil transformerait chaque refus en
        deconnexion definitive, y compris quand le client se contente d oublier
        son empreinte.

        Le controle d appareil ne court-circuite jamais la rotation quand la
        session est introuvable — voir `_session_for`.
        """
        try:
            session = self._session_for(command.refresh)
            if session is not None and session.device is not None:
                self._binding.assert_fingerprint(
                    device=session.device,
                    fingerprint=command.fingerprint,
                )

            pair = TokenService.rotate(command.refresh)
        except TokenExpiredError:
            fanid_auth_token_refresh_total.labels(result="expired").inc()
            raise
        except TokenReuseDetectedError:
            fanid_auth_token_refresh_total.labels(result="reuse_detected").inc()
            raise
        except DeviceMismatchError:
            fanid_auth_token_refresh_total.labels(result="device_mismatch").inc()
            raise
        except TokenInvalidError:
            fanid_auth_token_refresh_total.labels(result="invalid").inc()
            raise

        fanid_auth_token_refresh_total.labels(result="success").inc()

        logger.info(
            "auth.refresh.success",
            extra={
                "session_id": str(pair.session.pk),
                "device_bound": pair.session.device is not None,
            },
        )
        return RefreshResult(user=pair.session.user, device=pair.session.device, pair=pair)

    @staticmethod
    def _session_for(raw_refresh: str) -> Session | None:
        """
        Retrouve la session dont ce refresh est le jeton COURANT — sans verrou.

        Lecture seule, dans le seul but de connaitre l appareil attendu avant de
        rotationner. Le verrou pessimiste reste ou il doit etre, dans
        `TokenService.rotate`.

        **Un jeton deja tourne ne trouve rien ici, et c est voulu.** On renvoie
        `None` sans rien refuser : la rotation DOIT s executer pour constater la
        reutilisation et revoquer la famille. Refuser des maintenant laisserait
        vivre une famille compromise — le controle passerait au vert pendant que
        la protection ne s appliquerait jamais.
        """
        claims = decode_token(raw_refresh, expected_type=TokenType.REFRESH)
        try:
            jti = uuid.UUID(str(claims.get("jti")))
        except (TypeError, ValueError):
            # Un jeton signe par nous ne devrait jamais en arriver la, mais
            # « ne devrait jamais » n est pas une garantie : passe tel quel a un
            # `UUIDField`, ce claim produirait une 500 au lieu d un 401.
            raise TokenInvalidError() from None

        return (
            Session.objects.select_related("user", "user__role", "device")
            .filter(refresh_jti=jti, revoked_at__isnull=True, expires_at__gt=timezone.now())
            .first()
        )

    # -- deconnexion ---------------------------------------------------------

    def logout(self, *, session_id: uuid.UUID) -> int:
        """
        Revoque la session courante. Renvoie le nombre de lignes touchees.

        **Une seule session, pas la famille.** Se deconnecter d un appareil ne
        doit pas fermer les autres : `revoke_family` est reserve a la detection
        de reutilisation, ou l on ne sait pas lequel des porteurs est
        l attaquant. Ici on le sait — c est celui qui demande.

        Idempotence STRUCTURELLE et non par cle (ADR-S1-03) : un second appel
        presente un jeton dont la session est deja revoquee, et
        `JWTAuthentication` le refuse avant meme d arriver ici. Aucun double
        effet possible, donc aucun besoin de rejouer une reponse.
        """
        session = Session.objects.filter(pk=session_id).first()
        if session is None:
            # La session a disparu entre l authentification et ici — purge
            # concurrente, revocation par un administrateur. Il n y a rien a
            # revoquer, et l appelant obtient le meme resultat.
            return 0

        revoked = TokenService.revoke_session(session, SESSION_REVOKED_LOGOUT)
        logger.info(
            "auth.session.revoked",
            extra={"session_id": str(session.pk), "reason": SESSION_REVOKED_LOGOUT},
        )
        return revoked

    # -- changement de mot de passe ------------------------------------------

    def change_password(self, *, user: User, current_password: str, new_password: str) -> int:
        """
        Change le mot de passe et revoque TOUTES les sessions du compte.

        **Y compris celle de l appelant.** Un mot de passe qu on change parce
        qu on le croit compromis ne sert a rien si les sessions ouvertes avec
        l ancien survivent — et epargner le navigateur qui declenche
        l operation serait exactement l exception dont un attaquant profiterait,
        puisque c est peut-etre lui qui la declenche. Le client se reconnecte.

        **L appareil n est PAS revoque.** Le liberer ouvrirait le verrou au
        moment precis ou le compte est presume compromis : le premier a se
        connecter avec le nouveau mot de passe lierait son appareil, et rien ne
        garantit que ce soit le proprietaire. Laisser la liaison en place refuse
        au contraire tout appareil etranger. Le plan n exige pas cette
        revocation ; la constante `DEVICE_REVOKED_PASSWORD_CHANGE` existe pour
        le parcours de reinitialisation (S1-A.7), pas pour ce chemin.

        La verification precede toute ecriture, et l ecriture est atomique avec
        la revocation : une panne entre les deux laisserait un mot de passe
        change avec les anciennes sessions vivantes — le pire etat possible.
        """
        if not user.check_password(current_password):
            logger.warning(
                "auth.password_change.failed",
                extra={"user_id": str(user.pk), "reason": "bad_current_password"},
            )
            raise InvalidCurrentPasswordError(
                details={"current_password": ["Le mot de passe actuel est incorrect."]}
            )

        if user.check_password(new_password):
            raise PasswordUnchangedError(
                details={"new_password": ["Le nouveau mot de passe doit etre different de l ancien."]}
            )

        temporary_credential_replaced = bool(user.must_change_password)

        with transaction.atomic():
            user.set_password(new_password)

            user.must_change_password = False

            user.save(
                update_fields=[
                    "password",
                    "must_change_password",
                ],
            )

            revoked = TokenService.revoke_all_for_user(
                user,
                SESSION_REVOKED_PASSWORD_CHANGE,
            )

            publish_event(
                event_type=USER_PASSWORD_CHANGED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=(
                    user_password_changed_payload(
                        temporary_credential_replaced=(temporary_credential_replaced),
                    )
                ),
            )

        logger.info(
            "auth.session.revoked",
            extra={"user_id": str(user.pk), "reason": SESSION_REVOKED_PASSWORD_CHANGE, "sessions": revoked},
        )
        return revoked
