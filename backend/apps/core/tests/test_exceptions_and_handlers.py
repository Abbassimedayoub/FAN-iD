"""custom_exception_handler : chaque classe d'erreur produit le bon corps et le bon statut (§55)."""
import pytest
from rest_framework.exceptions import NotAuthenticated
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.core.exceptions import (
    ConflictError,
    IdempotencyKeyReuseError,
    NotFoundBusinessError,
    PermissionBusinessError,
    RateLimitError,
    StaleResourceError,
    UnprocessableError,
    ValidationBusinessError,
)
from apps.core.handlers import custom_exception_handler

factory = APIRequestFactory()


class _DummyView(APIView):
    pass


def _context():
    return {"view": _DummyView(), "request": factory.get("/x")}


@pytest.mark.parametrize(
    "exc_class,expected_status,expected_code",
    [
        (ValidationBusinessError, 400, "VALIDATION_ERROR"),
        (PermissionBusinessError, 403, "PERMISSION_DENIED"),
        (NotFoundBusinessError, 404, "NOT_FOUND"),
        (ConflictError, 409, "CONFLICT"),
        (StaleResourceError, 409, "STALE_RESOURCE"),
        (UnprocessableError, 422, "UNPROCESSABLE"),
        (IdempotencyKeyReuseError, 422, "IDEMPOTENCY_KEY_REUSE"),
        (RateLimitError, 429, "RATE_LIMIT_EXCEEDED"),
    ],
)
def test_business_error_produces_frozen_error_contract(exc_class, expected_status, expected_code):
    response = custom_exception_handler(exc_class("message de test"), _context())

    assert response.status_code == expected_status
    body = response.data
    assert body["error"]["code"] == expected_code
    assert body["error"]["message"] == "message de test"
    assert "correlation_id" in body["error"]
    assert "trace_id" in body["error"]
    assert "details" in body["error"]


def test_business_error_details_are_preserved():
    exc = ValidationBusinessError("stock insuffisant", code="STOCK_UNAVAILABLE", details={"requested": 4, "available": 2})
    response = custom_exception_handler(exc, _context())

    assert response.data["error"]["code"] == "STOCK_UNAVAILABLE"
    assert response.data["error"]["details"] == {"requested": 4, "available": 2}


def test_drf_exception_is_mapped_to_frozen_contract():
    response = custom_exception_handler(NotAuthenticated(), _context())

    assert response.status_code == 401
    assert response.data["error"]["code"] == "NOT_AUTHENTICATED"


def test_unhandled_exception_returns_500_without_technical_detail():
    class WeirdInternalError(Exception):
        pass

    response = custom_exception_handler(WeirdInternalError("détail technique sensible"), _context())

    assert response.status_code == 500
    assert response.data["error"]["code"] == "INTERNAL_ERROR"
    # Le message technique de l'exception Python NE DOIT JAMAIS fuiter au client.
    assert "détail technique sensible" not in str(response.data)
