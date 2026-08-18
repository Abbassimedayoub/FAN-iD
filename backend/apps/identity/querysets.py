"""
QuerySets du contexte `identity` (plan S1 §2.5).

Ils existent pour qu'aucun service n'ait à réécrire « ce qu'est un appareil
actif » ou « ce qu'est une session valide ». Une définition dupliquée finit
toujours par diverger : un filtre oublie `expires_at`, un autre oublie
`revoked_at`, et une session révoquée redevient utilisable quelque part.
"""

from datetime import datetime
from typing import Any

from django.db import models
from django.utils import timezone


class DeviceQuerySet(models.QuerySet):
    def active(self) -> "DeviceQuerySet":
        """Appareils non révoqués. Il ne peut y en avoir qu'un par compte —
        garanti en base par une unicité partielle, pas seulement ici."""
        return self.filter(revoked_at__isnull=True)

    def revoked(self) -> "DeviceQuerySet":
        return self.filter(revoked_at__isnull=False)

    def for_user(self, user: Any) -> "DeviceQuerySet":
        return self.filter(user=user)

    def stale(self, before: datetime) -> "DeviceQuerySet":
        """Appareils révoqués avant `before` — cible de la purge du Sprint 5."""
        return self.revoked().filter(revoked_at__lt=before)


class SessionQuerySet(models.QuerySet):
    def active(self) -> "SessionQuerySet":
        """
        Session utilisable : ni révoquée, ni expirée.

        Les DEUX conditions comptent. Ne filtrer que sur `revoked_at` laisserait
        passer une session dont le refresh a dépassé sa durée de vie ; ne filtrer
        que sur `expires_at` laisserait passer une session révoquée pour cause de
        réutilisation de jeton — c'est-à-dire précisément le scénario de vol que
        la révocation de famille est censée fermer.
        """
        return self.filter(revoked_at__isnull=True, expires_at__gt=timezone.now())

    def expired(self) -> "SessionQuerySet":
        return self.filter(expires_at__lte=timezone.now())

    def for_user(self, user: Any) -> "SessionQuerySet":
        return self.filter(user=user)

    def for_family(self, family_id: Any) -> "SessionQuerySet":
        """Toute la lignée issue d'une même connexion — unité de révocation
        lorsqu'une réutilisation de refresh est détectée (master prompt §17)."""
        return self.filter(family_id=family_id)


class MfaChallengeQuerySet(models.QuerySet):
    def open(self) -> "MfaChallengeQuerySet":
        """Défis encore utilisables : non consommés, non expirés, sous le
        plafond de tentatives."""
        return self.filter(
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
            attempts__lt=models.F("max_attempts"),
        )

    def for_purpose(self, user: Any, purpose: str) -> "MfaChallengeQuerySet":
        return self.filter(user=user, purpose=purpose)
