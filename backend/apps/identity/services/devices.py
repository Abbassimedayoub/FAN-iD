"""
`DeviceBindingService` — un seul appareil actif par compte (RM-5).

## Ce que le serveur sait, et ce qu il ne sait pas

L empreinte est calculee COTE CLIENT — identifiant materiel, identifiant de
bundle, sel persistant, le tout passe au SHA-256. Le serveur ne la recalcule
jamais, n en deduit rien, et n utilise NI l adresse IP, NI le `User-Agent`, NI
aucune empreinte comportementale comme substitut. Ces signaux sont instables
— un changement d operateur mobile suffit — et leur collecte serait
disproportionnee au regard de la minimisation RGPD.

Il valide donc uniquement le FORMAT. C est peu, et c est assume : le verrou
d appareil protege contre le partage de compte et le vol de jeton, pas contre un
client malveillant qui fabriquerait une empreinte. Ce dernier cas releve de
l attestation d application, hors perimetre.

## Deux roles sont exemptes

`ORGANIZER` et `ADMIN` (ADR-03). Un organisateur travaille depuis un poste fixe,
un telephone et parfois la machine d un collaborateur ; lui imposer un appareil
unique transformerait chaque changement de poste en parcours de
reinitialisation par code. Le compromis est explicite : ces roles perdent le
verrou d appareil et gardent la rotation de jetons, la detection de
reutilisation et la revocation de famille.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.interfaces import DeviceLockBackend

from ..constants import DEVICE_PLATFORMS, FINGERPRINT_PATTERN, ROLE_ADMIN, ROLE_ORGANIZER
from ..exceptions import DeviceLockedError, DeviceMismatchError, InvalidFingerprintError
from ..models import Device, User

#: Roles dispenses du verrou d appareil (ADR-03).
DEVICE_EXEMPT_ROLES: tuple[str, ...] = (ROLE_ORGANIZER, ROLE_ADMIN)

#: Duree de vie du verrou en cache. Depassee, la decision est simplement relue
#: en base : un verrou expire n ouvre aucun droit, il coute une requete.
LOCK_TTL_SECONDS = 3600

#: `last_seen_at` n est rafraichi qu au-dela de ce delai.
#:
#: Sans cette paresse, CHAQUE requete de l API produirait une ecriture sur
#: `identity_device`. Au pic de connexions — l ouverture des portes — c est la
#: base qui sature, pour une donnee dont personne ne lit la minute exacte.
LAST_SEEN_REFRESH = datetime.timedelta(hours=1)

_FINGERPRINT = re.compile(FINGERPRINT_PATTERN)


def _partial_label(device: Device) -> str:
    """
    Libelle tronque, destine au corps d une erreur `DEVICE_LOCKED`.

    Le plan limite volontairement ce detail (§3.4). Il faut en dire assez pour
    qu un utilisateur reconnaisse son ancien telephone — sinon le message est
    inutilisable — et assez peu pour qu il ne renseigne pas quelqu un qui
    viendrait de prouver le mot de passe d autrui.
    """
    label = device.label or device.platform
    return label if len(label) <= 12 else f"{label[:12]}…"


class DeviceBindingService:
    """Lie un appareil a un compte, et refuse les autres."""

    def __init__(self, lock: DeviceLockBackend) -> None:
        # Le verrou est INJECTE, jamais construit ici : c est ce qui permet aux
        # tests de simuler une panne Redis sans arreter de conteneur, donc de
        # tester le repli de facon deterministe.
        self._lock = lock

    # -- validation ---------------------------------------------------------

    @staticmethod
    def validate_fingerprint(fingerprint: str) -> str:
        """
        64 caracteres hexadecimaux MINUSCULES.

        Accepter les majuscules creerait deux representations de la meme
        empreinte, donc deux appareils distincts pour un seul telephone — et un
        verrou declenche a chaque bascule. On refuse plutot que de normaliser :
        normaliser masquerait un client qui envoie n importe quoi.
        """
        if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
            raise InvalidFingerprintError()
        return fingerprint

    @staticmethod
    def is_exempt(user: User) -> bool:
        return user.role.name in DEVICE_EXEMPT_ROLES

    # -- liaison ------------------------------------------------------------

    def bind(
        self,
        *,
        user: User,
        fingerprint: str,
        platform: str,
        label: str = "",
        now: datetime.datetime | None = None,
    ) -> Device | None:
        """
        Renvoie l appareil lie, ou `None` pour un role exempte.

        Leve `DeviceLockedError` si un AUTRE appareil est deja actif.
        """
        if self.is_exempt(user):
            return None

        self.validate_fingerprint(fingerprint)
        if platform not in DEVICE_PLATFORMS:
            raise InvalidFingerprintError(details={"platform": list(DEVICE_PLATFORMS)})

        moment = now or timezone.now()
        active = Device.objects.active().for_user(user).first()

        if active is not None:
            if active.fingerprint != fingerprint:
                raise DeviceLockedError(
                    details={
                        "active_device_label": _partial_label(active),
                        "bound_at": active.bound_at.isoformat(),
                        # Le parcours de reinitialisation par code arrive au lot
                        # S1-A.7. Annoncer `false` aujourd hui serait un mensonge
                        # utile a personne ; le client doit savoir qu une issue
                        # existe, meme si elle n est pas encore branchee.
                        "reset_available": True,
                    }
                )
            self._touch(active, moment)
            self._lock.acquire(str(user.pk), str(active.pk), LOCK_TTL_SECONDS)
            return active

        return self._create(user=user, fingerprint=fingerprint, platform=platform, label=label)

    def _create(self, *, user: User, fingerprint: str, platform: str, label: str) -> Device:
        """
        Cree l appareil, en laissant la BASE arbitrer les créations concurrentes.

        Deux connexions simultanees depuis deux telephones passeraient toutes
        deux le `first()` ci-dessus : entre la lecture et l ecriture, rien ne les
        separe. Seule l unicite partielle `UNIQUE(user_id) WHERE revoked_at IS
        NULL` tranche — et c est elle qu on ecoute, plutot que de courir apres la
        course avec un verrou applicatif qui aurait sa propre fenetre.
        """
        try:
            with transaction.atomic():
                device = Device.objects.create(
                    user=user,
                    fingerprint=fingerprint,
                    platform=platform,
                    label=label[:60],
                )
        except IntegrityError as exc:
            # Le perdant de la course : un autre appareil a ete lie entre-temps.
            # La reponse est la meme que s il etait arrive une seconde plus tard.
            active = Device.objects.active().for_user(user).first()
            details: dict[str, Any] = {"reset_available": True}
            if active is not None:
                details["active_device_label"] = _partial_label(active)
                details["bound_at"] = active.bound_at.isoformat()
            raise DeviceLockedError(details=details) from exc

        self._lock.acquire(str(user.pk), str(device.pk), LOCK_TTL_SECONDS)
        return device

    def _touch(self, device: Device, now: datetime.datetime) -> None:
        """Rafraichit `last_seen_at`, au plus une fois par heure."""
        if now - device.last_seen_at < LAST_SEEN_REFRESH:
            return
        Device.objects.filter(pk=device.pk).update(last_seen_at=now)
        device.last_seen_at = now

    # -- verification a chaque requete --------------------------------------

    def assert_matches(self, *, user: User, device_id: Any) -> Device | None:
        """
        Verifie que le `did` porte par le jeton designe bien l appareil actif.

        Appelee sur le chemin le plus chaud de l API. Le verrou en cache repond
        sans toucher la base dans le cas nominal ; en cas de panne Redis, le
        repli lit la verite, plus lentement.

        Leve `DeviceMismatchError` (401) — pas 403. Un jeton presente depuis un
        autre appareil est un jeton probablement vole : la bonne reponse est
        « cette identite n est pas prouvee », pas « vous n avez pas le droit ».
        """
        if self.is_exempt(user):
            return None

        expected = self._lock.get_active(str(user.pk))
        if expected is None:
            # Cache froid ou verrou expire : on relit la verite. Un cache vide
            # n autorise RIEN par lui-meme.
            device = Device.objects.active().for_user(user).first()
            if device is None:
                raise DeviceMismatchError()
            expected = str(device.pk)
            self._lock.acquire(str(user.pk), expected, LOCK_TTL_SECONDS)

        if device_id is None or str(device_id) != expected:
            raise DeviceMismatchError()

        return Device.objects.active().for_user(user).filter(pk=expected).first()

    # -- revocation ---------------------------------------------------------

    def revoke(self, device: Device, reason: str, *, now: datetime.datetime | None = None) -> int:
        """
        Revoque l appareil et libere le verrou.

        L ordre compte : la base d abord, le cache ensuite. Vider le cache avant
        d ecrire ouvrirait une fenetre pendant laquelle un autre appareil
        pourrait se lier alors que l ancien est encore actif en base — et se
        heurter a la contrainte d unicite, donc a une erreur serveur au lieu
        d un refus propre.
        """
        updated = Device.objects.filter(pk=device.pk, revoked_at__isnull=True).update(
            revoked_at=now or timezone.now(), revoked_reason=reason
        )
        if updated:
            self._lock.release(str(device.user_id))
        return updated
