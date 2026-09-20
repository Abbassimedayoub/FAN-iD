"""
Validate idempotency scope across user, key, endpoint, and request hash; matching keys and hashes
must not replay across different endpoints.
"""

import pytest

from apps.core import exceptions
from apps.core.idempotency import service


@pytest.mark.django_db
def test_same_key_same_hash_different_endpoint_is_rejected_not_replayed(user):
    """
    Critical case: the request hash matches but the endpoint differs; this must be rejected rather
    than replayed across endpoints.
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
    """Cross-endpoint rejection also applies while the original request is still IN_PROGRESS."""
    key = "shared-key-in-progress"
    service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="h1")

    with pytest.raises(exceptions.IdempotencyKeyReuseError):
        service.begin(key=key, user_id=user.pk, endpoint="/api/v1/orders/cancel", request_hash="h1")


@pytest.mark.django_db
def test_same_key_same_endpoint_same_hash_still_replays_normally(user):
    """Regression guard: normal replay on the same endpoint still works."""
    key = "normal-replay-key"
    outcome = service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="h1")
    service.complete(outcome.record, response_status=201, response_body={"order_id": "42"})

    replayed = service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="h1")

    assert replayed.replayed is True
    assert replayed.record.response_body == {"order_id": "42"}
