"""
Application Celery + propagation du contexte de trace OpenTelemetry.

Point technique critique (§2.4 Source B) : la propagation de `traceparent` dans
Celery n'est PAS automatique. On injecte l'en-tête à la publication
(`before_task_publish`) et on le restaure à l'exécution (`task_prerun`) pour
que la chaîne HTTP → Django → Celery reste une trace unique et cohérente.
Sans ce couplage, la trace s'arrête à la frontière asynchrone — précisément
ce que le test `test_trace_propagation.py` vérifie.
"""
import os

from celery import Celery
from celery.signals import before_task_publish, task_postrun, task_prerun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("fanid")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

_TRACEPARENT_HEADER_KEY = "traceparent"
_current_otel_context_token = {}


@before_task_publish.connect
def _inject_traceparent(headers=None, **kwargs):
    """Injecte le traceparent W3C courant dans les headers du message Celery."""
    try:
        from opentelemetry import propagate

        if headers is None:
            return
        carrier: dict = {}
        propagate.inject(carrier)
        if _TRACEPARENT_HEADER_KEY in carrier:
            headers[_TRACEPARENT_HEADER_KEY] = carrier[_TRACEPARENT_HEADER_KEY]
    except Exception:  # pragma: no cover - défense en profondeur, ne bloque jamais la publication
        pass


@task_prerun.connect
def _restore_traceparent(task_id=None, task=None, **kwargs):
    """Restaure le contexte de trace au début de l'exécution de la tâche."""
    try:
        from opentelemetry import context as otel_context
        from opentelemetry import propagate

        headers = getattr(task.request, "headers", None) or {}
        traceparent = headers.get(_TRACEPARENT_HEADER_KEY)
        if not traceparent:
            return
        carrier = {_TRACEPARENT_HEADER_KEY: traceparent}
        ctx = propagate.extract(carrier)
        token = otel_context.attach(ctx)
        _current_otel_context_token[task_id] = token
    except Exception:  # pragma: no cover
        pass


@task_postrun.connect
def _detach_traceparent(task_id=None, **kwargs):
    try:
        from opentelemetry import context as otel_context

        token = _current_otel_context_token.pop(task_id, None)
        if token is not None:
            otel_context.detach(token)
    except Exception:  # pragma: no cover
        pass
