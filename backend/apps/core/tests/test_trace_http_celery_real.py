import json
import time
import uuid

import pytest
import redis
from celery import shared_task
from django.conf import settings
from django.http import JsonResponse
from django.test import Client, override_settings
from django.urls import path
from opentelemetry import trace

from apps.core.observability.context import get_correlation_id


@shared_task(bind=True, name="test.trace_http_celery_real")
def trace_probe_task(self, probe_id: str):
    span = trace.get_current_span()
    ctx = span.get_span_context()

    trace_id = format(ctx.trace_id, "032x")
    span_id = format(ctx.span_id, "016x")
    correlation_id = get_correlation_id()

    received_headers = dict(getattr(self.request, "headers", None) or {})

    client = redis.Redis(
        host="redis",
        port=6379,
        db=4,
        decode_responses=True,
    )

    client.setex(
        f"test:trace-probe:{probe_id}",
        30,
        json.dumps(
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "correlation_id": correlation_id,
                "received_headers": received_headers,
            },
            default=str,
        ),
    )

    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "correlation_id": correlation_id,
        "received_headers": received_headers,
    }


def trace_trigger_view(request):
    probe_id = str(uuid.uuid4())

    http_span = trace.get_current_span()
    http_ctx = http_span.get_span_context()

    http_trace_id = format(http_ctx.trace_id, "032x")
    http_span_id = format(http_ctx.span_id, "016x")
    http_correlation_id = get_correlation_id()

    trace_probe_task.delay(probe_id)

    return JsonResponse(
        {
            "probe_id": probe_id,
            "http_trace_id": http_trace_id,
            "http_span_id": http_span_id,
            "http_correlation_id": http_correlation_id,
        }
    )


urlpatterns = [
    path("test/trace-celery", trace_trigger_view),
]


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    not settings.OTEL_ENABLED,
    reason="Test d'intégration réel nécessitant OTEL_ENABLED=True et un worker Celery réel.",
)
@override_settings(ROOT_URLCONF=__name__)
def test_real_http_request_and_real_celery_worker_share_trace():
    client = Client()

    response = client.get(
        "/test/trace-celery",
        HTTP_X_CORRELATION_ID="p0-8-test",
    )

    assert response.status_code == 200

    body = response.json()

    probe_id = body["probe_id"]
    http_trace_id = body["http_trace_id"]
    http_span_id = body["http_span_id"]
    http_correlation_id = body["http_correlation_id"]

    redis_client = redis.Redis(
        host="redis",
        port=6379,
        db=4,
        decode_responses=True,
    )

    key = f"test:trace-probe:{probe_id}"

    worker_result = None

    for _ in range(50):
        raw = redis_client.get(key)

        if raw:
            worker_result = json.loads(raw)
            break

        time.sleep(0.1)

    assert worker_result is not None, (
        "Le worker Celery réel n'a pas écrit le résultat de trace dans Redis."
    )

    celery_trace_id = worker_result["trace_id"]
    celery_span_id = worker_result["span_id"]
    celery_correlation_id = worker_result["correlation_id"]

    assert http_trace_id != "00000000000000000000000000000000"
    assert celery_trace_id != "00000000000000000000000000000000"

    # Même trace HTTP -> Celery.
    assert celery_trace_id == http_trace_id

    # Deux spans distincts dans la même trace.
    assert celery_span_id != http_span_id

    # Correlation ID propagé jusqu'au vrai worker.
    assert http_correlation_id == "p0-8-test"
    assert celery_correlation_id == "p0-8-test"
    assert celery_correlation_id == http_correlation_id