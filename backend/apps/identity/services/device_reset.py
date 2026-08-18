"""
`DeviceResetService` — delier un appareil quand on ne peut plus s authentifier.

## Pourquoi ce service existe hors de toute authentification

Le verrou d appareil refuse la connexion depuis un second telephone avec
`403 DEVICE_LOCKED`, et ce refus n emet aucun jeton. L utilisateur dont
l appareil est perdu, vole ou casse est donc, par construction, incapable
d appeler un point de terminaison authentifie — et c est precisement lui qui a
besoin de delier.

Les deux routes sont donc anonymes, chacune portant sa propre preuve :
identifiants pour la demande, code a usage unique pour la confirmation.
ADR-S1-04 documente la contradiction du plan que cette decision corrige.

## Les trois pieges de ce lot

1. **L oracle d existence.** La demande accepte une adresse et un mot de passe :
   c est un second `POST /auth/login` deguise. Meme corps, meme code, meme temps
   de reponse — hachage factice compris — que l adresse existe ou non. Le
   `challenge_id` est TOUJOURS renvoye, fabrique quand les identifiants sont
   faux, sans quoi sa presence serait elle-meme l oracle.

2. **L increment perdu.** Compter une tentative infructueuse PUIS lever
   l exception a l interieur de la transaction annule l increment : le compteur
   ne monte jamais, le plafond de cinq n est jamais atteint, et le code se
   force tranquillement. Meme piege qu au lot S1-A.5 avec la revocation de
   famille. Ici, la transaction ecrit et se ferme ; l exception est levee APRES.

3. **Le secret dans les journaux.** Le code n est stocke que hache
   (`ck_mfa_code_hash_is_a_digest` le verifie en base) et n apparait dans aucun
   journal applicatif. Seul `ConsoleSender`, reserve au developpement, le rend
   lisible — et il previent qu il le fait.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import logging
import secrets
import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.interfaces import NotificationSender
from apps.core.observability.metrics import fanid_device_reset_total
from apps.core.outbox.publisher import publish_event

from ..constants import (
    DEVICE_REVOKED_USER_RESET,
    MFA_PURPOSE_DEVICE_RESET,
    OTP_TTL_MINUTES,
    SESSION_REVOKED_DEVICE_RESET,
)
from ..events import (
    AGGREGATE_USER,
    DEVICE_RESET_CONFIRMED,
    DEVICE_RESET_REQUESTED,
    device_reset_confirmed_payload,
    device_reset_requested_payload,
)
from ..exceptions import OtpInvalidError, OtpMaxAttemptsError
from ..models import Device, MfaChallenge, User
from .authentication import _decoy_hash
from .devices import DeviceBindingService
from .tokens import TokenService

logger = logging.getLogger("fanid.identity")

#: Longueur du code envoye. Six chiffres, comme tout ce que les gens recopient
#: depuis un courriel. La solidite ne vient pas de la longueur mais du plafond
#: de cinq tentatives : 10^6 possibilites contre 5 essais par defi.
CODE_DIGITS = 6


def _hash_code(code: str) -> str:
    """SHA-256 hexadecimal minuscule — le format que la contrainte exige."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True, slots=True)
class ResetRequestResult:
    """
    Resultat d une demande.

    `challenge_id` est renvoye dans TOUS les cas. `created` dit la verite au
    service, jamais au client : il ne sert qu a decider s il faut envoyer un
    courriel et emettre un evenement.
    """

    challenge_id: uuid.UUID
    created: bool


@dataclasses.dataclass(frozen=True, slots=True)
class ResetConfirmResult:
    device_revoked: bool
    sessions_revoked: int


