"""
Tests de concurrence — idempotence (§57 master prompt / §6.1 Source B) :
5 requêtes concurrentes même clé ⇒ 1 exécution + 4 réponses rejouées ; même
clé + corps différent ⇒ 422 ; enregistrement orphelin repris après le délai
de garde.

Nécessite PostgreSQL réel pour une vraie concurrence multi-connexion (§62
master prompt) — voir SPRINT_TEST_REPORT.md pour la commande d'exécution.
"""

import threading
from datetime import timedelta

import pytest
from django.db import connections
from django.utils import timezone

from apps.core import exceptions
from apps.core.idempotency import service
from apps.core.idempotency.models import IdempotencyRecord


@pytest.mark.django_db(transaction=True)
def test_five_concurrent_requests_same_key_yield_one_execution(user):
    """
    5 threads appellent begin() avec la MÊME clé. Un seul doit recevoir
    `replayed=False` (l'exécuteur réel) ; les 4 autres doivent soit rejouer
    la réponse mémorisée (si le premier a déjà complété), soit recevoir
    `RequestInProgressError` (s'il ne l'a pas encore complété) — jamais une
    deuxième exécution réelle.
    """
    key = "purchase-key-concurrent-1"
    results: list[tuple[str, bool | None]] = []
    lock = threading.Lock()

    def worker():
        connections.close_all()  # chaque thread a sa propre connexion DB
        try:
            outcome = service.begin(
                key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="h1"
            )
            with lock:
                results.append(("ok", outcome.replayed))
        except exceptions.RequestInProgressError:
            with lock:
                results.append(("in_progress", None))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    real_executions = [r for r in results if r == ("ok", False)]
    assert len(real_executions) == 1, f"attendu exactement 1 exécution réelle, obtenu: {results}"

    rejected_or_replayed = [r for r in results if r != ("ok", False)]
    assert len(rejected_or_replayed) == 4


@pytest.mark.django_db
def test_same_key_different_body_is_rejected(user):
    key = "purchase-key-2"
    outcome = service.begin(
        key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a"
    )
    service.complete(outcome.record, response_status=201, response_body={"order_id": "1"})

    with pytest.raises(exceptions.IdempotencyKeyReuseError) as exc_info:
        service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-b")

    assert exc_info.value.code == "IDEMPOTENCY_KEY_REUSE"


@pytest.mark.django_db
def test_same_key_same_body_replays_completed_response(user):
    key = "purchase-key-3"
    outcome = service.begin(
        key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a"
    )
    service.complete(outcome.record, response_status=201, response_body={"order_id": "42"})

    replayed = service.begin(
        key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a"
    )

    assert replayed.replayed is True
    assert replayed.record.response_body == {"order_id": "42"}


@pytest.mark.django_db
def test_in_progress_execution_rejects_immediate_retry(user):
    key = "purchase-key-4"
    service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a")

    with pytest.raises(exceptions.RequestInProgressError):
        service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a")


@pytest.mark.django_db
def test_orphaned_in_progress_record_is_recovered_after_guard_delay(user, settings):
    """
    Processus tué entre IN_PROGRESS et COMPLETED : après le délai de garde
    (`locked_at` + 60s), l'enregistrement doit être considéré orphelin et
    repris — sinon le client ne peut plus jamais acheter avec cette clé.
    """
    from unittest.mock import patch

    settings.IDEMPOTENCY_ORPHAN_GUARD_SECONDS = 60
    key = "purchase-key-5"

    record = IdempotencyRecord.objects.create(
        key=key,
        user_id=user.pk,
        endpoint="/api/v1/tickets/purchase",
        request_hash="hash-a",
        status=IdempotencyRecord.Status.IN_PROGRESS,
        expires_at=timezone.now() + timedelta(hours=24),
    )

    # Simule un enregistrement verrouillé il y a plus de 60 secondes.
    IdempotencyRecord.objects.filter(pk=record.pk).update(locked_at=timezone.now() - timedelta(seconds=61))

    # Vérifie que la récupération de l'orphelin génère bien un WARNING.
    with patch("apps.core.idempotency.service.logger.warning") as warning_mock:
        outcome = service.begin(
            key=key,
            user_id=user.pk,
            endpoint="/api/v1/tickets/purchase",
            request_hash="hash-a",
        )

    assert outcome.replayed is False
    assert outcome.record.status == IdempotencyRecord.Status.IN_PROGRESS

    warning_mock.assert_called_once()
    assert warning_mock.call_args.args[0] == "idempotency_orphan_recovered"


@pytest.mark.django_db
def test_key_is_scoped_per_user_not_global(user, other_user):
    """Deux utilisateurs différents peuvent utiliser la même clé sans interférence."""
    key = "shared-client-generated-key"
    outcome_a = service.begin(key=key, user_id=user.pk, endpoint="/api/v1/x", request_hash="h")
    outcome_b = service.begin(key=key, user_id=other_user.pk, endpoint="/api/v1/x", request_hash="h")

    assert outcome_a.replayed is False
    assert outcome_b.replayed is False
    assert outcome_a.record.pk != outcome_b.record.pk
