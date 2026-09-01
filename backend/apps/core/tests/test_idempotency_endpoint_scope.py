"""
Validation du quadruplet (user, key, endpoint, request_hash) — P1.A.1 du plan
de correction post-bilan Sprint 0. Une même clé + un même hash sur un
endpoint DIFFÉRENT ne doit jamais rejouer la réponse d'un autre endpoint.
"""

import pytest

from apps.core import exceptions
from apps.core.idempotency import service


@pytest.mark.django_db
def test_same_key_same_hash_different_endpoint_is_rejected_not_replayed(user):
    """
    Cas critique : le hash COÏNCIDE (ex. deux endpoints appelés avec un corps
    vide) mais l'endpoint diffère. Avant P1.A.1, ceci aurait rejoué la
    réponse du premier endpoint sur le second — fuite de réponse
    inter-endpoints. Doit désormais être rejeté, jamais rejoué.
    """
    key = "shared-key-across-endpoints"
    same_hash = "hash-identical-on-both-calls"

    outcome = service.begin(
        key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash=same_hash
    )
    service.complete(outcome.record, response_status=201, response_body={"order_id": "1"})

    with pytest.raises(exceptions.IdempotencyKeyReuseError) as exc_info:
        service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/transfer", request_hash=same_hash)

    assert exc_info.value.code == "IDEMPOTENCY_KEY_REUSE"
    assert exc_info.value.details["expected_endpoint"] == "/api/v1/tickets/purchase"
    assert exc_info.value.details["received_endpoint"] == "/api/v1/tickets/transfer"


@pytest.mark.django_db
def test_endpoint_mismatch_rejected_even_while_in_progress(user):
    """Le rejet inter-endpoints s'applique aussi pendant une exécution
    IN_PROGRESS, pas seulement sur un enregistrement COMPLETED.
    """
    key = "shared-key-in-progress"
    service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="h1")

    with pytest.raises(exceptions.IdempotencyKeyReuseError):
        service.begin(key=key, user_id=user.pk, endpoint="/api/v1/orders/cancel", request_hash="h1")


@pytest.mark.django_db
def test_same_key_same_endpoint_same_hash_still_replays_normally(user):
    """Non-régression : le chemin de rejeu normal (même endpoint) continue de fonctionner."""
    key = "normal-replay-key"
    outcome = service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="h1")
    service.complete(outcome.record, response_status=201, response_body={"order_id": "42"})

    replayed = service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="h1")

    assert replayed.replayed is True
    assert replayed.record.response_body == {"order_id": "42"}
