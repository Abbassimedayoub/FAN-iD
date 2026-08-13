import json
import threading
import time

import pytest
from django.db import connections
from django.http import JsonResponse
from django.test import Client, override_settings
from django.urls import path

from apps.core.idempotency.middleware import REPLAYED_MARKER_HEADER
from apps.core.idempotency.models import IdempotencyRecord

_execution_count = 0
_execution_lock = threading.Lock()


def purchase_view(request):
    global _execution_count

    with _execution_lock:
        _execution_count += 1
        execution_number = _execution_count

    # Laisse une petite fenêtre pour provoquer une vraie compétition HTTP.
    time.sleep(0.15)

    return JsonResponse(
        {
            "ok": True,
            "execution_number": execution_number,
        },
        status=201,
    )


urlpatterns = [
    path("test/idempotent-purchase", purchase_view),
]


@pytest.mark.django_db(transaction=True)
@override_settings(ROOT_URLCONF=__name__)
def test_five_concurrent_http_requests_execute_business_logic_only_once(user):
    global _execution_count
    _execution_count = 0

    key = "http-concurrency-key"
    payload = {"ticket_id": "123"}
    barrier = threading.Barrier(5)

    results = []
    results_lock = threading.Lock()

    def worker():
        connections.close_all()

        client = Client()
        client.force_login(user)

        barrier.wait()

        response = client.post(
            "/test/idempotent-purchase",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        with results_lock:
            results.append(
                {
                    "status": response.status_code,
                    "replayed": response.headers.get(REPLAYED_MARKER_HEADER),
                    "body": response.json(),
                }
            )

        connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(5)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Invariant critique : une seule vraie exécution métier.
    assert _execution_count == 1, results

    assert len(results) == 5

    # Une requête doit avoir réellement exécuté la vue.
    successful_originals = [
        result for result in results if result["status"] == 201 and result["replayed"] != "true"
    ]
    assert len(successful_originals) == 1, results

    # Les quatre concurrentes ne doivent JAMAIS déclencher une autre exécution.
    # Selon leur timing exact, elles peuvent recevoir 409 IN_PROGRESS
    # ou arriver après completion et obtenir immédiatement un replay.
    other_results = [result for result in results if result not in successful_originals]
    assert len(other_results) == 4

    assert all(result["status"] in {201, 409} for result in other_results), results

    assert (
        IdempotencyRecord.objects.filter(
            key=key,
            user_id=user.pk,
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
@override_settings(ROOT_URLCONF=__name__)
def test_completed_http_request_is_replayed_four_times_without_reexecution(user):
    global _execution_count
    _execution_count = 0

    key = "http-replay-key"
    payload = {"ticket_id": "456"}

    client = Client()
    client.force_login(user)

    first = client.post(
        "/test/idempotent-purchase",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=key,
    )

    assert first.status_code == 201
    assert _execution_count == 1

    replays = []

    for _ in range(4):
        response = client.post(
            "/test/idempotent-purchase",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        replays.append(response)

    assert _execution_count == 1

    assert all(response.status_code == 201 for response in replays)
    assert all(response.headers.get(REPLAYED_MARKER_HEADER) == "true" for response in replays)
