# SPRINT 0 — Statut

Légende : `TODO` / `IN PROGRESS` / `BLOCKED` / `DONE*` (code écrit et
cohérent, non exécuté dans l'environnement de génération — voir
`SPRINT_TEST_REPORT.md`) / `DONE` (exécuté et vérifié).

**Aucune tâche n'est marquée `DONE` sans exécution réelle — voir §76 master
prompt. Toutes les tâches ci-dessous sont `DONE*` au mieux.**

| Lot | Tâche | Statut |
|---|---|---|
| 1 | Mono-repo, `.gitignore`, pre-commit, `.importlinter` | DONE* |
| 2 | `docker-compose.yml` (8 services), Redis/Nginx/OTel/Prometheus conf, Dockerfile multi-stage, entrypoint | DONE* |
| 3 | Django core : settings base/dev/test/prod, ASGI/WSGI, urls, celery.py + propagation traceparent | DONE* |
| 4 | Modèles de base (UUID/TimeStamped/Versioned), contrat d'erreur, pagination | DONE* |
| 5 | 3 tables infra (idempotency_record, outbox_event, consumed_event) + migrations manuelles | DONE* |
| 6 | 6 ports + adaptateurs de test (Fake*/InMemory*/Recording*) | DONE* |
| 7 | Observabilité : CorrelationMiddleware, JSON logs + SecretRedactor, RED/USE metrics, OTel bootstrap | DONE* |
| 8 | Idempotence : service + middleware + tâche de purge + tests de concurrence | DONE* |
| 9 | Outbox : publisher + relay (SKIP LOCKED) + consumer + tâches Beat + tests de concurrence | DONE* |
| 10 | Endpoints `/health`, `/health/ready`, `/metrics`, `/schema`, `/swagger-ui/` | DONE* |
| 11 | Web : bootstrap React 19/TS strict/Vite/Tailwind, client Axios, TanStack Query, Zustand, 5 états d'écran | DONE* |
| 12 | Mobile : bootstrap Flutter Clean Architecture, Dio, Failure scellée, widgets d'état | DONE* |
| 13 | CI : 5 pipelines (`ci-backend`, `ci-web`, `ci-mobile`, `security`, `deploy`), 8 portes de qualité | DONE* |
| 14 | Sécurité : `.env.example` sans secret réel, `detect-secrets` baseline, headers prod, Bandit/pip-audit config | DONE* |
| 15 | Documentation : README, INSTALL, OBSERVABILITY, 8 ADR, traçabilité | DONE* |
| — | **Exécution réelle** (`docker compose up`, `pytest`, `npm test`, `flutter test`, CI) | **BLOCKED — sandbox sans réseau/Docker, voir SPRINT_TEST_REPORT.md** |

## Reste explicitement transmis (hors périmètre Sprint 0, §7.3 Source B)

- Environnement AWS complet et déploiement → Sprint 5.
- Grafana → Sprint 5 (ou coupé selon arbitrage final).
- Politique expand/contract exercée pour de vrai sur une table peuplée →
  Sprint 2.
- Circuit breaker branché sur un vrai service externe → Sprint 3.
- `PolicyEngine`, RBAC/ABAC, rotation de refresh token → Sprint 1.

## Correction post-bilan (note 72/100)

Un correctif complet a été appliqué suite au bilan externe du Sprint 0 —
voir `SPRINT0_CORRECTION_REPORT.md` pour le détail statut par statut du
plan P0/P1/P2. Résumé : tous les points corrigeables dans cet
environnement sont `DONE*` (corrigés, vérifiés statiquement, non exécutés
— même limitation réseau/Docker que le rapport initial) ; un seul point
reste `BLOQUÉ` (P0.A1, `web/package-lock.json`, nécessite `npm install` sur
une machine avec accès réseau) ; un point était déjà correct (P0.B3,
permissions `entrypoint.sh`, faux positif du relecteur externe).
