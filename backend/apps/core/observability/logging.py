"""
Structured JSON logging with automatic secret redaction.

`SecretRedactor` recursively masks any value whose key matches a sensitive
pattern, including nested dictionaries and lists, so tokens, passwords,
cryptographic seeds, and payment data are never logged accidentally.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from .context import get_correlation_id, get_trace_id

# Broad patterns use partial matching. Anchored patterns are used for short,
# ambiguous Sprint 1 keys such as `code`, `did`, and `jti`. Partial matching
# for those names would also hide useful fields such as `error_code`,
# `status_code`, or `candidate`. The `^otp` and `^refresh` prefixes cover
# derivatives such as `otp_code` and `refresh_jti` without matching `totp`.
_SENSITIVE_KEY_PATTERN = re.compile(
    r"password|token|secret|seed|key|authorization|card|fingerprint"
    r"|cookie|set-cookie|sessionid|csrftoken"
    r"|^otp|^refresh|^jti$|^did$|^access$|^code$",
    re.IGNORECASE,
)
_REDACTED = "***REDACTED***"

_SENSITIVE_TEXT_PATTERNS = (
    (
        re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE),
        f"Bearer {_REDACTED}",
    ),
    (
        re.compile(
            r"\b(fanid_refresh|sessionid|csrftoken)=([^;\s]+)",
            re.IGNORECASE,
        ),
        rf"\1={_REDACTED}",
    ),
    (
        re.compile(
            r"\b(password|token|secret|authorization|otp|cookie)" r"\s*[:=]\s*[^\s,;]+",
            re.IGNORECASE,
        ),
        rf"\1={_REDACTED}",
    ),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\." r"[A-Za-z0-9_-]{8,}\." r"[A-Za-z0-9_-]{8,}\b"),
        _REDACTED,
    ),
)

_RESERVED_LOGRECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
}


class SecretRedactor:
    """Recursively mask values whose keys match the sensitive-key pattern."""

    @classmethod
    def redact(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: (_REDACTED if _SENSITIVE_KEY_PATTERN.search(str(k)) else cls.redact(v))
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls.redact(v) for v in value]
        if isinstance(value, str):
            return cls.redact_text(value)
        return value

    @staticmethod
    def redact_text(value: str) -> str:
        """Redact credential-shaped values embedded inside free-form text."""
        redacted = value
        for pattern, replacement in _SENSITIVE_TEXT_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted


class CorrelationLogFilter(logging.Filter):
    """Inject correlation_id, trace_id, service, and environment into each record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        record.trace_id = getattr(record, "trace_id", None) or get_trace_id()
        return True


class JsonFormatter(logging.Formatter):
    """Serialize one structured JSON object per log record."""

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
            "message": SecretRedactor.redact_text(record.getMessage()),
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
            payload["exception"] = SecretRedactor.redact_text(self.formatException(record.exc_info))

        return json.dumps(payload, default=str, ensure_ascii=False)
