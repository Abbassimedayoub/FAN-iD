"""
Endpoints plateforme du Sprint 0 (§34-36 master prompt, §3.2 Source B) :
liveness, readiness. `/metrics` est servi par django-prometheus (urls.py).
"""

import logging
import time

from django.conf import settings
from django.db import connections
from django.http import HttpRequest, JsonResponse
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


def libpq_connect_timeout(timeout: float) -> int:
    """
    Normalise un délai de garde applicatif (float, secondes) vers ce que libpq
    accepte réellement pour `connect_timeout`.

    Deux contraintes de libpq, toutes deux silencieuses — défaut révélé par le
    premier passage réel de mypy sur ce dépôt (P1-000) :

    1. La valeur doit être un ENTIER décimal de secondes. Vérifié : libpq 16
       rejette `connect_timeout=2.0` avec « invalid integer value ». Un float
       ne survit ici que grâce à une coercition implicite de psycopg — s'y
       fier est fragile, et une troncature `int()` arrondit vers le bas.
    2. Le plancher est de 2 secondes, et la valeur 0 signifie pour libpq
       « attendre INDÉFINIMENT ». Une configuration à 0.5 produirait donc une
       sonde SANS AUCUN délai de garde : l'exact inverse de l'exigence §36, et
       un incident invisible tant que la base répond.

    On borne donc explicitement à un entier >= 2 plutôt que de déléguer à une
    conversion implicite.
    """
    return max(2, int(round(timeout)))


class HealthView(View):
    """
    Health de bootstrap Sprint 1.

    Le contrat d'acceptation exige que `/api/v1/health` prouve que les deux
    dépendances nécessaires au démarrage fonctionnel de l'API — PostgreSQL et
    Redis — sont joignables. La readiness détaillée reste disponible séparément
    sur `/health/ready`, notamment pour Celery et les latences.
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
    Readiness — vérifie PostgreSQL (critique ⇒ 503 si en panne), Redis et
    Celery (non critiques ⇒ `degraded` en 200), avec un délai de garde par
    sonde (§36 master prompt).
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
        Signale une file Outbox qui ne progresse plus.

        Une file active peut contenir brièvement des événements PENDING ou
        FAILED. Elle devient dégradée uniquement lorsqu'un événement dépasse
        OUTBOX_STUCK_AFTER_SECONDS, ou lorsqu'un événement DEAD existe.
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
            # Chaîne fixe, non dérivée d'une exception — sans risque de fuite.
            return {"status": "degraded", "detail": "no heartbeat"}
        except Exception:
            logger.warning("readiness_celery_check_failed", exc_info=True)
            return {"status": "degraded", "detail": _GENERIC_UNAVAILABLE_DETAIL}
