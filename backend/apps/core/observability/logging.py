"""
Logs JSON structurés + rédaction automatique des secrets (§28 master prompt,
§5.3 Source B).

`SecretRedactor` masque récursivement toute valeur dont la CLÉ correspond à un
motif sensible — y compris dans des structures imbriquées (dict dans dict,
dict dans liste) — pour ne jamais logguer un token, un mot de passe, une
graine cryptographique ou une donnée de paiement, même par accident via un
`extra={"payload": stripe_response}`.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from .context import get_correlation_id, get_trace_id

_SENSITIVE_KEY_PATTERN = re.compile(r"(password|token|secret|seed|key|authorization|card)", re.IGNORECASE)
_REDACTED = "***REDACTED***"

_RESERVED_LOGRECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
}


class SecretRedactor:
    """Masque récursivement les valeurs dont la clé matche le motif sensible."""

    @classmethod
    def redact(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: (_REDACTED if _SENSITIVE_KEY_PATTERN.search(str(k)) else cls.redact(v))
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls.redact(v) for v in value]
        return value


class CorrelationLogFilter(logging.Filter):
    """Injecte correlation_id/trace_id/service/env dans chaque LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        record.trace_id = getattr(record, "trace_id", None) or get_trace_id()
        return True


class JsonFormatter(logging.Formatter):
    """Une ligne JSON par entrée, champs obligatoires §28 master prompt."""

    def format(self, record: logging.LogRecord) -> str:
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _RESERVED_LOGRECORD_ATTRS and not k.startswith("_")
        }
        extra_fields = SecretRedactor.redact(extra_fields)

        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
            "user_id": getattr(record, "user_id", None),
            "service": os.environ.get("OTEL_SERVICE_NAME", "fanid-api"),
            "env": os.environ.get("OTEL_ENVIRONMENT", "dev"),
            "version": os.environ.get("APP_VERSION", "0.0.0-dev"),
            **extra_fields,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)
