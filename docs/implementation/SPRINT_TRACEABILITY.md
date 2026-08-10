# SPRINT 0 — Matrice de traçabilité

Format (§67 master prompt) : ID exigence → Source → Tâche → Fichiers →
Test → Commande → Résultat. `Résultat = NON EXÉCUTÉ (sandbox)` partout où
l'exécution réelle n'a pas pu avoir lieu — voir `SPRINT_TEST_REPORT.md`.

| ID | Source | Exigence | Fichiers | Test | Commande | Résultat |
|---|---|---|---|---|---|---|
| S0-REPO-001 | §14 master prompt | Structure monorepo cible | `backend/`, `web/`, `mobile/`, `infra/`, `docs/` | — (structurel) | `find . -maxdepth 2 -type d` | Vérifié (structure créée) |
| S0-REPO-002 | §40/§41 | `.env` jamais commité, secrets hors Git | `.gitignore`, `.env.example` | `test_dev_env_example_never_contains_a_real_looking_secret` | `pytest apps/core/tests/test_security.py` | NON EXÉCUTÉ (sandbox) |
| S0-MODEL-001 | §16 / §2.2 Source B | `UUIDModel` : PK UUID v4 | `apps/core/models.py` | `test_uuid_model_generates_uuid4_pk` | `pytest apps/core/tests/test_models.py` | NON EXÉCUTÉ (sandbox) |
| S0-MODEL-002 | §16 | `VersionedModel` : verrouillage optimiste | `apps/core/models.py` | `test_versioned_model_save_uses_f_expression_when_updating` | idem | NON EXÉCUTÉ (sandbox) |
| S0-ERR-001 | §17 / §3.3 Source B | Contrat d'erreur gelé (code/message/details/correlation_id/trace_id) | `apps/core/exceptions.py`, `handlers.py` | `test_business_error_produces_frozen_error_contract` (paramétré ×8) | `pytest apps/core/tests/test_exceptions_and_handlers.py` | NON EXÉCUTÉ (sandbox) |
| S0-ERR-002 | §17 | 5xx n'expose jamais de détail technique | `handlers.py` | `test_unhandled_exception_returns_500_without_technical_detail` | idem | NON EXÉCUTÉ (sandbox) |
| S0-PAG-001 | §18 | Pagination standard + curseur stable | `apps/core/pagination.py` | `test_cursor_pagination_orders_on_created_at_then_id_for_stability` | `pytest apps/core/tests/test_pagination.py` | NON EXÉCUTÉ (sandbox) |
| S0-PORT-001..006 | §19 / §2.3 Source B | 6 ports (Secret/Event/Payment/Notification/Storage/DeviceLock) | `apps/core/interfaces/*.py`, `apps/core/adapters/*.py` | import + instanciation des adaptateurs Fake/InMemory/Recording | — | Compilation syntaxique vérifiée (`py_compile`), exécution NON FAITE |
| S0-IDEMP-001 | §20 / §3.1 Source B | Table `idempotency_record`, `UNIQUE(key,user_id)` | `apps/core/idempotency/models.py`, migration | schéma en migration manuelle | `python manage.py migrate` | NON EXÉCUTÉ (sandbox) |
| S0-IDEMP-002 | §20 / §57 | 5 requêtes concurrentes même clé ⇒ 1 exécution | `apps/core/idempotency/service.py` | `test_five_concurrent_requests_same_key_yield_one_execution` | `pytest apps/core/tests/test_idempotency.py -v` | NON EXÉCUTÉ (sandbox — nécessite PostgreSQL réel) |
| S0-IDEMP-003 | §20 | Même clé, corps différent ⇒ 422 | idem | `test_same_key_different_body_is_rejected` | idem | NON EXÉCUTÉ (sandbox) |
| S0-IDEMP-004 | §20 | Enregistrement orphelin repris après délai de garde | idem | `test_orphaned_in_progress_record_is_recovered_after_guard_delay` | idem | NON EXÉCUTÉ (sandbox) |
| S0-IDEMP-005 | §33 | Middleware après authentification, clé scopée par utilisateur | `apps/core/idempotency/middleware.py`, `config/settings/base.py` (ordre `MIDDLEWARE`) | `test_key_is_scoped_per_user_not_global` | idem | NON EXÉCUTÉ (sandbox) |
| S0-OUTBOX-001 | §21 / §3.1 Source B | Table `outbox_event`, index partiel relais | `apps/core/outbox/models.py`, migration | schéma en migration manuelle | `python manage.py migrate` | NON EXÉCUTÉ (sandbox) |
| S0-OUTBOX-002 | §23 / §58 | Rollback transaction ⇒ aucun événement | `apps/core/outbox/publisher.py` | `test_rolled_back_transaction_publishes_no_event` | `pytest apps/core/tests/test_outbox.py -v` | NON EXÉCUTÉ (sandbox) |
| S0-OUTBOX-003 | §21 / §58 | 2 relais concurrents ⇒ aucun doublon (SKIP LOCKED) | `apps/core/outbox/relay.py` | `test_two_concurrent_relays_never_process_same_event_twice` | idem | NON EXÉCUTÉ (sandbox — nécessite PostgreSQL réel) |
| S0-OUTBOX-004 | §21 | 5 échecs ⇒ DEAD + métrique | `apps/core/outbox/relay.py`, `observability/metrics.py` | `test_event_failing_five_times_becomes_dead` | idem | NON EXÉCUTÉ (sandbox) |
| S0-OUTBOX-005 | §22 | `consumed_event` PK composite = déduplication | `apps/core/outbox/consumer.py` | `test_consumed_event_primary_key_deduplicates` | idem | NON EXÉCUTÉ (sandbox) |
| S0-OBS-001 | §26 / §2.5 Source B | `CorrelationMiddleware` génère/propage, jamais 2 IDs | `apps/core/observability/middleware.py` | `test_generates_correlation_id_when_absent`, `test_propagates_incoming_correlation_id`, `test_never_produces_two_different_ids_for_same_request` | `pytest apps/core/tests/test_correlation_middleware.py` | NON EXÉCUTÉ (sandbox) |
| S0-OBS-002 | §27 / §2.4 Source B | Propagation traceparent HTTP → Celery, une seule trace | `backend/config/celery.py` | `test_http_request_and_celery_task_share_one_trace` | `pytest apps/core/tests/test_trace_propagation.py -v` | NON EXÉCUTÉ (sandbox) — **test critique** |
| S0-OBS-003 | §28 | Rédaction automatique des secrets dans les logs | `apps/core/observability/logging.py` | `test_redacts_*` (×5), `test_no_secret_pattern_leaks_through_the_logging_pipeline_end_to_end` | `pytest apps/core/tests/test_secret_redactor.py apps/core/tests/test_security.py` | NON EXÉCUTÉ (sandbox) |
| S0-OBS-004 | §29/§30/§31 | Métriques RED/USE/métier déclarées, jamais alimentées artificiellement | `apps/core/observability/metrics.py` | inspection manuelle (aucun `.inc()`/`.set()` hors code métier réel) | `grep -rn "\.inc()\|\.set(" apps/core` | Vérifié par lecture — aucune valeur factice |
| S0-HEALTH-001 | §35/§36 / §3.2 Source B | `/health` ne dépend d'aucune dépendance | `apps/core/views.py` | `test_health_liveness_never_touches_database` | `pytest apps/core/tests/test_health.py` | NON EXÉCUTÉ (sandbox) |
| S0-HEALTH-002 | §36 | DB down ⇒ 503 ; Celery down ⇒ 200 degraded | idem | `test_readiness_returns_503_when_database_down`, `test_readiness_degraded_when_celery_down_but_db_up` | idem | NON EXÉCUTÉ (sandbox) |
| S0-SCHEMA-001 | §37 | `/api/v1/schema/`, `/swagger-ui/` exposés (dev) | `backend/config/urls.py`, `SPECTACULAR_SETTINGS` | — | `curl localhost:8000/swagger-ui/` | NON EXÉCUTÉ (sandbox) |
| S0-DOCKER-001 | §38/§39 / §2.1 Source B | 8 services, healthchecks, `depends_on: service_healthy` | `docker-compose.yml` | `docker compose config` (validation syntaxique) | `docker compose up` | NON EXÉCUTÉ (sandbox — pas de daemon Docker) |
| S0-CI-001..008 | §52/§53 / §6.2 Source B | 8 portes de qualité bloquantes | `.github/workflows/ci-backend.yml` | — | push PR réel sur GitHub | NON EXÉCUTÉ (sandbox — pas d'accès GitHub Actions) |
| S0-ARCH-001 | §61 / ADR-S-01 | `core` indépendant, pas de dépendance circulaire | `.importlinter` | — | `lint-imports` | NON EXÉCUTÉ (sandbox — import-linter non installable) |
| S0-WEB-001 | §49 / §4.2-4.3 Source B | 5 états d'écran implémentés et exercés | `web/src/components/{Skeleton,EmptyState,ErrorState,RetryButton}.tsx`, `web/src/app/App.tsx` | `errors.test.ts` (classification) | `npm run test -- --run` | NON EXÉCUTÉ (sandbox — npm registry bloqué) |
| S0-WEB-002 | §47 | TanStack Query : staleTime 30s, retry≠4xx | `web/src/lib/queryClient.ts` | inspection + `errors.test.ts` | idem | NON EXÉCUTÉ (sandbox) |
| S0-MOBILE-001 | §50/§56 | Clean Architecture, `Failure` scellée, mapping d'erreurs | `mobile/lib/core/errors/failure.dart`, `dio_client.dart` | `mobile/test/core/dio_client_test.dart` | `flutter test` | NON EXÉCUTÉ (sandbox — Flutter non installé) |

## Synthèse

- **Fichiers produits** : conformes à Source A/B, relus ligne à ligne,
  100% syntaxiquement valides (`py_compile` sur tout `backend/`).
- **Exécution réelle** : **0 test exécuté** dans cet environnement — voir
  `SPRINT_TEST_REPORT.md` pour la cause exacte et la commande à lancer sur
  une machine avec accès réseau/Docker pour obtenir la preuve d'exécution.
