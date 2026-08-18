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
def test_health_liveness_never_touches_database():
    """Liveness ne doit toucher AUCUNE dépendance (§35 master prompt)."""
    client = APIClient()
    with mock.patch("django.db.connections") as mocked_connections:
        response = client.get(reverse("health"))
        mocked_connections.__getitem__.assert_not_called()

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