class DeviceResetService:
    """Emission et verification du code de reinitialisation d appareil."""

    def __init__(self, *, binding: DeviceBindingService, sender: NotificationSender) -> None:
        self._binding = binding
        self._sender = sender

    # -- demande -------------------------------------------------------------

    def request(self, *, email: str, password: str) -> ResetRequestResult:
        """
        Emet un code, ou fait semblant.

        Le chemin factice n ecrit rien, n envoie rien, n emet aucun evenement —
        et coute le meme temps, parce que le hachage factice a ete verifie.
        """
        user = self._verify(email, password)
        if user is None:
            # Identifiant tire au hasard, jamais persiste. `confirm` ne le
            # trouvera pas et repondra `OTP_INVALID`, ce que repondrait aussi un
            # mauvais code sur un vrai defi.
            return ResetRequestResult(challenge_id=uuid.uuid4(), created=False)

        code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
        now = timezone.now()

        with transaction.atomic():
            # Verrou sur la ligne du COMPTE : trois demandes simultanees se
            # serialisent ici. Sans lui, elles liraient toutes trois un etat ou
            # aucun defi n est encore cree, et en laisseraient trois ouverts —
            # donc trois codes valides pour un plafond de cinq tentatives
            # chacun. Le test de concurrence du plan (§6.3) fige ce point.
            User.objects.select_for_update().get(pk=user.pk)

            invalidated = (
                MfaChallenge.objects.for_purpose(user, MFA_PURPOSE_DEVICE_RESET)
                .filter(consumed_at__isnull=True)
                .update(consumed_at=now)
            )

            challenge = MfaChallenge.objects.create(
                user=user,
                purpose=MFA_PURPOSE_DEVICE_RESET,
                code_hash=_hash_code(code),
                expires_at=now + datetime.timedelta(minutes=int(OTP_TTL_MINUTES)),
            )
            active = Device.objects.active().for_user(user).first()
            publish_event(
                event_type=DEVICE_RESET_REQUESTED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=device_reset_requested_payload(device_bound=active is not None),
            )

        # Envoi APRES la transaction : un courriel parti sur une transaction
        # annulee annoncerait un code qui n existe pas. L echec d envoi est
        # journalise sans etre relaye au client — une erreur ici ne doit pas
        # distinguer, de l exterieur, un compte existant d un compte inconnu.
        self._send(user, code)

        logger.info(
            "device.reset.requested",
            extra={"user_id": str(user.pk), "invalidated": invalidated},
        )
        return ResetRequestResult(challenge_id=challenge.pk, created=True)

    def _verify(self, email: str, password: str) -> User | None:
        """
        Les memes trois refus qu a la connexion, et le meme cout.

        Le hachage factice est IMPORTE de `authentication` plutot que recalcule :
        deux secrets distincts coûteraient pareil, mais un seul garantit que les
        deux routes restent alignees si les parametres du hacheur changent.
        """
        user = User.objects.select_related("role").filter(email=email).first()
        if user is None:
            from django.contrib.auth.hashers import check_password

            check_password(password, _decoy_hash())
            logger.info("device.reset.refused", extra={"reason": "unknown_email"})
            return None
        if not user.check_password(password):
            logger.info("device.reset.refused", extra={"reason": "bad_password"})
            return None
        if not user.is_active or user.anonymized_at is not None:
            logger.warning("device.reset.refused", extra={"reason": "inactive_account"})
            return None
        return user

    def _send(self, user: User, code: str) -> None:
        try:
            self._sender.send_email(
                to=user.email,
                subject="FAN iD — code de reinitialisation d appareil",
                body=(
                    f"Votre code de reinitialisation est {code}. "
                    f"Il expire dans {OTP_TTL_MINUTES} minutes. "
                    "Si vous n etes pas a l origine de cette demande, ignorez ce message."
                ),
            )
        except Exception:  # noqa: BLE001 - la panne d envoi ne doit rien reveler
            logger.exception("device.reset.send_failed", extra={"user_id": str(user.pk)})

    # -- confirmation --------------------------------------------------------

    def confirm(self, *, challenge_id: uuid.UUID, code: str) -> ResetConfirmResult:
        """
        Verifie le code, delie l appareil, ferme les sessions.

        **La transaction ecrit, puis se ferme. L exception vient apres.** Lever
        depuis l interieur annulerait l increment de tentative qu on vient
        d ecrire : le compteur resterait a zero et le plafond de cinq ne serait
        jamais atteint. C est le meme defaut que la revocation de famille
        annulee au lot S1-A.5, et il est invisible en test si l on se contente
        de verifier que l erreur est bien levee.
        """
        outcome, result = self._settle(challenge_id, code)

        if outcome == "exhausted":
            fanid_device_reset_total.labels(result="exhausted").inc()
            raise OtpMaxAttemptsError()
        if outcome == "invalid":
            fanid_device_reset_total.labels(result="invalid").inc()
            raise OtpInvalidError()

        fanid_device_reset_total.labels(result="success").inc()
        assert result is not None
        return result

    def _settle(self, challenge_id: Any, code: str) -> tuple[str, ResetConfirmResult | None]:
        """Applique toutes les ecritures et renvoie le verdict, sans lever."""
        now = timezone.now()

        with transaction.atomic():
            challenge = (
                # `of=("self",)` : on verrouille la ligne du defi, et elle seule.
                # Sans cette precision, la jointure vers `role` — nullable cote
                # utilisateur — ferait refuser la requete par PostgreSQL, et la
                # version permissive aurait serialise toutes les confirmations
                # derriere les quatre lignes du referentiel des roles.
                MfaChallenge.objects.select_for_update(of=("self",))
                .select_related("user", "user__role")
                .filter(pk=challenge_id, purpose=MFA_PURPOSE_DEVICE_RESET)
                .first()
            )

            unusable = (
                challenge is None
                or challenge.consumed_at is not None
                or challenge.expires_at <= now
                or challenge.attempts >= challenge.max_attempts
            )
            if unusable or challenge is None:
                logger.info("device.reset.refused", extra={"reason": "challenge_unusable"})
                return "invalid", None

            if not secrets.compare_digest(challenge.code_hash, _hash_code(code)):
                challenge.attempts += 1
                exhausted = challenge.attempts >= challenge.max_attempts
                if exhausted:
                    challenge.consumed_at = now
                challenge.save(update_fields=["attempts", "consumed_at"])
                logger.warning(
                    "device.reset.refused",
                    extra={"reason": "bad_code", "attempts": challenge.attempts},
                )
                return ("exhausted" if exhausted else "invalid"), None

            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])

            user = challenge.user
            active = Device.objects.active().for_user(user).first()
            device_revoked = False
            if active is not None:
                device_revoked = bool(self._binding.revoke(active, DEVICE_REVOKED_USER_RESET, now=now))

            # Toutes les sessions tombent, pas seulement celles liees a
            # l appareil : l appareil est presume perdu, et une session ouverte
            # ailleurs avec le meme mot de passe n a aucune raison de survivre a
            # un parcours de recuperation.
            sessions_revoked = TokenService.revoke_all_for_user(user, SESSION_REVOKED_DEVICE_RESET, now=now)

            publish_event(
                event_type=DEVICE_RESET_CONFIRMED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=device_reset_confirmed_payload(
                    device_revoked=device_revoked, sessions_revoked=sessions_revoked
                ),
            )

        logger.info(
            "device.reset.confirmed",
            extra={"device_revoked": device_revoked, "sessions_revoked": sessions_revoked},
        )
        return "ok", ResetConfirmResult(device_revoked=device_revoked, sessions_revoked=sessions_revoked)
