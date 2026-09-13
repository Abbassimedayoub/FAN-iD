"""
Settings de production.

§41 master prompt : aucun secret avec valeur par défaut fonctionnelle ici —
tout `env()` sans `default=` fait échouer le démarrage si la variable manque.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # pas de défaut : obligatoire


def _required_nonempty_env(name: str) -> str:
    """Read a required non-empty production environment variable."""
    value = env(name).strip()

    if not value:
        raise ImproperlyConfigured(f"{name} must be configured in production.")

    return value


def _required_backend(name: str, expected: str) -> str:
    """Require the provider selected by the production architecture."""
    value = _required_nonempty_env(name).lower()

    if value != expected:
        raise ImproperlyConfigured(f"{name} must be '{expected}' in production.")

    return value


PAYMENT_GATEWAY = _required_backend(
    "PAYMENT_GATEWAY",
    "stripe",
)
STRIPE_SECRET_KEY = _required_nonempty_env(
    "STRIPE_SECRET_KEY",
)
STRIPE_WEBHOOK_SECRET = _required_nonempty_env(
    "STRIPE_WEBHOOK_SECRET",
)

OBJECT_STORAGE_BACKEND = _required_backend(
    "OBJECT_STORAGE_BACKEND",
    "r2",
)
R2_ACCOUNT_ID = _required_nonempty_env(
    "R2_ACCOUNT_ID",
)
R2_ACCESS_KEY_ID = _required_nonempty_env(
    "R2_ACCESS_KEY_ID",
)
R2_SECRET_ACCESS_KEY = _required_nonempty_env(
    "R2_SECRET_ACCESS_KEY",
)
R2_BUCKET = _required_nonempty_env(
    "R2_BUCKET",
)

# --- En-têtes de sécurité (§5.1 Source B) ---
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Le refresh est TOUJOURS transmis en Secure en production — non négociable,
# contrairement au développement local où l'absence de TLS l'impose à False.
REFRESH_COOKIE_SECURE = True
REFRESH_REQUIRE_TRUSTED_ORIGIN = True

# Obligatoire en production : sans liste blanche, toute requête authentifiée par
# cookie depuis une origine tierce serait acceptée.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# --- Production API documentation surface ---
API_DOCS_ENABLED = False
SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "SERVE_PUBLIC": False}  # noqa: F405

# Render injects production secrets through environment variables.
SECRET_PROVIDER_BACKEND = "env"

OTEL_TRACES_SAMPLE_RATE = env.float(
    "OTEL_TRACES_SAMPLER_ARG", default=0.2
)  # 20% + conservation des erreurs (voir tracing.py)

LOGGING["root"]["level"] = "INFO"  # noqa: F405

# Pas de défaut : un canal de notification absent doit empêcher le démarrage,
# pas se replier en silence sur la console.
NOTIFICATION_BACKEND = env("NOTIFICATION_BACKEND")
