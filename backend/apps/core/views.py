"""
Endpoints plateforme du Sprint 0 (§34-36 master prompt, §3.2 Source B) :
liveness, readiness. `/metrics` est servi par django-prometheus (urls.py).
"""
import time

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.views import View

_START_TIME = time.monotonic()


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
        start = time.monotonic()
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {"status": "ok", "latency_ms": round((time.monotonic() - start) * 1000, 1)}
        except Exception as exc:  # noqa: BLE001 — on rapporte, jamais on ne propage
            return {"status": "down", "detail": str(exc)[:200]}

    @staticmethod
    def _check_redis(timeout: float) -> dict:
        start = time.monotonic()
        try:
            import redis as redis_lib

            client = redis_lib.from_url(settings.REDIS_URL, socket_timeout=timeout)
            client.ping()
            return {"status": "ok", "latency_ms": round((time.monotonic() - start) * 1000, 1)}
        except Exception as exc:  # noqa: BLE001
            return {"status": "degraded", "detail": str(exc)[:200]}

    @staticmethod
    def _check_celery(timeout: float) -> dict:
        try:
            from config.celery import app as celery_app

            replies = celery_app.control.ping(timeout=timeout)
            if replies:
                return {"status": "ok"}
            return {"status": "degraded", "detail": "no heartbeat"}
        except Exception as exc:  # noqa: BLE001
            return {"status": "degraded", "detail": str(exc)[:200]}
