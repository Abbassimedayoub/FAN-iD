"""
Settings communs à tous les environnements.

Règle absolue (§40 du master prompt / §5.1 Source B) : aucune variable
d'environnement critique n'a de valeur par défaut fonctionnelle. `env()` sans
`default=` lève immédiatement une erreur explicite si la variable manque —
un défaut silencieux en production est pire qu'un crash au démarrage.
"""

from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APPS_DIR = BASE_DIR / "apps"

env = environ.Env()
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# --- Sécurité / identité de service (critique, jamais de défaut) ---
SECRET_KEY = env("DJANGO_SECRET_KEY")
APP_VERSION = env("APP_VERSION", default="0.0.0-dev")
COMMIT_SHA = env("COMMIT_SHA", default="unknown")
ENVIRONMENT = env("OTEL_ENVIRONMENT", default="dev")

# --- Applications ---
DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "django.contrib.sessions",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "django_celery_beat",
    "django_prometheus",
    "django_migration_linter",
]

# Bounded contexts (§14 Source B / ADR-S-01). `core` en premier : il ne dépend
# d'aucun des autres et tous les autres peuvent en dépendre.
LOCAL_APPS = [
    "apps.core",
    "apps.identity",
    "apps.organizing",
    "apps.catalog",
    "apps.ordering",
    "apps.payments",
    "apps.ticketing",
    "apps.access",
    "apps.notifying",
    "apps.realtime",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
# Django Admin local/demo
for _app in [
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]:
    if _app not in INSTALLED_APPS:
        INSTALLED_APPS.append(_app)


# --- Middlewares — ordre imposé, §2.5 Source B / §33 master prompt ---
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.core.observability.middleware.CorrelationMiddleware",
    "apps.core.observability.middleware.RequestLogMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.core.idempotency.middleware.IdempotencyMiddleware",
    "apps.core.observability.metrics.MetricsMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "identity.User"

# --- Hachage des mots de passe (ADR-S-04 règle 5 / plan S1 §5.1) ---
PASSWORD_HASHERS = [
    "apps.identity.hashers.FanIdArgon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Base de données ---
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["ENGINE"] = "django_prometheus.db.backends.postgresql"

# --- Redis ---
REDIS_URL = env("REDIS_URL")
REDIS_CACHE_DB = env.int("REDIS_CACHE_DB", default=0)
REDIS_CHANNEL_LAYER_DB = env.int("REDIS_CHANNEL_LAYER_DB", default=1)
REDIS_LOCK_DB = env.int("REDIS_LOCK_DB", default=2)


def _redis_url_with_db(db_index: int) -> str:
    base = REDIS_URL.rsplit("/", 1)[0]
    return f"{base}/{db_index}"


REDIS_LOCK_URL = _redis_url_with_db(REDIS_LOCK_DB)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _redis_url_with_db(REDIS_CACHE_DB),
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [_redis_url_with_db(REDIS_CHANNEL_LAYER_DB)]},
    }
}

# --- Celery ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["apps.core.permissions.DenyAll"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.identity.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "apps.core.handlers.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON_RATE", default="60/min"),
        "user": env("THROTTLE_USER_RATE", default="300/min"),
        "register": env("THROTTLE_REGISTER_RATE", default="3/hour"),
        "login": env("THROTTLE_LOGIN_RATE", default="5/min"),
        "login_account": env(
            "THROTTLE_LOGIN_ACCOUNT_RATE",
            default="10/hour",
        ),
        "logout": env("THROTTLE_LOGOUT_RATE", default="20/hour"),
        "device_reset_request": env("THROTTLE_RESET_REQUEST_RATE", default="20/hour"),
        "device_reset_account": env("THROTTLE_RESET_ACCOUNT_RATE", default="3/hour"),
        "device_reset_confirm": env("THROTTLE_RESET_CONFIRM_RATE", default="30/hour"),
        "step_up_request": env("THROTTLE_STEP_UP_REQUEST_RATE", default="5/hour"),
        "step_up_confirm": env("THROTTLE_STEP_UP_CONFIRM_RATE", default="30/hour"),
        "password_reset_request": env(
            "THROTTLE_PASSWORD_RESET_REQUEST_RATE",
            default="10/hour",
        ),
        "password_reset_account": env(
            "THROTTLE_PASSWORD_RESET_ACCOUNT_RATE",
            default="3/hour",
        ),
        "password_reset_confirm": env(
            "THROTTLE_PASSWORD_RESET_CONFIRM_RATE",
            default="30/hour",
        ),
        "password_change": env("THROTTLE_PASSWORD_CHANGE_RATE", default="5/hour"),
        "profile_update": env("THROTTLE_PROFILE_UPDATE_RATE", default="20/hour"),
        "sessions_list": env("THROTTLE_SESSIONS_LIST_RATE", default="60/hour"),
        "session_revoke": env("THROTTLE_SESSION_REVOKE_RATE", default="20/hour"),
        # S1-A.6d : quota par session, et non par adresse IP.
        "refresh": env(
            "THROTTLE_REFRESH_RATE",
            default="30/hour",
        ),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FAN id API",
    "DESCRIPTION": ("Plateforme de billetterie sécurisée — Sprint 0 (socle plateforme)"),
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}

# --- CORS ---
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (*default_headers, "if-match", "x-correlation-id")
CORS_EXPOSE_HEADERS = ("ETag",)

