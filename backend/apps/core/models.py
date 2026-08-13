"""
Modèles de base du socle (§16 master prompt / §2.2 Source B).

Règle absolue : `core` ne dépend d'aucun bounded context métier (ADR-S-01,
vérifié par import-linter). Ces classes abstraites sont importées PAR les
bounded contexts, jamais l'inverse.
"""

import uuid
from typing import Any

from django.db import models


class UUIDModel(models.Model):
    """
    PK UUID v4 plutôt qu'un entier séquentiel.

    Exigence de sécurité (§2.2 Source B) : le QR code expose l'UUID du billet.
    Un identifiant séquentiel permettrait l'énumération (IDOR trivial :
    /tickets/1, /tickets/2, ...). Toute ressource exposée à un client externe
    doit hériter de ce modèle.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Horodatage de création/mise à jour, posé une fois pour tous les modèles métier."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class VersionedModel(models.Model):
    """
    Support du verrouillage optimiste (ADR-S-05, stratégie de concurrence hybride).

    Utilisé par les ressources à contention faible éditées par des humains
    (event, category en édition, product, organizer.validation_status) — PAS
    par les ressources à contention élevée du chemin d'achat, qui utilisent
    `SELECT FOR UPDATE` (verrouillage pessimiste) implémenté au niveau des
    services métier des sprints correspondants, pas ici.

    L'incrément de version et la détection de conflit (`409 STALE_RESOURCE`)
    sont la responsabilité du service applicatif qui appelle `save()` avec la
    version attendue — ce modèle ne fait que porter le compteur. Le
    comportement complet est exercé et testé à partir du Sprint 2 (première
    ressource optimiste : `event`/`category` en édition).
    """

    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk and not kwargs.get("force_insert"):
            self.version = models.F("version") + 1
        super().save(*args, **kwargs)
        if self.pk:
            self.refresh_from_db(fields=["version"])


# Les tables d'infrastructure du Sprint 0 (§3.1 Source B) vivent dans des
# sous-modules dédiés pour la lisibilité (core/idempotency/, core/outbox/),
# mais sont rattachées à l'app Django `core` (une seule migration racine,
# core/migrations/0001_infrastructure.py) via `Meta.app_label = "core"`.
# L'import ici est ce qui les rend visibles à `makemigrations`.
from .idempotency.models import IdempotencyRecord  # noqa: E402,F401
from .outbox.models import ConsumedEvent, OutboxEvent  # noqa: E402,F401
