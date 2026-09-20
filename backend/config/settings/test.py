"""
Test settings executed by pytest.

Intentional differences from development:
- passwords use MD5 for test speed only, never production;
- Celery eager mode stays disabled by default so Outbox/idempotency tests
  exercise explicit task paths rather than a synchronous shortcut that could
  hide serialization or trace-propagation bugs.
"""

from typing import Any, cast

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = ["*"]
SECRET_KEY = env("DJANGO_SECRET_KEY", default="test-secret-key-not-for-prod-use-only")
QR_SIGNING_KEY = env(  # pragma: allowlist secret
    "QR_SIGNING_KEY", default="test-qr-signing-key-not-for-prod-use-only"
)

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

OTEL_TRACES_SAMPLE_RATE = 1.0
# Real OTel bootstrap, which would export over the network, is disabled in tests.
# Trace-propagation tests install an in-memory TracerProvider explicitly instead.
OTEL_ENABLED = False

# Application request logging remains active because its behavior is tested, but
# the root level is raised to avoid noisy pytest output.
cast(dict[str, Any], LOGGING)["root"]["level"] = "WARNING"  # noqa: F405

# In-memory capture ensures a test that forgets to inject a sender records the
# code instead of logging it.
NOTIFICATION_BACKEND = "memory"