# --- Transport du refresh token côté Web ---
REFRESH_COOKIE_NAME = env(
    "REFRESH_COOKIE_NAME",
    default="fanid_refresh",
)
REFRESH_COOKIE_DOMAIN = (
    env(
        "REFRESH_COOKIE_DOMAIN",
        default="",
    )
    or None
)
REFRESH_COOKIE_SECURE = env.bool(
    "REFRESH_COOKIE_SECURE",
    default=False,
)
REFRESH_COOKIE_SAMESITE = env(
    "REFRESH_COOKIE_SAMESITE",
    default="Lax",
)
REFRESH_COOKIE_PATH = env(
    "REFRESH_COOKIE_PATH",
    default="/api/v1/auth",
)
REFRESH_COOKIE_HTTPONLY = True

# --- Jetons JWT ---
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY")
JWT_ALGORITHM = env("JWT_ALGORITHM", default="HS256")
JWT_ISSUER = env("JWT_ISSUER", default="fanid-api")
JWT_LEEWAY_SECONDS = env.int(
    "JWT_LEEWAY_SECONDS",
    default=10,
)
JWT_ACCESS_LIFETIME_MINUTES = env.int(
    "JWT_ACCESS_LIFETIME_MINUTES",
    default=15,
)
JWT_REFRESH_LIFETIME_DAYS = env.int(
    "JWT_REFRESH_LIFETIME_DAYS",
    default=7,
)

# --- CSRF ---
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[],
)
CSRF_COOKIE_SAMESITE = env(
    "CSRF_COOKIE_SAMESITE",
    default="Lax",
)
SESSION_COOKIE_SAMESITE = env(
    "SESSION_COOKIE_SAMESITE",
    default="Lax",
)

SESSION_COOKIE_SAMESITE = env(
    "SESSION_COOKIE_SAMESITE",
    default="Lax",
)

# --- Internationalisation ---
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Fichiers statiques ---
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Idempotence / Outbox ---
IDEMPOTENCY_RETENTION_HOURS = env.int(
    "IDEMPOTENCY_RETENTION_HOURS",
    default=24,
)
IDEMPOTENCY_ORPHAN_GUARD_SECONDS = env.int(
    "IDEMPOTENCY_ORPHAN_GUARD_SECONDS",
    default=60,
)
OUTBOX_RELAY_BATCH_SIZE = env.int(
    "OUTBOX_RELAY_BATCH_SIZE",
    default=100,
)
OUTBOX_RELAY_INTERVAL_SECONDS = env.int(
    "OUTBOX_RELAY_INTERVAL_SECONDS",
    default=2,
)
OUTBOX_STUCK_AFTER_SECONDS = env.int(
    "OUTBOX_STUCK_AFTER_SECONDS",
    default=30,
)
OUTBOX_MAX_ATTEMPTS = env.int(
    "OUTBOX_MAX_ATTEMPTS",
    default=5,
)
OUTBOX_RETENTION_DAYS = env.int(
    "OUTBOX_RETENTION_DAYS",
    default=30,
)
OUTBOX_BACKOFF_SCHEDULE_SECONDS = [2, 8, 32, 120, 480]

CELERY_BEAT_SCHEDULE = {
    "outbox-relay": {
        "task": "core.outbox.relay_batch",
        "schedule": OUTBOX_RELAY_INTERVAL_SECONDS,
    },
    "outbox-purge-published": {
        "task": "core.outbox.purge_published",
        "schedule": 86400.0,
    },
    "idempotency-purge-expired": {
        "task": "core.idempotency.purge_expired",
        "schedule": 86400.0,
    },
}

# --- Secrets ---
SECRET_PROVIDER_BACKEND = env(
    "SECRET_PROVIDER",
    default="env",
)
SSM_PARAMETER_PREFIX = env(
    "SSM_PARAMETER_PREFIX",
    default="/fanid/dev/",
)

# --- django-migration-linter ---
MIGRATION_LINTER_OPTIONS = {
    # Deux migrations HISTORIQUES, déjà appliquées, sont écartées nommément.
    #
    # Elles ajoutent des colonnes NOT NULL sur des tables peuplées via le motif
    # canonique `default` temporaire + `preserve_default=False`. Le linter
    # signale ce motif sans distinguer l'usage correct de la faute qu'il vise.
    # Une migration appliquée ne se réécrit pas pour faire taire un
    # avertissement — principe posé au lot P1-001.
    #
    # `ignore_name` et non `exclude_migration_tests` : désarmer NOT_NULL ou
    # ALTER_COLUMN les neutraliserait pour TOUTES les migrations à venir, alors
    # que le Sprint 2 ajoutera des colonnes sur des tables peuplées et que
    # c'est exactement ce que ce contrôle doit attraper. Ici, deux migrations
    # sont écartées ; tout le reste du dépôt reste vérifié.
    "ignore_name": [
        "0002_role_and_user_identity",
        "0004_user_role",
        "0009_user_must_change_password_and_more",
    ],
    "include_apps": [
        "core",
        "identity",
        "organizing",
    ],
}

# --- Health / readiness ---
HEALTH_DEPENDENCY_TIMEOUT_SECONDS = env.float(
    "HEALTH_DEPENDENCY_TIMEOUT_SECONDS",
    default=2.0,
)

# --- Logging ---
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation": {"()": "apps.core.observability.logging.CorrelationLogFilter"},
    },
    "formatters": {
        "json": {"()": "apps.core.observability.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["correlation"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "fanid": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

# --- OpenTelemetry ---
OTEL_SERVICE_NAME = env(
    "OTEL_SERVICE_NAME",
    default="fanid-api",
)
OTEL_EXPORTER_OTLP_ENDPOINT = env(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    default="http://otel-collector:4317",
)
OTEL_ENABLED = True
