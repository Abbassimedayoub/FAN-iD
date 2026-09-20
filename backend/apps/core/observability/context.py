"""
Per-request correlation context backed by contextvars for thread/coroutine locality.

Correlation middleware writes it, logging and error handling read it, and
asynchronous publication may copy the correlation ID into Outbox metadata.
OpenTelemetry trace propagation remains a separate mechanism.
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
    """Return the current W3C-format OpenTelemetry trace ID, or None when no span is active."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is None or ctx.trace_id == 0:
            return None
        return format(ctx.trace_id, "032x")
    except Exception:  # pragma: no cover - défense en profondeur
        return None
