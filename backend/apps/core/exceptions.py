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
    """
    428 — en-tête `If-Match` requis mais absent sur une ressource versionnée.

    **428 Precondition Required**, pas 412 : le 412 signifie « la précondition
    fournie a échoué », alors qu'ici le client n'en a fourni AUCUNE. RFC 6585 §3
    a créé le 428 exactement pour ce cas, afin d'empêcher la mise à jour perdue
    (« lost update ») lorsqu'un client oublie `If-Match`. Corrigé au Sprint 1 :
    le contrat gelé du Sprint 0 portait 412, le plan S1 §3.4 exige 428, et aucun
    appelant n'existait encore.
    """

    status_code = 428
    default_code = "PRECONDITION_REQUIRED"
    default_message = "L'en-tête If-Match est requis pour cette opération."


class InvalidStateTransitionError(ConflictError):
    """
    409 — transition de machine à états interdite.

    Générique par nature : `organizing` s'en sert pour le cycle de validation
    d'un organisateur (S1), `ticketing` s'en servira pour le cycle de vie d'un
    billet (S3). Défini ici plutôt que dans un contexte pour éviter qu'un
    contexte n'importe les exceptions d'un autre (ADR-S-01).
    """

    default_code = "INVALID_STATE_TRANSITION"
    default_message = "Cette transition d'état n'est pas autorisée."


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
