"""CorrelationMiddleware : génère si absent, propage si présent, jamais deux IDs (§55)."""

from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.observability.context import get_correlation_id

# `correlation_id` est posé dynamiquement sur la requête par
# CorrelationMiddleware : `WSGIRequest` ne le déclare pas. C'est précisément
# le comportement testé ici. Un protocole de requête typé sera introduit au
# Sprint 1 si le motif se généralise (DeviceBindingMiddleware, AuthAudit).
from apps.core.observability.middleware import CORRELATION_ID_HEADER, CorrelationMiddleware

factory = RequestFactory()


def _middleware(captured: dict):
    def get_response(request):
        captured["seen_in_view"] = get_correlation_id()
        return HttpResponse("ok")

    return CorrelationMiddleware(get_response)


def test_generates_correlation_id_when_absent():
    captured: dict[str, object] = {}
    middleware = _middleware(captured)
    request = factory.get("/x")

    response = middleware(request)

    assert response[CORRELATION_ID_HEADER]
    assert request.correlation_id == response[CORRELATION_ID_HEADER]  # type: ignore[attr-defined]
    assert captured["seen_in_view"] == response[CORRELATION_ID_HEADER]


def test_propagates_incoming_correlation_id():
    captured: dict[str, object] = {}
    middleware = _middleware(captured)
    request = factory.get("/x", HTTP_X_CORRELATION_ID="incoming-id-123")

    response = middleware(request)

    assert response[CORRELATION_ID_HEADER] == "incoming-id-123"
    assert captured["seen_in_view"] == "incoming-id-123"


def test_never_produces_two_different_ids_for_same_request():
    captured: dict[str, object] = {}
    middleware = _middleware(captured)
    request = factory.get("/x")

    response = middleware(request)

    # L'ID vu dans la vue doit être EXACTEMENT celui renvoyé au client — pas
    # un second ID généré indépendamment.
    assert captured["seen_in_view"] == response[CORRELATION_ID_HEADER]
    # `RequestFactory` produit une `WSGIRequest` brute ; l'attribut est posé
    # par le middleware sous test lui-même — c'est précisément l'assertion.
    assert request.correlation_id == response[CORRELATION_ID_HEADER]  # type: ignore[attr-defined]
