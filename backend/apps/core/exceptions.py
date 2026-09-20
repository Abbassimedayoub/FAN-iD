"""
Business error hierarchy.

The error contract is stable: `code` is machine-readable, never translated,
and never renamed without an explicit contract change. New business errors
should inherit from one of these classes instead of raising a generic Python
exception.
"""


class BusinessError(Exception):
    """Base class. `code` is the machine contract; `message` is human-readable."""

    status_code = 500
    default_code = "INTERNAL_ERROR"
    default_message = "Une erreur interne est survenue."

    def __init__(self, message: str | None = None, code: str | None = None, details: dict | None = None):
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)


class ValidationBusinessError(BusinessError):
    status_code = 400
    default_code = "VALIDATION_ERROR"
    default_message = "La requête ne respecte pas une règle métier."


class AuthError(BusinessError):
    status_code = 401
    default_code = "NOT_AUTHENTICATED"
    default_message = "Authentification requise."


class PermissionBusinessError(BusinessError):
    status_code = 403
    default_code = "PERMISSION_DENIED"
    default_message = "Accès interdit à cette ressource."


class NotFoundBusinessError(BusinessError):
    status_code = 404
    default_code = "NOT_FOUND"
    default_message = "Ressource introuvable."


class ConflictError(BusinessError):
    """409 — state or version conflict, including optimistic locking."""

    status_code = 409
    default_code = "CONFLICT"
    default_message = "La ressource a changé d'état."


class StaleResourceError(ConflictError):
    """Specialized 409 — `If-Match` no longer matches the current version."""

    default_code = "STALE_RESOURCE"
    default_message = "La ressource a été modifiée entre-temps."


class PreconditionFailed(BusinessError):
    """
    428 — required `If-Match` header is missing on a versioned resource.

    This is **428 Precondition Required**, not 412: 412 means that a provided
    precondition failed, while here the client provided none. RFC 6585 section
    3 defines 428 for exactly this case, preventing lost updates when a client
    omits `If-Match`.
    """

    status_code = 428
    default_code = "PRECONDITION_REQUIRED"
    default_message = "L'en-tête If-Match est requis pour cette opération."


class InvalidStateTransitionError(ConflictError):
    """
    409 — forbidden state-machine transition.

    This error is intentionally generic: different bounded contexts can use it
    for their own lifecycle transitions. It lives in core so one context never
    needs to import another context's exceptions.
    """

    default_code = "INVALID_STATE_TRANSITION"
    default_message = "Cette transition d'état n'est pas autorisée."


class UnprocessableError(BusinessError):
    status_code = 422
    default_code = "UNPROCESSABLE"
    default_message = "La requête ne peut pas être traitée."


class IdempotencyKeyReuseError(UnprocessableError):
    """Same idempotency key used with a different request body."""

    default_code = "IDEMPOTENCY_KEY_REUSE"
    default_message = "Cette clé d'idempotence a déjà été utilisée avec une requête différente."


class RequestInProgressError(ConflictError):
    """An operation is already running for this idempotency key; the client should retry."""

    status_code = 409
    default_code = "REQUEST_IN_PROGRESS"
    default_message = "Une requête identique est déjà en cours de traitement."


class RateLimitError(BusinessError):
    status_code = 429
    default_code = "RATE_LIMIT_EXCEEDED"
    default_message = "Trop de requêtes. Merci de réessayer plus tard."
