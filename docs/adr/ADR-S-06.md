# ADR-S-06 — Idempotence de toutes les mutations sensibles

**Statut** : Accepté (Source A §1.5).

**Portée (sprints suivants)** : `POST /tickets/purchase`, `POST
/tickets/transfer`, `POST /transfers/{token}/accept`, `POST
/orders/{id}/cancel`, `POST /payments/webhook`, `POST /scan/validate`.

**Mécanisme** : en-tête `Idempotency-Key` (UUID v4 client) → table
`idempotency_record(key, user_id, endpoint, request_hash, status,
response_body, response_status, created_at, expires_at)` avec
`UNIQUE(key, user_id)`.

**Règles fines** — le quadruplet **(user, key, endpoint, request_hash)** est
validé explicitement, pas seulement (user, key) :
- même clé sur un **endpoint différent** (même si le hash coïncide) ⇒
  `422 IDEMPOTENCY_KEY_REUSE` — vérifié en tout premier, avant toute
  logique par statut, pour empêcher qu'une réponse d'un endpoint soit
  rejouée sur un autre (correction post-bilan Sprint 0, P1.A.1).
- même clé + même endpoint + même empreinte ⇒ réponse mémorisée rejouée,
  y compris un sous-ensemble whitelisté d'en-têtes clés (`Content-Type`,
  `Location`, `Retry-After` — jamais `Set-Cookie` ni `X-Correlation-ID`,
  P1.A.2).
- même clé + même endpoint + empreinte **différente** ⇒ `422 IDEMPOTENCY_KEY_REUSE`.
- exécution en cours ⇒ `409 REQUEST_IN_PROGRESS`.
- exécution orpheline (processus tué, `locked_at` + 60s dépassé) ⇒ reprise
  avec log `WARNING`.
- rétention 24h, purge quotidienne (Celery Beat).

**Implémentation Sprint 0** : `apps/core/idempotency/{models,service,
middleware,tasks}.py`, positionné dans `MIDDLEWARE` **après**
`AuthenticationMiddleware` (la clé est scopée par utilisateur — voir
`backend/config/settings/base.py` et le commentaire dans
`middleware.py`), tests de concurrence complets
(`apps/core/tests/test_idempotency.py`).
