"""
Settings de test — exécutés par pytest (voir backend/pytest.ini).

Différences volontaires par rapport à dev :
- mots de passe hachés en MD5 (rapidité des tests, jamais en prod)
- Celery en mode eager désactivé par défaut : les tests d'Outbox/idempotence
  doivent exercer le vrai chemin asynchrone via des tâches explicitement
  appelées, pas via l'exécution "magique" synchrone qui masquerait des bugs
  de sérialisation ou de propagation de traceparent (§2.4 Source B).
"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = ["*"]
SECRET_KEY = env("DJANGO_SECRET_KEY", default="test-secret-key-not-for-prod-use-only")

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

OTEL_TRACES_SAMPLE_RATE = 1.0
# Le bootstrap OTel réel (export réseau vers le collector) est désactivé en test :
# les tests de propagation de trace (test_trace_propagation.py) utilisent un
# TracerProvider en mémoire (InMemorySpanExporter) instrumenté explicitement par
# le test lui-même, pas ce bootstrap applicatif.
OTEL_ENABLED = False

# Le middleware de log applicatif reste actif (comportement testé), mais le
# niveau racine est relevé pour ne pas polluer la sortie pytest.
LOGGING["root"]["level"] = "WARNING"  # noqa: F405

# Capture en mémoire : si un test oublie d injecter son expéditeur,
# il capturera le code au lieu de le journaliser.
NOTIFICATION_BACKEND = "memory"
