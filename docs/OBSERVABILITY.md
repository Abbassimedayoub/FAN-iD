# Observabilité — FAN id (Sprint 0)

Référence : ADR-S-07, Source B §2.4/§5.3, master prompt §25-32.

## Chaîne de bout en bout

```
Client → CorrelationMiddleware (génère/propage X-Correlation-ID)
       → OTel SDK (span racine HTTP)
       → ViewSet
       → JsonFormatter + SecretRedactor (logs) → stdout → Docker
       → MetricsMiddleware (RED) → /metrics → Prometheus (via otel-collector:8889)
       → apply_async + traceparent injecté (config/celery.py) → tâche Celery
                                                                → traceparent restauré → span lié
       → OTel Collector (otlp:4317/4318) → exporteurs debug + prometheus
```

## Traces (OpenTelemetry)

- Instrumentation automatique : Django, psycopg, Redis, requests, Celery
  (`apps/core/observability/tracing.py`).
- Propagation W3C `traceparent` à travers Celery : injection à la
  publication (`before_task_publish`), restauration à l'exécution
  (`task_prerun`) — voir `backend/config/celery.py`. **Test dédié :**
  `apps/core/tests/test_trace_propagation.py` (à ne jamais désactiver,
  §5.3 Source B).
- Échantillonnage : 100% en dev (`dev.py`), 20% en prod avec conservation
  systématique des traces en erreur *(la conservation systématique des
  erreurs au sampler nécessite un exportateur tail-based, hors périmètre
  Sprint 0 — actuellement 20% head-based en prod, limitation documentée
  dans SPRINT_DECISIONS.md)*.

## Logs

- Une ligne JSON par entrée (`apps/core/observability/logging.py`,
  `JsonFormatter`).
- Champs obligatoires : `timestamp`, `level`, `logger`, `message`,
  `correlation_id`, `trace_id`, `span_id`, `user_id`, `service`, `env`,
  `version`.
- `SecretRedactor` masque récursivement toute clé matchant
  `password|token|secret|seed|key|authorization|card` (insensible à la
  casse, y compris imbriqué) — testé par `test_secret_redactor.py` et
  `test_security.py::test_no_secret_pattern_leaks_through_the_logging_pipeline_end_to_end`.

## Métriques

**RED** (par endpoint, `apps/core/observability/metrics.py`) :
`http_requests_total{method,route,status}`,
`http_request_duration_seconds{method,route}`, `http_requests_in_flight{route}`.

**USE** (par ressource) : `db_connections_active/max`,
`db_query_duration_seconds`, `redis_commands_total`, `redis_latency_seconds`,
`celery_queue_depth{queue}`, `celery_task_duration_seconds{task,status}`,
`process_cpu_seconds_total`, `process_resident_memory_bytes`.

**Métier** (structure posée au S0, alimentée par les sprints suivants —
**jamais de fausse valeur**, §64 master prompt) : `fanid_outbox_pending`,
`fanid_outbox_dead`, `fanid_idempotency_conflicts_total{reason}`,
`fanid_scan_total{result,reason}`, `fanid_purchase_total{status}`,
`fanid_stock_hold_active`, `fanid_totp_verification_total{result}`.

## Alertes définies (à câbler sur Alertmanager/Grafana au Sprint 5)

| Alerte | Condition | Gravité |
|---|---|---|
| Taux d'erreur élevé | `5xx > 1%` sur 5 min | Critique |
| Latence dégradée | `p95 > 2×` cible sur 10 min | Avertissement |
| Outbox bloqué | `fanid_outbox_pending > 100` pendant 5 min | **Critique — panne silencieuse** |
| Événements morts | `fanid_outbox_dead > 0` | **Critique** |
| File Celery saturée | `celery_queue_depth > 500` | Avertissement |
| Base saturée | connexions actives > 80% du max | Critique |

## Comment déboguer un incident avec ce socle

1. Récupérer le `correlation_id` affiché à l'utilisateur (écran `error`,
   §4.2 Source B) ou dans la réponse d'erreur (`error.correlation_id`).
2. Chercher ce `correlation_id` dans les logs (`docker compose logs api |
   grep <correlation_id>`) — toutes les lignes de la requête, y compris
   dans les tâches Celery déclenchées, le portent.
3. Utiliser le `trace_id` associé pour retrouver la trace distribuée
   complète (collecteur OTel → futur backend de traces, Sentry/Jaeger,
   Sprint 5).
