"""
Settings de production.

§41 master prompt : aucun secret avec valeur par défaut fonctionnelle ici —
tout `env()` sans `default=` fait échouer le démarrage si la variable manque.
"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # pas de défaut : obligatoire

# --- En-têtes de sécurité (§5.1 Source B) ---
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Le refresh est TOUJOURS transmis en Secure en production — non négociable,
# contrairement au développement local où l'absence de TLS l'impose à False.
REFRESH_COOKIE_SECURE = True

# Obligatoire en production : sans liste blanche, toute requête authentifiée par
# cookie depuis une origine tierce serait acceptée.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# --- Schema/Swagger protégés en production (§37 master prompt) ---
SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "SERVE_PUBLIC": False}  # noqa: F405

# --- Secrets : SsmSecretProvider (implémentation réelle hors périmètre S0 local) ---
SECRET_PROVIDER_BACKEND = "ssm"

OTEL_TRACES_SAMPLE_RATE = env.float(
    "OTEL_TRACES_SAMPLER_ARG", default=0.2
)  # 20% + conservation des erreurs (voir tracing.py)

LOGGING["root"]["level"] = "INFO"  # noqa: F405
