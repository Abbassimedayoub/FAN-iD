"""
Application Celery FAN-iD.

La propagation OpenTelemetry du contexte W3C (`traceparent`) à travers
Celery est assurée par `CeleryInstrumentor`, initialisé dans
`apps.core.observability.tracing.bootstrap_tracing()`.

Le `correlation_id` applicatif est propagé séparément via le header
personnalisé `X-Correlation-ID` :
- injection avant publication ;
- restauration dans le ContextVar côté worker ;
- nettoyage du ContextVar après exécution.

`traceparent` et `correlation_id` sont deux mécanismes distincts.
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


# Les tâches core sont organisées par sous-domaines et ne résident donc pas
# dans apps.core.tasks, que l'autodiscovery Celery recherche par défaut.
#
# IMPORTANT :
# les modules de tests ne sont jamais importés par défaut. Le test
# d'intégration réel P0-8 peut explicitement activer son module de tâche
# avec FANID_IMPORT_TEST_TASKS=1 sur un worker dédié.
_celery_imports = [
    "apps.core.outbox.tasks",
    "apps.core.idempotency.tasks",
]

if os.environ.get("FANID_IMPORT_TEST_TASKS") == "1":
    _celery_imports.append("apps.core.tests.test_trace_http_celery_real")

app.conf.imports = tuple(_celery_imports)


# Ne surtout pas utiliser "correlation_id" ici :
# c'est une propriété réservée par Celery/AMQP.
_CORRELATION_ID_HEADER_KEY = "X-Correlation-ID"

_current_correlation_tokens = {}


@before_task_publish.connect
def _inject_correlation_id(headers=None, **kwargs):
    """
    Injecte le correlation_id applicatif courant dans un header Celery custom.

    Le `traceparent` reste entièrement géré par CeleryInstrumentor.
    """
    if headers is None:
        return

    from apps.core.observability.context import get_correlation_id

    correlation_id = get_correlation_id()

    if correlation_id:
        headers[_CORRELATION_ID_HEADER_KEY] = correlation_id


@task_prerun.connect
def _restore_correlation_id(task_id=None, task=None, **kwargs):
    """
    Restaure le correlation_id reçu dans le ContextVar du worker.
    """
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
    Nettoie le ContextVar après exécution afin d'empêcher toute fuite
    du correlation_id vers une tâche suivante du même worker.
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
