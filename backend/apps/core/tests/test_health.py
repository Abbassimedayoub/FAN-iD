"""
/health et /health/ready — nominal, base coupée ⇒ 503, Celery coupé ⇒ degraded/200
(§56 master prompt / §6.1 Source B).

Nécessite une vraie base PostgreSQL (voir docker-compose.yml) : ces tests
s'exécutent via `docker compose exec api pytest`, pas dans ce sandbox sans
réseau/Docker (voir SPRINT_TEST_REPORT.md).
"""

from unittest import mock

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_returns_the_exact_sprint_1_contract():
    client = APIClient()

    with (
        mock.patch(
            "apps.core.views.ReadinessView._check_database",
            return_value={"status": "ok"},
        ),
        mock.patch(
            "apps.core.views.ReadinessView._check_redis",
            return_value={"status": "ok"},
        ),
    ):
        response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "ok",
        "redis": "ok",
    }


@pytest.mark.django_db
def test_health_returns_503_when_a_required_dependency_is_unavailable():
    client = APIClient()

    with (
        mock.patch(
            "apps.core.views.ReadinessView._check_database",
            return_value={"status": "ok"},
        ),
        mock.patch(
            "apps.core.views.ReadinessView._check_redis",
            return_value={"status": "degraded", "detail": "hidden"},
        ),
    ):
        response = client.get(reverse("health"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "down",
        "db": "ok",
        "redis": "degraded",
    }


@pytest.mark.django_db
def test_readiness_nominal_returns_ok():
    client = APIClient()
    response = client.get(reverse("health-ready"))

    assert response.status_code == 200
    assert response.json()["checks"]["database"]["status"] == "ok"


@pytest.mark.django_db
def test_readiness_returns_503_when_database_down():
    client = APIClient()
    with mock.patch(
        "apps.core.views.ReadinessView._check_database",
        return_value={"status": "down", "detail": "connection refused"},
    ):
        response = client.get(reverse("health-ready"))

    assert response.status_code == 503
    assert response.json()["status"] == "down"


@pytest.mark.django_db
def test_readiness_degraded_when_celery_down_but_db_up():
    """Celery indisponible ne doit PAS transformer une panne partielle en panne totale (§36)."""
    client = APIClient()
    with mock.patch(
        "apps.core.views.ReadinessView._check_celery",
        return_value={"status": "degraded", "detail": "no heartbeat"},
    ):
        response = client.get(reverse("health-ready"))

    assert response.status_code == 200  # PAS 503 : Celery n'est pas critique
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["celery"]["status"] == "degraded"


@pytest.mark.django_db
def test_readiness_reports_outbox_ok_when_queue_is_empty():
    from apps.core.views import ReadinessView

    result = ReadinessView._check_outbox()

    assert result == {
        "status": "ok",
    }


@pytest.mark.django_db
def test_readiness_reports_stuck_outbox_as_degraded(settings):
    from datetime import timedelta
    import uuid

    from django.utils import timezone

    from apps.core.outbox.models import OutboxEvent
    from apps.core.views import ReadinessView

    settings.OUTBOX_STUCK_AFTER_SECONDS = 30

    OutboxEvent.objects.create(
        event_type="test.health.stuck",
        event_version=1,
        aggregate_type="health",
        aggregate_id=uuid.uuid4(),
        payload={},
        status=OutboxEvent.Status.PENDING,
        attempts=0,
        available_at=timezone.now(),
        occurred_at=(
            timezone.now()
            - timedelta(minutes=5)
        ),
    )

    result = ReadinessView._check_outbox()

    assert result["status"] == "degraded"
    assert result["detail"] == "stuck events detected"
    assert result["stuck"] == 1


@pytest.mark.django_db
def test_readiness_reports_dead_outbox_as_degraded():
    import uuid

    from django.utils import timezone

    from apps.core.outbox.models import OutboxEvent
    from apps.core.views import ReadinessView

    OutboxEvent.objects.create(
        event_type="test.health.dead",
        event_version=1,
        aggregate_type="health",
        aggregate_id=uuid.uuid4(),
        payload={},
        status=OutboxEvent.Status.DEAD,
        attempts=5,
        available_at=timezone.now(),
        occurred_at=timezone.now(),
    )

    result = ReadinessView._check_outbox()

    assert result["status"] == "degraded"
    assert result["detail"] == "dead events detected"
    assert result["dead"] == 1
