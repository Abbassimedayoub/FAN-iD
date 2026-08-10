"""
Service d'idempotence (ADR-S-06).

Le quadruplet **(user, key, endpoint, request_hash)** est validé
explicitement — pas seulement (user, key) — car une même valeur de clé
soumise par erreur (ou par un client bogué) sur DEUX endpoints différents ne
doit JAMAIS pouvoir rejouer la réponse de l'un sur l'autre : c'est une fuite
de réponse inter-endpoints, potentiellement inter-fonctionnalités (ex. la
réponse d'un `POST /tickets/purchase` rejouée sur un `POST
/tickets/transfer` qui partagerait accidentellement la même clé client).

Règles fines (§3.1 Source B / §20 master prompt) :
- clé déjà vue sur un endpoint DIFFÉRENT (même si le hash coïncide) ⇒
  `IdempotencyKeyReuseError` (422) — vérifié EN PREMIER, avant toute
  logique par statut : ce cas ne doit jamais atteindre un chemin de rejeu.
- clé déjà vue, COMPLETED, même endpoint, même empreinte de requête ⇒
  réponse mémorisée rejouée.
- clé déjà vue, même endpoint, empreinte DIFFÉRENTE ⇒ IdempotencyKeyReuseError (422).
- clé IN_PROGRESS, non orpheline (< délai de garde) ⇒ RequestInProgressError (409).
- clé IN_PROGRESS, orpheline (processus tué entre IN_PROGRESS et COMPLETED,
  `locked_at` + 60s dépassé) ⇒ reprise, avec log WARNING.
- L'INSERTION est le verrou : pas de SELECT puis INSERT (fenêtre de course).
"""
import hashlib
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import IdempotencyKeyReuseError, RequestInProgressError
from apps.core.observability.metrics import fanid_idempotency_conflicts_total

from .models import IdempotencyRecord

logger = logging.getLogger("fanid.idempotency")


def compute_request_hash(body: bytes) -> str:
    """Empreinte SHA-256 du corps canonique de la requête."""
    return hashlib.sha256(body or b"").hexdigest()


class IdempotencyOutcome:
    """Résultat de `begin()` : soit une réponse rejouée, soit un enregistrement à compléter."""

    def __init__(self, record: IdempotencyRecord, replayed: bool):
        self.record = record
        self.replayed = replayed


def _is_orphaned(record: IdempotencyRecord) -> bool:
    guard = timedelta(seconds=settings.IDEMPOTENCY_ORPHAN_GUARD_SECONDS)
    return timezone.now() - record.locked_at > guard


@transaction.atomic
def begin(*, key: str, user_id, endpoint: str, request_hash: str) -> IdempotencyOutcome:
    """
    Démarre (ou rejoue) une opération idempotente.

    L'insertion est tentée directement ; une IntegrityError signifie qu'un
    enregistrement existe déjà pour (key, user_id) — c'est le mécanisme de
    verrou, pas un SELECT préalable.
    """
    expires_at = timezone.now() + timedelta(hours=settings.IDEMPOTENCY_RETENTION_HOURS)
    try:
        record = IdempotencyRecord.objects.create(
            key=key,
            user_id=user_id,
            endpoint=endpoint,
            request_hash=request_hash,
            status=IdempotencyRecord.Status.IN_PROGRESS,
            expires_at=expires_at,
        )
        return IdempotencyOutcome(record=record, replayed=False)
    except IntegrityError:
        pass

    # Un enregistrement existe déjà : verrouillage pessimiste pour la décision.
    record = IdempotencyRecord.objects.select_for_update().get(key=key, user_id=user_id)

    # Validation du quadruplet (user, key, endpoint, request_hash) — PREMIÈRE
    # vérification, avant toute branche par statut. Un endpoint différent est
    # TOUJOURS un rejet, quel que soit le statut de l'enregistrement existant
    # (COMPLETED, IN_PROGRESS ou FAILED) : ré-utiliser une clé sur un autre
    # endpoint n'est jamais une "reprise" légitime, c'est soit un bug client,
    # soit une tentative de faire rejouer la réponse d'un autre endpoint.
    if record.endpoint != endpoint:
        fanid_idempotency_conflicts_total.labels(reason="endpoint_mismatch").inc()
        logger.warning(
            "idempotency_key_reused_across_endpoints",
            extra={
                "idempotency_key": key,
                "user_id": str(user_id),
                "original_endpoint": record.endpoint,
                "attempted_endpoint": endpoint,
            },
        )
        raise IdempotencyKeyReuseError(
            message="Cette clé d'idempotence a déjà été utilisée sur un autre endpoint.",
            details={"key": key, "expected_endpoint": record.endpoint, "received_endpoint": endpoint},
        )

    if record.status == IdempotencyRecord.Status.COMPLETED:
        if record.request_hash != request_hash:
            fanid_idempotency_conflicts_total.labels(reason="key_reuse").inc()
            raise IdempotencyKeyReuseError(
                details={"key": key, "endpoint": endpoint},
            )
        return IdempotencyOutcome(record=record, replayed=True)

    if record.status == IdempotencyRecord.Status.IN_PROGRESS:
        if _is_orphaned(record):
            logger.warning(
                "idempotency_orphan_recovered",
                extra={"idempotency_key": key, "user_id": str(user_id), "endpoint": endpoint},
            )
            record.locked_at = timezone.now()
            record.request_hash = request_hash
            record.save(update_fields=["locked_at", "request_hash"])
            return IdempotencyOutcome(record=record, replayed=False)

        fanid_idempotency_conflicts_total.labels(reason="in_progress").inc()
        raise RequestInProgressError(details={"key": key, "endpoint": endpoint})

    # FAILED : autoriser une nouvelle tentative propre (nouvel état IN_PROGRESS).
    record.status = IdempotencyRecord.Status.IN_PROGRESS
    record.locked_at = timezone.now()
    record.request_hash = request_hash
    record.save(update_fields=["status", "locked_at", "request_hash"])
    return IdempotencyOutcome(record=record, replayed=False)


def complete(
    record: IdempotencyRecord,
    *,
    response_status: int,
    response_body,
    response_headers: dict | None = None,
) -> None:
    """
    Mémorise le résultat pour un rejeu futur. `response_headers` ne contient
    QU'un sous-ensemble d'en-têtes "clés" (whitelist, voir
    `middleware.REPLAYABLE_RESPONSE_HEADERS`) — jamais l'intégralité des
    en-têtes de la réponse originale (certains, comme `Set-Cookie` ou
    `X-Correlation-ID`, ne doivent jamais être rejoués tels quels).
    """
    record.status = IdempotencyRecord.Status.COMPLETED
    record.response_status = response_status
    record.response_body = response_body
    record.response_headers = response_headers or {}
    record.save(update_fields=["status", "response_status", "response_body", "response_headers"])


def fail(record: IdempotencyRecord) -> None:
    record.status = IdempotencyRecord.Status.FAILED
    record.save(update_fields=["status"])


def purge_expired() -> int:
    """Purge des enregistrements expirés (§20 master prompt — tâche Beat quotidienne)."""
    deleted, _ = IdempotencyRecord.objects.filter(expires_at__lt=timezone.now()).delete()
    return deleted


def serialize_response_body(data) -> bytes:
    return json.dumps(data, default=str).encode()
