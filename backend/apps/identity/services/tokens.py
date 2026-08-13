"""
`TokenService` — cycle de vie des jetons : emission, rotation, revocation.

`tokens.py` sait signer et verifier. Ce module sait ce qu un jeton VAUT : quelle
session il represente, s il a deja servi, et quoi faire quand il ressert.

## Le modele : usage unique strict, revocation par famille

Une connexion ouvre une FAMILLE. La famille est materialisee par une ligne
`identity_session` qui porte le `jti` du refresh COURANT. Chaque rotation
remplace ce `jti` : l ancien ne correspond alors plus a aucune ligne.

Rejouer un refresh deja tourne est donc detectable par une simple absence — et
c est tout l interet du dispositif. La reponse n est pas de refuser ce jeton,
mais de **revoquer la famille entiere**, y compris le refresh legitime emis une
seconde plus tot. La raison est qu on ne sait pas lequel des deux porteurs est
l attaquant : celui qui rejoue peut etre le voleur comme la victime. Deconnecter
les deux est le seul choix sur.

## Ce que cela coute, et pourquoi on l accepte

Deux rafraichissements LEGITIMES concurrents — l onglet qui recharge pendant
qu une requete de fond expire — sont **indiscernables** d un vol. Le perdant de
la course declenche la revocation, donc une deconnexion.

C est le comportement attendu (RFC 6819 §5.2.2.3), et la parade est cote client :
le plan impose de serialiser les rafraichissements derriere un seul verrou en
vol (§ « Points d attention React »). Adoucir la regle cote serveur — une fenetre
de grace de quelques secondes pendant laquelle l ancien `jti` reste valable —
rendrait le vol indetectable exactement dans la fenetre ou il est le plus
probable, juste apres l interception.

## Verrou pessimiste, pas optimiste

`SELECT ... FOR UPDATE` sur la ligne de session pendant la rotation. Sans lui,
deux rotations concurrentes liraient la meme ligne et ecriraient deux `jti`
differents : **deux refresh valides pour une seule session**, ce qui supprime
purement et simplement la detection de reutilisation.

Le verrouillage optimiste (`version`) ne conviendrait pas : il detecte le
conflit APRES coup, en refusant la seconde ecriture, alors qu ici il faut que la
seconde transaction RELISE l etat mis a jour pour constater que le `jti` a
change. C est precisement ce que fait `FOR UPDATE` en lecture confirmee.
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
import uuid
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..constants import AUTH_LEVEL_PASSWORD
from ..models import Device, Session, User
from ..tokens import TokenInvalidError, TokenReuseDetectedError, TokenType, decode_token, encode_token

logger = logging.getLogger("fanid.identity")

#: Motifs de revocation. Contraints en base par `ck_session_revoked_reason_valid`.
REASON_LOGOUT = "LOGOUT"
REASON_ROTATION_REUSE = "ROTATION_REUSE"
REASON_PASSWORD_CHANGE = "PASSWORD_CHANGE"
REASON_ADMIN = "ADMIN"
REASON_DEVICE_RESET = "DEVICE_RESET"


class _ReuseSignal(Exception):
    """
    Signal INTERNE : une reutilisation vient d etre constatee.

    Il ne sort jamais de ce module. Son unique role est de faire remonter le
    constat HORS de la transaction de rotation, parce que la revocation qui en
    decoule ne doit surtout pas etre annulee avec elle (voir `rotate`).
    """

    def __init__(self, family_id: uuid.UUID) -> None:
        self.family_id = family_id
        super().__init__(str(family_id))


def _as_uuid(value: Any) -> uuid.UUID | None:
    """Convertit un claim en UUID, ou `None` si la valeur n en est pas un."""
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


@dataclasses.dataclass(frozen=True, slots=True)
class IssuedPair:
    """Une paire de jetons et la session qui la porte."""

    access: str
    refresh: str
    session: Session
    access_expires_at: datetime.datetime
    refresh_expires_at: datetime.datetime


def _access_lifetime() -> datetime.timedelta:
    return datetime.timedelta(minutes=int(settings.JWT_ACCESS_LIFETIME_MINUTES))


def _refresh_lifetime() -> datetime.timedelta:
    return datetime.timedelta(days=int(settings.JWT_REFRESH_LIFETIME_DAYS))


class TokenService:
    """Emission, rotation et revocation des jetons."""

    # -- emission -----------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def issue_pair(
        *,
        user: User,
        device: Device | None = None,
        family_id: uuid.UUID | None = None,
        auth_level: int = AUTH_LEVEL_PASSWORD,
        ip: str | None = None,
        user_agent: str = "",
        now: datetime.datetime | None = None,
    ) -> IssuedPair:
        """
        Ouvre une session et emet la paire correspondante.

        La ligne `session` est construite AVANT la signature : son identifiant
        alimente le claim `sid`, et son `refresh_jti` doit valoir exactement le
        `jti` du refresh emis. C est possible sans aller-retour en base parce que
        toutes les cles primaires du projet sont des UUID a valeur par defaut —
        l identifiant existe des la construction de l objet, avant l INSERT.
        """
        moment = now or timezone.now()
        session = Session(
            user=user,
            device=device,
            family_id=family_id or uuid.uuid4(),
            auth_level=auth_level,
            ip=ip,
            # Tronque plutot que rejete : un `User-Agent` de 300 caracteres est
            # une curiosite d audit, pas une raison de refuser une connexion.
            user_agent=(user_agent or "")[:255],
            issued_at=moment,
            last_used_at=moment,
        )
        pair = TokenService._sign_pair(session=session, user=user, device=device, now=moment)
        session.save()
        logger.info(
            "auth.session.opened",
            extra={"session_id": str(session.pk), "auth_level": auth_level},
        )
        return pair

    @staticmethod
    def _sign_pair(
        *,
        session: Session,
        user: User,
        device: Device | None,
        now: datetime.datetime,
    ) -> IssuedPair:
        """
        Signe une paire pour une session donnee et aligne la ligne dessus.

        Mute `session` sans la sauvegarder : l appelant choisit le moment de
        l ecriture, ce qui permet a `issue_pair` de faire un INSERT et a
        `rotate` un UPDATE cible, tous deux dans une transaction deja ouverte.
        """
        refresh, refresh_jti, refresh_expires_at = encode_token(
            token_type=TokenType.REFRESH,
            subject=user.pk,
            lifetime=_refresh_lifetime(),
            claims={"family": str(session.family_id)},
            issued_at=now,
        )
        access, _, access_expires_at = encode_token(
            token_type=TokenType.ACCESS,
            subject=user.pk,
            lifetime=_access_lifetime(),
            claims={
                # Le role voyage dans le jeton : sans lui, chaque controle
                # d autorisation couterait une requete (plan §3.5). Corollaire
                # assume : un changement de role ne prend effet qu au
                # rafraichissement suivant, soit 15 minutes au pire.
                "role": user.role.name,
                "did": str(device.pk) if device is not None else None,
                "sid": str(session.pk),
                "auth_level": session.auth_level,
            },
            issued_at=now,
        )
        session.refresh_jti = refresh_jti
        session.expires_at = refresh_expires_at
        session.last_used_at = now
        return IssuedPair(
            access=access,
            refresh=refresh,
            session=session,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    # -- rotation -----------------------------------------------------------

    @staticmethod
    def rotate(raw_refresh: str, *, now: datetime.datetime | None = None) -> IssuedPair:
        """
        Consomme un refresh et en emet un nouveau. Usage unique strict.

        Leve `TokenReuseDetectedError` — et revoque la famille — si le jeton
        presente a deja ete tourne.
        """
        claims = decode_token(raw_refresh, expected_type=TokenType.REFRESH)
        moment = now or timezone.now()

        try:
            with transaction.atomic():
                session = TokenService._lock_current_session(claims, moment)
                pair = TokenService._sign_pair(
                    session=session,
                    user=session.user,
                    device=session.device,
                    now=moment,
                )
                session.save(update_fields=["refresh_jti", "expires_at", "last_used_at"])
        except _ReuseSignal as signal:
            # LA REVOCATION DOIT SURVIVRE AU REJET DE LA ROTATION.
            #
            # Revoquer a l interieur du bloc `atomic` serait annule par la remontee
            # de l exception : la famille resterait vivante, et l attaquant
            # pourrait rejouer indefiniment un jeton que le systeme declare
            # pourtant compromis. Le controle passe donc au vert — l erreur est
            # bien levee — pendant que la protection ne s applique jamais.
            #
            # On sort donc de la transaction AVANT de revoquer, en signalant le
            # constat par une exception interne.
            revoked = TokenService.revoke_family(signal.family_id, REASON_ROTATION_REUSE, now=moment)
            logger.warning(
                "auth.token.reuse_detected",
                extra={"family_id": str(signal.family_id), "sessions_revoked": revoked},
            )
            raise TokenReuseDetectedError() from None

        logger.info("auth.token.rotated", extra={"session_id": str(session.pk)})
        return pair

    @staticmethod
    def _lock_current_session(claims: dict[str, Any], now: datetime.datetime) -> Session:
        """
        Verrouille la session dont ce refresh est le jeton COURANT.

        En lecture confirmee, `SELECT ... FOR UPDATE` bloque sur une ligne
        verrouillee puis **reevalue la condition** apres liberation. C est ce qui
        fait que le perdant d une course ne trouve plus la ligne : le gagnant a
        change `refresh_jti` entre-temps. La detection de reutilisation tombe
        donc juste, sans horodatage ni comparaison de dates.
        """
        # Les deux identifiants sont convertis AVANT toute requete. Django
        # leverait `ValidationError` — donc une 500 — sur un UUID mal forme
        # passe a un `UUIDField`. Un jeton signe par nous ne devrait jamais en
        # contenir, mais « ne devrait jamais » n est pas une garantie : c est le
        # genre d hypothese qui transforme une anomalie en erreur serveur.
        jti = _as_uuid(claims.get("jti"))
        family_id = _as_uuid(claims.get("family"))
        if jti is None:
            raise TokenInvalidError()

        try:
            return (
                # `of=("self",)` : on verrouille la ligne de SESSION, et elle seule.
                #
                # Sans cette precision, PostgreSQL refuse carrement la requete —
                # « FOR UPDATE cannot be applied to the nullable side of an outer
                # join » — parce que `device` est nullable, donc joint en LEFT
                # JOIN. Le refus est une chance : sans lui, la version verrouillant
                # toutes les tables jointes serait passee, et chaque rotation
                # aurait verrouille la ligne de `identity_role` correspondante.
                # Quatre lignes de role pour toute la plateforme : TOUTES les
                # rotations des supporters se seraient serialisees derriere un
                # unique verrou global, avec un effondrement du debit visible
                # seulement en charge.
                Session.objects.select_for_update(of=("self",))
                .select_related("user", "user__role", "device")
                .get(refresh_jti=jti, revoked_at__isnull=True, expires_at__gt=now)
            )
        except Session.DoesNotExist:
            pass

        if family_id and Session.objects.filter(family_id=family_id, revoked_at__isnull=True).exists():
            # Le jeton est bien signe par nous, sa famille est vivante, mais il
            # n est plus le refresh courant : il a donc DEJA ete tourne.
            # La revocation est confiee a `rotate`, hors transaction.
            raise _ReuseSignal(family_id)

        # Famille inconnue ou deja revoquee : rien a apprendre a l appelant.
        # Un jeton de session close ne merite pas un motif distinct — le
        # distinguer dirait a un attaquant que sa cible s est deconnectee.
        raise TokenInvalidError()

    # -- revocation ---------------------------------------------------------

    @staticmethod
    def revoke_family(
        family_id: uuid.UUID,
        reason: str,
        *,
        now: datetime.datetime | None = None,
    ) -> int:
        """
        Revoque toute la lignee issue d une connexion. Renvoie le nombre de
        sessions touchees.

        Une seule requete `UPDATE ... WHERE family_id = %s AND revoked_at IS
        NULL` : la revocation d urgence ne doit pas dependre d une boucle Python
        qui pourrait s interrompre a mi-parcours.
        """
        return Session.objects.filter(family_id=family_id, revoked_at__isnull=True).update(
            revoked_at=now or timezone.now(), revoked_reason=reason
        )

    @staticmethod
    def revoke_session(session: Session, reason: str, *, now: datetime.datetime | None = None) -> int:
        """Revoque une session precise — deconnexion d un seul appareil."""
        return Session.objects.filter(pk=session.pk, revoked_at__isnull=True).update(
            revoked_at=now or timezone.now(), revoked_reason=reason
        )

    @staticmethod
    def revoke_all_for_user(user: User, reason: str, *, now: datetime.datetime | None = None) -> int:
        """
        Revoque toutes les sessions actives d un compte.

        Utilise au changement de mot de passe (`PASSWORD_CHANGE`) : un mot de
        passe change parce qu on le croit compromis ne sert a rien si les
        sessions ouvertes avec l ancien survivent.
        """
        return Session.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=now or timezone.now(), revoked_reason=reason
        )
