"""
Endpoints plateforme du Sprint 0 (§34-36 master prompt, §3.2 Source B) :
liveness, readiness. `/metrics` est servi par django-prometheus (urls.py).
"""
import logging
import time

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.views import View

_START_TIME = time.monotonic()

logger = logging.getLogger("fanid.health")

# Message générique renvoyé au CLIENT pour toute dépendance en échec —
# jamais le texte de l'exception (§P1.B.2 plan de correction : une chaîne de
# connexion, un nom d'hôte interne ou un message pilote PostgreSQL/Redis ne
# doivent jamais atteindre un appelant non authentifié de /health/ready).
# L'exception complète est systématiquement consignée côté serveur via
# `logger.warning(..., exc_info=True)`.
_GENERIC_UNAVAILABLE_DETAIL = "dépendance indisponible — voir les journaux serveur pour le détail"


class HealthView(View):
    """
    Liveness — vérifie uniquement que le processus répond. NE dépend
    d'AUCUNE dépendance externe (§35 master prompt) : une sonde de vie qui
    teste la base redémarre le conteneur quand c'est la base qui est en
    panne, ce qui aggrave l'incident.
    """

    def get(self, request):
        return JsonResponse(
            {
                "status": "ok",
                "version": settings.APP_VERSION,
                "commit": settings.COMMIT_SHA,
            }
        )


class ReadinessView(View):
    """
    Readiness — vérifie PostgreSQL (critique ⇒ 503 si en panne), Redis et
    Celery (non critiques ⇒ `degraded` en 200), avec un délai de garde par
    sonde (§36 master prompt).
    """

    def get(self, request):
        timeout = settings.HEALTH_DEPENDENCY_TIMEOUT_SECONDS
        checks = {
            "database": self._check_database(timeout),
            "redis": self._check_redis(timeout),
            "celery": self._check_celery(timeout),
        }

        db_ok = checks["database"]["status"] == "ok"
        any_degraded = any(c["status"] != "ok" for c in checks.values())

        if not db_ok:
            overall_status = "down"
            http_status = 503
        elif any_degraded:
            overall_status = "degraded"
            http_status = 200
        else:
            overall_status = "ok"
            http_status = 200

        return JsonResponse(
            {
                "status": overall_status,
                "checks": checks,
                "version": settings.APP_VERSION,
                "commit": settings.COMMIT_SHA,
                "uptime_s": round(time.monotonic() - _START_TIME, 1),
            },
            status=http_status,
        )

    @staticmethod
    def _check_database(timeout: float) -> dict:
        """
        Timeout RÉELLEMENT appliqué (§P1.B.1) : une connexion psycopg dédiée
        et éphémère est ouverte avec `connect_timeout` (phase TCP/auth) ET
        `statement_timeout` SQL (phase requête) bornés à `timeout` secondes.

        La connexion partagée/poolée de Django (`connections["default"]`,
        `CONN_MAX_AGE=60`) est délibérément évitée pour cette sonde : une
        requête posée dessus n'a AUCUN timeout par défaut et pourrait geler
        indéfiniment sur un réseau dégradé, ce qui viderait de son sens le
        "délai de garde de 2s par sonde" exigé (§36 master prompt) — la
        version précédente de ce code recevait `timeout` en paramètre mais
        ne l'appliquait nulle part, bug corrigé ici.
        """
        start = time.monotonic()
        try:
            import psycopg

            params = dict(connections["default"].get_connection_params())
            params.pop("connect_timeout", None)
            existing_options = params.pop("options", "")
            statement_timeout_ms = max(int(timeout * 1000), 1)
            params["options"] = f"{existing_options} -c statement_timeout={statement_timeout_ms}".strip()

            with psycopg.connect(connect_timeout=timeout, **params) as probe_connection:
                with probe_connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            return {"status": "ok", "latency_ms": round((time.monotonic() - start) * 1000, 1)}
        except Exception:
            logger.warning("readiness_database_check_failed", exc_info=True)
            return {"status": "down", "detail": _GENERIC_UNAVAILABLE_DETAIL}

    @staticmethod
    def _check_redis(timeout: float) -> dict:
        start = time.monotonic()
        try:
            import redis as redis_lib

            client = redis_lib.from_url(
                settings.REDIS_URL, socket_timeout=timeout, socket_connect_timeout=timeout
            )
            client.ping()
            return {"status": "ok", "latency_ms": round((time.monotonic() - start) * 1000, 1)}
        except Exception:
            logger.warning("readiness_redis_check_failed", exc_info=True)
            return {"status": "degraded", "detail": _GENERIC_UNAVAILABLE_DETAIL}

    @staticmethod
    def _check_celery(timeout: float) -> dict:
        try:
            from config.celery import app as celery_app

            replies = celery_app.control.ping(timeout=timeout)
            if replies:
                return {"status": "ok"}
            # Chaîne fixe, non dérivée d'une exception — sans risque de fuite.
            return {"status": "degraded", "detail": "no heartbeat"}
        except Exception:
            logger.warning("readiness_celery_check_failed", exc_info=True)
            return {"status": "degraded", "detail": _GENERIC_UNAVAILABLE_DETAIL}
