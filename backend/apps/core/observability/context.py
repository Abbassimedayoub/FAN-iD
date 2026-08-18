"""
Contexte de corrélation partagé par requête (thread/coroutine-local via contextvars).

Utilisé par : CorrelationMiddleware (écrit), JsonFormatter (lit pour chaque log
ligne), custom_exception_handler (lit pour le corps d'erreur), et la tâche
Celery publiée depuis la vue (lit pour transmettre le correlation_id en tant
qu'attribut d'événement Outbox — pas le traceparent, qui est un mécanisme OTel
séparé, cf. config/celery.py).
"""

from contextvars import ContextVar, Token

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

CORRELATION_ID_HEADER = "X-Correlation-ID"


def set_correlation_id(value: str | None) -> Token:
    return _correlation_id.set(value)


def reset_correlation_id(token: Token) -> None:
    _correlation_id.reset(token)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def get_trace_id() -> str | None:
    """
    ID de trace OpenTelemetry courant, au format hexadécimal W3C (32 caractères).

    Retourne None si aucun span n'est actif (ex. hors requête HTTP) plutôt que
    de lever — l'observabilité ne doit jamais faire échouer une requête.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is None or ctx.trace_id == 0:
            return None
        return format(ctx.trace_id, "032x")
    except Exception:  # pragma: no cover - défense en profondeur
        return None
