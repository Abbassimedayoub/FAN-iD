# SECURITY.md — FAN id

> Placeholder Sprint 0 (§78 master prompt — arborescence `docs/` cible).
> Contenu complet livré progressivement à mesure que les mécanismes de
> sécurité sont implémentés (Sprint 1 : Zero Trust/RBAC-ABAC ; Sprint 3 :
> paiement/TOTP ; Sprint 5 : audit OWASP complet).

## Déjà en place au Sprint 0

- **Secrets** : port `SecretProvider` (`EnvSecretProvider` en dev,
  `SsmSecretProvider` prévu en prod), `.env` exclu de Git avant le premier
  commit, `detect-secrets` bloquant en CI (`.github/workflows/security.yml`,
  `.github/workflows/ci-backend.yml`) — voir `docs/adr/ADR-S-04.md`.
- **Rédaction des logs** : `apps/core/observability/logging.SecretRedactor`
  masque récursivement tout champ `password|token|secret|seed|key|
  authorization|card` — voir `docs/OBSERVABILITY.md`.
- **Masquage des erreurs d'infrastructure** : `/api/v1/health/ready` ne
  renvoie jamais le texte brut d'une exception au client (P1.B.2, voir
  `apps/core/views.py`) — l'exception complète est journalisée côté
  serveur uniquement.
- **En-têtes de sécurité production** : HSTS, `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy` — voir
  `backend/config/settings/prod.py` et son test
  `apps/core/tests/test_security.py`.
- **Analyse statique** : Bandit, `pip-audit`, `npm audit`, `detect-secrets`
  — bloquants en CI, sans bypass (`.github/workflows/security.yml`).

## Politique de signalement (à compléter — Sprint 1)

Canal de signalement responsable, SLA de correction par sévérité,
processus de disclosure : à définir avant l'ouverture publique du dépôt.

## OWASP Top 10 — suivi (à compléter — Sprint 5)

Checklist complète et preuve de couverture par item, voir
`plan-dev-v2/08-sprint-5-production.md` (projet).
