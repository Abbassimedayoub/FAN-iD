"""
Test de propagation de trace HTTP -> Celery.

La propagation W3C `traceparent` est assurée par l'instrumentation officielle
OpenTelemetry Celery (`CeleryInstrumentor`), pas par des handlers Celery
maison.

Ce test vérifie qu'un contexte parent injecté dans un message Celery est
correctement restauré côté tâche et que le span de tâche appartient à la
même trace que le span HTTP simulé.
"""

from opentelemetry import context, propagate, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


def test_http_request_and_celery_task_share_one_trace():
    exporter = InMemorySpanExporter()

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Le provider global peut déjà être défini dans certains environnements.
    # On utilise donc directement le provider local pour créer le tracer.
    tracer = provider.get_tracer("fanid.test")

    # 1. Span HTTP simulé.
    with tracer.start_as_current_span("http.request") as http_span:
        http_ctx = http_span.get_span_context()
        root_trace_id = http_ctx.trace_id
        http_span_id = http_ctx.span_id

        # 2. Simulation de la publication Celery :
        # CeleryInstrumentor fait propagate.inject(headers).
        headers = {}
        propagate.inject(headers)

        assert "traceparent" in headers

    # 3. Simulation côté worker :
    # CeleryInstrumentor fait propagate.extract(headers).
    extracted_context = propagate.extract(headers)

    token = context.attach(extracted_context)
    try:
        with tracer.start_as_current_span("celery.dummy_task") as task_span:
            task_ctx = task_span.get_span_context()

            task_trace_id = task_ctx.trace_id
            task_span_id = task_ctx.span_id
    finally:
        context.detach(token)

    # Même trace.
    assert task_trace_id == root_trace_id

    # Mais span différent.
    assert task_span_id != http_span_id

    spans = exporter.get_finished_spans()
    span_names = {span.name for span in spans}

    assert {"http.request", "celery.dummy_task"}.issubset(span_names)

    trace_ids = {span.context.trace_id for span in spans}
    assert trace_ids == {root_trace_id}