"""
Gestionnaire d'exception unique — produit le contrat d'erreur gelé (§17 master
prompt / §3.3 Source B) pour TOUTE erreur, qu'elle vienne de DRF ou d'une
`BusinessError` métier.
"""
import logging

from rest_framework.exceptions import APIException
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


def custom_exception_handler(exc, context):
    """
    Point d'entrée unique appelé par DRF (`REST_FRAMEWORK.EXCEPTION_HANDLER`).

    Toute erreur 5xx ne doit JAMAIS exposer de détail technique (message
    d'exception Python, traceback, requête SQL) au client — seule la
    `correlation_id`/`trace_id` permet de retrouver l'incident côté serveur.
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
        message = str(exc.detail) if hasattr(exc, "detail") else str(exc)
        details = response.data if isinstance(response.data, dict) else {"detail": response.data}
        response.data = _error_body(code, message, details)
        return response

    # Erreur non gérée par DRF ni BusinessError : 500 générique, aucun détail exposé.
    logger.exception("unhandled_exception")
    return Response(
        _error_body("INTERNAL_ERROR", "Une erreur interne est survenue."),
        status=500,
    )


class DRFBusinessException(APIException):
    """Pont pour lever une BusinessError depuis du code qui attend une APIException DRF."""

    def __init__(self, business_error: BusinessError):
        self.status_code = business_error.status_code
        self.detail = business_error.message
        self.business_error = business_error
