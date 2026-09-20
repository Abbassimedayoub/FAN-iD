"""
FAN-iD Celery application.

OpenTelemetry propagates the W3C trace context through Celery instrumentation.
The application correlation ID is propagated separately through a custom
X-Correlation-ID header, restored in the worker context, then cleared after task
execution. Trace context and correlation ID remain distinct mechanisms.
"""

import os

from celery import Celery
from celery.signals import before_task_publish, task_postrun, task_prerun

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.dev",
)

app = Celery("fanid")

app.config_from_object(
    "django.conf:settings",
    namespace="CELERY",
)

app.autodiscover_tasks()


# Core tasks are organized by subdomain rather than living in apps.core.tasks,
# which is Celery's default autodiscovery target.
#
# IMPORTANT :
# Test task modules are never imported by default; dedicated integration workers
# may opt in explicitly through FANID_IMPORT_TEST_TASKS=1.
_celery_imports = [
    "apps.core.outbox.tasks",
    "apps.core.idempotency.tasks",
]

if os.environ.get("FANID_IMPORT_TEST_TASKS") == "1":
    _celery_imports.append("apps.core.tests.test_trace_http_celery_real")

app.conf.imports = tuple(_celery_imports)


# Do not use the name "correlation_id" here; Celery/AMQP reserves it.
_CORRELATION_ID_HEADER_KEY = "X-Correlation-ID"

_current_correlation_tokens = {}


@before_task_publish.connect
def _inject_correlation_id(headers=None, **kwargs):
    """
    Inject the current application correlation ID into a custom Celery header; traceparent stays
    managed by CeleryInstrumentor.
    """
    if headers is None:
        return

    from apps.core.observability.context import get_correlation_id

    correlation_id = get_correlation_id()

    if correlation_id:
        headers[_CORRELATION_ID_HEADER_KEY] = correlation_id


@task_prerun.connect
def _restore_correlation_id(task_id=None, task=None, **kwargs):
    """Restore the received correlation ID into the worker ContextVar."""
    if task is None:
        return

    from apps.core.observability.context import set_correlation_id

    headers = getattr(task.request, "headers", None) or {}
    correlation_id = headers.get(_CORRELATION_ID_HEADER_KEY)

    if not correlation_id:
        return

    token = set_correlation_id(correlation_id)

    if task_id is not None:
        _current_correlation_tokens[task_id] = token


@task_postrun.connect
def _reset_correlation_id(task_id=None, **kwargs):
    """
    Clear the ContextVar after execution so the correlation ID cannot leak into the next task on the
    same worker.
    """
    if task_id is None:
        return

    from apps.core.observability.context import reset_correlation_id

    token = _current_correlation_tokens.pop(
        task_id,
        None,
    )

    if token is not None:
        reset_correlation_id(token)
