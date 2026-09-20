"""CorrelationMiddleware generates, propagates, and preserves one ID per request."""

from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.observability.context import get_correlation_id

# `correlation_id` is attached dynamically by CorrelationMiddleware;
# `WSGIRequest` does not declare it statically. That behavior is what these
# tests verify.
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

    # The ID observed in the view must be exactly the one returned to the client,
    # not another independently generated value.
    assert captured["seen_in_view"] == response[CORRELATION_ID_HEADER]
    # RequestFactory produces a raw WSGIRequest; the middleware under test adds
    # the attribute dynamically.
    assert request.correlation_id == response[CORRELATION_ID_HEADER]  # type: ignore[attr-defined]
