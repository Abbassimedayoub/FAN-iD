from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def production_environment() -> dict[str, str]:
    env = os.environ.copy()

    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.prod",
            "DJANGO_SECRET_KEY": "configured-test-value",
            "DATABASE_URL": ("postgresql://fanid:fanid@localhost:5432/fanid"),
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/3",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/4",
            "JWT_SIGNING_KEY": "configured-test-value",
            "QR_SIGNING_KEY": "configured-test-value",
            "DJANGO_ALLOWED_HOSTS": "api.example.test",
            "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
            "CORS_ALLOWED_ORIGINS": "https://app.example.test",
            "NOTIFICATION_BACKEND": "console",
            "PAYMENT_GATEWAY": "stripe",
            "STRIPE_SECRET_KEY": "configured-test-value",
            "STRIPE_WEBHOOK_SECRET": "configured-test-value",
            "OBJECT_STORAGE_BACKEND": "r2",
            "R2_ACCOUNT_ID": ("0123456789abcdef0123456789abcdef"),
            "R2_ACCESS_KEY_ID": "configured-test-value",
            "R2_SECRET_ACCESS_KEY": "configured-test-value",
            "R2_BUCKET": "fanid-private",
            "OTEL_ENVIRONMENT": "production",
            "APP_VERSION": "production-config-test",
            "COMMIT_SHA": "production-config-test",
        }
    )

    return env


def run_production(
    overrides: dict[str, str] | None = None,
    *,
    check_urls: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = production_environment()

    if overrides:
        env.update(overrides)

    script = "import django; django.setup()"

    if check_urls:
        script += """
from apps.catalog.urls import urlpatterns

names = {
    pattern.name
    for pattern in urlpatterns
    if pattern.name
}

if "local-storage-media" in names:
    raise RuntimeError(
        "Local storage route is exposed with R2 enabled."
    )
"""

    return subprocess.run(
        [
            sys.executable,
            "-c",
            script,
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("PAYMENT_GATEWAY", "fake"),
        ("OBJECT_STORAGE_BACKEND", "local"),
        ("OBJECT_STORAGE_BACKEND", "s3"),
    ],
)
def test_production_rejects_wrong_provider(
    variable,
    value,
):
    result = run_production({variable: value})

    assert result.returncode != 0


@pytest.mark.parametrize(
    "variable",
    [
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET",
    ],
)
def test_production_rejects_missing_provider_configuration(
    variable,
):
    result = run_production({variable: ""})

    assert result.returncode != 0


def test_valid_production_uses_stripe_r2_and_hides_local_route():
    result = run_production(
        check_urls=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("source_url", "database", "expected"),
    [
        (
            "redis://render-redis:6379",
            0,
            "redis://render-redis:6379/0",
        ),
        (
            "redis://render-redis:6379/9",
            2,
            "redis://render-redis:6379/2",
        ),
        (
            "rediss://user:password@render-redis:6379?ssl=true",
            1,
            "rediss://user:password@render-redis:6379/1?ssl=true",
        ),
    ],
)
def test_render_style_redis_url_without_database_path(
    monkeypatch,
    source_url,
    database,
    expected,
):
    from config.settings import base as base_settings

    monkeypatch.setattr(
        base_settings,
        "REDIS_URL",
        source_url,
    )

    assert base_settings._redis_url_with_db(database) == expected
