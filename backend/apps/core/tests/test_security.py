"""
Security tests: production settings, security headers, and end-to-end secret
redaction through the logging pipeline.
"""

import importlib
import logging
import os
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.core.observability.logging import JsonFormatter


def _set_required_production_environment(monkeypatch):
    """Provide fake but structurally valid production configuration."""
    values = {
        "DJANGO_SECRET_KEY": "x" * 60,
        "DJANGO_ALLOWED_HOSTS": "example.com",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "CELERY_BROKER_URL": "redis://localhost:6379/3",
        "CELERY_RESULT_BACKEND": "redis://localhost:6379/4",
        "JWT_SIGNING_KEY": "test-jwt-signing-key",
        "QR_SIGNING_KEY": "test-qr-signing-key",
        "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
        "CORS_ALLOWED_ORIGINS": "https://app.example.test",
        "NOTIFICATION_BACKEND": "memory",
        "PAYMENT_GATEWAY": "stripe",
        "STRIPE_SECRET_KEY": "configured-test-value",
        "STRIPE_WEBHOOK_SECRET": "configured-test-value",
        "OBJECT_STORAGE_BACKEND": "r2",
        "R2_ACCOUNT_ID": "0123456789abcdef0123456789abcdef",
        "R2_ACCESS_KEY_ID": "configured-test-value",
        "R2_SECRET_ACCESS_KEY": "configured-test-value",
        "R2_BUCKET": "fanid-private",
        "OTEL_ENVIRONMENT": "production",
        "APP_VERSION": "security-test",
        "COMMIT_SHA": "security-test",
    }

    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_production_settings_module_defines_required_security_headers(monkeypatch):
    """
    Load `config.settings.prod` with a minimal fake environment and verify the
    values Django actually sees rather than inspecting source text.
    """
    _set_required_production_environment(monkeypatch)

    # Clear the module cache so production settings are really evaluated with the
    # environment prepared by this test, regardless of test ordering.
    sys.modules.pop("config.settings.prod", None)
    prod_settings = importlib.import_module("config.settings.prod")

    assert prod_settings.SECURE_HSTS_SECONDS == 31536000
    assert prod_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod_settings.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod_settings.X_FRAME_OPTIONS == "DENY"
    assert prod_settings.SECURE_REFERRER_POLICY == "strict-origin-when-cross-origin"
    assert prod_settings.SECURE_SSL_REDIRECT is True
    assert prod_settings.DEBUG is False
    assert prod_settings.SPECTACULAR_SETTINGS["SERVE_PUBLIC"] is False

    # Refresh tokens travel in a cookie in production, so secure/HttpOnly flags and
    # a populated HTTPS CSRF allowlist are required.
    assert prod_settings.REFRESH_COOKIE_SECURE is True
    assert prod_settings.REFRESH_COOKIE_HTTPONLY is True
    assert prod_settings.CSRF_TRUSTED_ORIGINS
    assert all(o.startswith("https://") for o in prod_settings.CSRF_TRUSTED_ORIGINS)


def test_production_refuses_to_start_without_a_csrf_allowlist(monkeypatch):
    """
    Critical production variables must not have functional defaults. Missing
    CSRF_TRUSTED_ORIGINS must therefore fail startup rather than fall back
    silently.
    """
    _set_required_production_environment(monkeypatch)
    monkeypatch.delenv(
        "CSRF_TRUSTED_ORIGINS",
        raising=False,
    )

    # Guardrail: if the environment still provided the variable, the test would
    # pass without proving anything.
    assert "CSRF_TRUSTED_ORIGINS" not in os.environ

    # Clear the cache for deterministic behavior regardless of test ordering.
    sys.modules.pop("config.settings.prod", None)
    with pytest.raises(ImproperlyConfigured):
        importlib.import_module("config.settings.prod")


def test_dev_env_example_never_contains_a_real_looking_secret():
    """`.env.example` must not contain values that resemble real production secrets."""
    from pathlib import Path

    candidates = [
        Path("/config/.env.example"),
        *(parent / ".env.example" for parent in Path(__file__).resolve().parents),
    ]

    env_example = next(
        (path for path in candidates if path.exists()),
        None,
    )

    assert env_example is not None, ".env.example introuvable depuis le contexte de test"

    content = env_example.read_text()

    forbidden_patterns = [
        "sk_live_",
        "AKIA",
        "-----BEGIN",
    ]

    for pattern in forbidden_patterns:
        assert pattern not in content, f"motif de secret réel potentiel trouvé : {pattern}"


def test_no_secret_pattern_leaks_through_the_logging_pipeline_end_to_end(caplog):
    """
    Exercise the complete JsonFormatter pipeline with a deliberate secret and
    verify that the raw value never appears in formatted output.
    """
    formatter = JsonFormatter()
    secret_value = "sk_test_do_not_leak_me_0000000000"
    record = logging.LogRecord(
        name="fanid.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="payment_intent_created",
        args=(),
        exc_info=None,
    )
    record.stripe_secret_key = secret_value
    record.nested = {"authorization": f"Bearer {secret_value}"}

    formatted_line = formatter.format(record)

    assert secret_value not in formatted_line
