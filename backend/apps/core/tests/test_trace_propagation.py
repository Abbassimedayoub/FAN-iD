"""
Test de propagation de trace HTTP → Celery (§59 master prompt / §6.1 Source B).

C'est le test le plus critique du Sprint 0 : sans lui, une régression de la
propagation du `traceparent` W3C à travers Celery est invisible (aucune
erreur HTTP, aucun test fonctionnel ne casse) — seule l'observabilité en
souffre, et seulement en production, au pire moment. Ce test échoue si la
propagation casse.

Utilise un TracerProvider en mémoire (InMemorySpanExporter), sans réseau ni
collecteur OTel réel — cohérent avec `OTEL_ENABLED = False` en settings de
test (le bootstrap applicatif réseau est désactivé, ce test instrumente
explicitement lui-même un provider isolé).
"""
from celery import shared_task
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from config.celery import _inject_traceparent, _restore_traceparent


@shared_task(name="test.dummy_task_for_trace_propagation")
def _dummy_task():
    tracer = trace.get_tracer("fanid.test")
    with tracer.start_as_current_span("celery.dummy_task") as span:
        return format(span.get_span_context().trace_id, "032x")


def test_http_request_and_celery_task_share_one_trace():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer("fanid.test")

    # 1. Span racine HTTP (simulé).
    with tracer.start_as_current_span("http.request") as http_span:
        root_trace_id = http_span.get_span_context().trace_id

        # 2. Publication : le signal `before_task_publish` injecte le traceparent
        #    courant dans les headers du message Celery (config/celery.py).
        headers: dict = {}
        _inject_traceparent(headers=headers)
        assert "traceparent" in headers, "traceparent non injecté à la publication"

        # 3. Consommation : le signal `task_prerun` restaure le contexte à partir
        #    des headers — on simule l'objet `task.request` que Celery fournit.
        class _FakeRequest:
            pass

        class _FakeTask:
            request = _FakeRequest()

        fake_task = _FakeTask()
        fake_task.request.headers = headers

        _restore_traceparent(task_id="fake-task-id", task=fake_task)

        # 4. Exécution de la "tâche" sous ce contexte restauré : son span doit
        #    appartenir à la MÊME trace que le span HTTP racine.
        with tracer.start_as_current_span("celery.dummy_task") as task_span:
            task_trace_id = task_span.get_span_context().trace_id

    assert task_trace_id == root_trace_id, (
        "La tâche Celery a démarré une trace SÉPARÉE au lieu de continuer la "
        "trace HTTP — régression de propagation du traceparent (point critique "
        "§2.4 Source B)."
    )

    spans = exporter.get_finished_spans()
    span_names = {s.name for s in spans}
    assert {"http.request", "celery.dummy_task"}.issubset(span_names)
    # Les deux spans doivent partager le même trace_id — c'est UNE trace, pas deux.
    trace_ids = {s.context.trace_id for s in spans}
    assert len(trace_ids) == 1
