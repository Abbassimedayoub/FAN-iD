"""
Single exception handler that produces the stable API error contract for every
error, whether it comes from DRF or from a business-domain `BusinessError`.
"""

import logging
from typing import Any

from rest_framework.exceptions import APIException, ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .exceptions import BusinessError
from .observability.context import get_correlation_id, get_trace_id

logger = logging.getLogger("fanid.errors")

_DRF_STATUS_TO_CODE = {
    400: "VALIDATION_ERROR",
    401: "NOT_AUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    406: "NOT_ACCEPTABLE",
    409: "CONFLICT",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "UNPROCESSABLE",
    429: "RATE_LIMIT_EXCEEDED",
}


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "correlation_id": get_correlation_id(),
            "trace_id": get_trace_id(),
        }
    }


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """
    Single entry point called by DRF (`REST_FRAMEWORK.EXCEPTION_HANDLER`).

    A 5xx response must never expose technical details such as Python exception
    messages, tracebacks, or SQL queries. The correlation and trace identifiers
    are the only client-visible references used to find the server-side incident.
    """
    if isinstance(exc, BusinessError):
        logger.warning(
            "business_error",
            extra={"error_code": exc.code, "status_code": exc.status_code},
        )
        return Response(_error_body(exc.code, exc.message, exc.details), status=exc.status_code)

    response = drf_exception_handler(exc, context)

    if response is not None:
        code = _DRF_STATUS_TO_CODE.get(response.status_code, "ERROR")
        detail = getattr(exc, "detail", None)

        # DRF keeps an explicit permission code inside ErrorDetail.
        # Preserve only specialized codes; default DRF codes are normalized
        # through _DRF_STATUS_TO_CODE to keep the historical API contract.
        if isinstance(detail, ErrorDetail):
            detail_code = str(detail.code)
            default_code = getattr(exc, "default_code", None)
            if detail_code != default_code:
                code = detail_code

        message = str(detail) if detail is not None else str(exc)
        details = response.data if isinstance(response.data, dict) else {"detail": response.data}
        response.data = _error_body(code, message, details)
        return response

    # Error not handled by DRF or BusinessError: return a generic 500 response
    # without exposing implementation details.
    logger.exception("unhandled_exception")
    return Response(
        _error_body("INTERNAL_ERROR", "Une erreur interne est survenue."),
        status=500,
    )


class DRFBusinessException(APIException):
    """Bridge a BusinessError into code that expects a DRF APIException."""

    def __init__(self, business_error: BusinessError):
        self.status_code = business_error.status_code
        # APIException.detail is typed as ErrorDetail | list | dict. A raw str
        # works at runtime but violates DRF's declared type contract.
        # ErrorDetail is a str subclass, so behavior stays unchanged.
        self.detail = ErrorDetail(business_error.message)
        self.business_error = business_error
