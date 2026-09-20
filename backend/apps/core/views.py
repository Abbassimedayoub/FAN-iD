"""
Platform health endpoints: liveness and readiness.
`/metrics` is served by django-prometheus (urls.py).
"""

import logging
import time

from django.conf import settings
from django.db import connections
from django.http import HttpRequest, JsonResponse
from django.views import View

_START_TIME = time.monotonic()

logger = logging.getLogger("fanid.health")

# Generic message returned to the CLIENT when any dependency fails.
# Never expose exception text: connection strings, internal hostnames, or
# PostgreSQL/Redis driver messages must not reach an unauthenticated caller
# of /health/ready.
# The complete exception is always logged server-side with
# `logger.warning(..., exc_info=True)`.
_GENERIC_UNAVAILABLE_DETAIL = "dépendance indisponible — voir les journaux serveur pour le détail"


def libpq_connect_timeout(timeout: float) -> int:
    """
    Normalize an application-level timeout (float, seconds) to a value that
    libpq actually accepts for `connect_timeout`.

    libpq has two silent constraints that matter here:

    1. The value must be a decimal INTEGER number of seconds. libpq 16 rejects
       `connect_timeout=2.0` with "invalid integer value". A float survives
       here only because of implicit psycopg coercion; relying on that is
       fragile, and `int()` truncation would round down.
    2. The minimum effective timeout is 2 seconds, while 0 means "wait
       INDEFINITELY" to libpq. A configuration value of 0.5 could therefore
       create a probe with no timeout at all.

    Clamp explicitly to an integer >= 2 instead of delegating to implicit
    conversion.
    """
    return max(2, int(round(timeout)))


class HealthView(View):
    """
    Bootstrap health endpoint.

    The acceptance contract requires `/api/v1/health` to prove that the two
    dependencies required for functional API startup — PostgreSQL and Redis —
    are reachable. Detailed readiness remains available separately on
    `/health/ready`, including Celery and latency checks.
    """

    def get(self, request: HttpRequest) -> JsonResponse:
        timeout = settings.HEALTH_DEPENDENCY_TIMEOUT_SECONDS
        database = ReadinessView._check_database(timeout)
        redis = ReadinessView._check_redis(timeout)

        db_status = database["status"]
        redis_status = redis["status"]
        healthy = db_status == "ok" and redis_status == "ok"

        return JsonResponse(
            {
                "status": "ok" if healthy else "down",
                "db": db_status,
                "redis": redis_status,
            },
            status=200 if healthy else 503,
        )


class ReadinessView(View):
    """
    Readiness endpoint — checks PostgreSQL (critical, so failure returns 503),
    Redis, and Celery (non-critical, so failures return `degraded` with 200),
    with a timeout applied to each probe.
    """

    def get(self, request: HttpRequest) -> JsonResponse:
        timeout = settings.HEALTH_DEPENDENCY_TIMEOUT_SECONDS
        checks = {
            "database": self._check_database(timeout),
            "redis": self._check_redis(timeout),
            "celery": self._check_celery(timeout),
            "outbox": self._check_outbox(),
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
        Apply a real timeout: open a dedicated, short-lived psycopg connection
        with both `connect_timeout` (TCP/auth phase) and SQL
        `statement_timeout` (query phase) bounded by `timeout` seconds.

        The shared/persistent Django connection (`connections["default"]`,
        `CONN_MAX_AGE=60`) is deliberately avoided for this probe. A query
        on that connection has no default timeout and could hang indefinitely
        on a degraded network. The dedicated probe therefore guarantees that
        the configured health-check timeout is actually enforced.
        """
        start = time.monotonic()
        try:
            import psycopg

            params = dict(connections["default"].get_connection_params())
            params.pop("connect_timeout", None)
            existing_options = params.pop("options", "")
            statement_timeout_ms = max(int(timeout * 1000), 1)
            params["options"] = f"{existing_options} -c statement_timeout={statement_timeout_ms}".strip()

            with psycopg.connect(
                connect_timeout=libpq_connect_timeout(timeout), **params
            ) as probe_connection:
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
    def _check_outbox() -> dict:
        """
        Report an Outbox queue that is no longer making progress.

        An active queue may briefly contain PENDING or FAILED events. It becomes
        degraded only when an event exceeds OUTBOX_STUCK_AFTER_SECONDS, or when
        at least one DEAD event exists.
        """
        try:
            from datetime import timedelta

            from django.utils import timezone

            from apps.core.outbox.models import OutboxEvent

            dead_count = OutboxEvent.objects.filter(
                status=OutboxEvent.Status.DEAD,
            ).count()

            if dead_count:
                return {
                    "status": "degraded",
                    "detail": "dead events detected",
                    "dead": dead_count,
                }

            cutoff = timezone.now() - timedelta(
                seconds=settings.OUTBOX_STUCK_AFTER_SECONDS,
            )

            stuck_count = OutboxEvent.objects.filter(
                status__in=[
                    OutboxEvent.Status.PENDING,
                    OutboxEvent.Status.FAILED,
                ],
                occurred_at__lt=cutoff,
            ).count()

            if stuck_count:
                return {
                    "status": "degraded",
                    "detail": "stuck events detected",
                    "stuck": stuck_count,
                }

            return {
                "status": "ok",
            }
        except Exception:
            logger.warning(
                "readiness_outbox_check_failed",
                exc_info=True,
            )
            return {
                "status": "degraded",
                "detail": _GENERIC_UNAVAILABLE_DETAIL,
            }

    @staticmethod
    def _check_celery(timeout: float) -> dict:
        try:
            from config.celery import app as celery_app

            replies = celery_app.control.ping(timeout=timeout)
            if replies:
                return {"status": "ok"}
            # Fixed string, not derived from an exception, so it cannot leak exception details.
            return {"status": "degraded", "detail": "no heartbeat"}
        except Exception:
            logger.warning("readiness_celery_check_failed", exc_info=True)
            return {"status": "degraded", "detail": _GENERIC_UNAVAILABLE_DETAIL}
