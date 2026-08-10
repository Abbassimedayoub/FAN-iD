"""
Hiérarchie d'erreurs métier (§17 master prompt / §3.3 Source B).

Le contrat d'erreur est GELÉ au Sprint 0 : `code` est stable, jamais traduit,
jamais renommé sans décision explicite. Toute nouvelle erreur métier des
sprints suivants hérite d'une de ces classes plutôt que de lever une
exception Python générique.
"""


class BusinessError(Exception):
    """Classe de base. `code` est le contrat machine ; `message` est humain."""

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
    """409 — conflit d'état ou de version (verrouillage optimiste, ADR-S-05)."""

    status_code = 409
    default_code = "CONFLICT"
    default_message = "La ressource a changé d'état."


class StaleResourceError(ConflictError):
    """409 spécialisé — `If-Match` ne correspond plus à la version courante."""

    default_code = "STALE_RESOURCE"
    default_message = "La ressource a été modifiée entre-temps."


class PreconditionFailed(BusinessError):
    """412 — en-tête `If-Match` requis mais absent, ou mal formé."""

    status_code = 412
    default_code = "PRECONDITION_REQUIRED"
    default_message = "L'en-tête If-Match est requis pour cette opération."


class UnprocessableError(BusinessError):
    status_code = 422
    default_code = "UNPROCESSABLE"
    default_message = "La requête ne peut pas être traitée."


class IdempotencyKeyReuseError(UnprocessableError):
    """Même clé d'idempotence, corps de requête différent (ADR-S-06)."""

    default_code = "IDEMPOTENCY_KEY_REUSE"
    default_message = "Cette clé d'idempotence a déjà été utilisée avec une requête différente."


class RequestInProgressError(ConflictError):
    """Exécution en cours pour cette clé d'idempotence — le client doit retenter."""

    status_code = 409
    default_code = "REQUEST_IN_PROGRESS"
    default_message = "Une requête identique est déjà en cours de traitement."


class RateLimitError(BusinessError):
    status_code = 429
    default_code = "RATE_LIMIT_EXCEEDED"
    default_message = "Trop de requêtes. Merci de réessayer plus tard."
