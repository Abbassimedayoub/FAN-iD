"""Settings de développement local (docker-compose)."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

# En dev, le schema/swagger sont accessibles sans authentification (§37 master prompt).
SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "SERVE_PUBLIC": True}  # noqa: F405

OTEL_TRACES_SAMPLE_RATE = 1.0  # 100% en dev, §5.3 Source B

NOTIFICATION_BACKEND = env("NOTIFICATION_BACKEND", default="console")


# Local development origins for Django Admin / CSRF
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
