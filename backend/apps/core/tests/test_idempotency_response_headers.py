"""
Rejeu des en-têtes de réponse "clés" (P1.A.2 du plan de correction) —
whitelist REPLAYABLE_RESPONSE_HEADERS, jamais l'intégralité des en-têtes.
"""
import json

import pytest
from django.http import JsonResponse
from django.test import RequestFactory

from apps.core.idempotency.middleware import (
    IDEMPOTENCY_KEY_HEADER,
    REPLAYABLE_RESPONSE_HEADERS,
    REPLAYED_MARKER_HEADER,
    IdempotencyMiddleware,
)

factory = RequestFactory()


def _make_request(user, key, body=b"{}"):
    request = factory.post(
        "/api/v1/tickets/purchase",
        data=body,
        content_type="application/json",
        **{IDEMPOTENCY_KEY_HEADER: key},
    )
    request.user = user
    return request


@pytest.mark.django_db
def test_key_response_headers_are_captured_and_replayed(user):
    def get_response(request):
        response = JsonResponse({"order_id": "1"}, status=201)
        response["Content-Type"] = "application/json"
        response["Location"] = "/api/v1/orders/1"
        response["Set-Cookie"] = "sessionid=should-never-be-replayed"
        return response

    middleware = IdempotencyMiddleware(get_response)
    key = "purchase-with-headers"

    # 1ère exécution : réelle, capture les en-têtes whitelistés.
    first_response = middleware(_make_request(user, key))
    assert first_response.status_code == 201
    assert first_response["Location"] == "/api/v1/orders/1"

    # 2e exécution : rejeu, mêmes en-têtes whitelistés restitués.
    replay_response = middleware(_make_request(user, key))
    assert replay_response.status_code == 201
    assert replay_response["Location"] == "/api/v1/orders/1"
    assert replay_response["Content-Type"] == "application/json"
    assert replay_response[REPLAYED_MARKER_HEADER] == "true"
    # Le cookie de session ne doit JAMAIS être rejoué — pas dans la whitelist.
    assert "Set-Cookie" not in replay_response or replay_response.get("Set-Cookie") != "sessionid=should-never-be-replayed"


def test_replayable_headers_whitelist_excludes_session_and_correlation():
    assert "Set-Cookie" not in REPLAYABLE_RESPONSE_HEADERS
    assert "X-Correlation-ID" not in REPLAYABLE_RESPONSE_HEADERS
    assert set(REPLAYABLE_RESPONSE_HEADERS) == {"Content-Type", "Location", "Retry-After"}
