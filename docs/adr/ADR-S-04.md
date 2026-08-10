# ADR-S-04 — Zero Trust appliqué à l'API

**Statut** : Accepté (Source A §1.5).

**Principe** : aucune requête n'est de confiance, même authentifiée, même
interne.

**Sept règles** :

1. Deny by default — `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES =
   ["IsAuthenticated"]` (voir `backend/config/settings/base.py`) ; ouvrir
   un endpoint est un acte explicite, revu en PR.
2. Authentifier **et** autoriser à chaque requête — aucune décision
   d'autorisation mise en cache côté client (implémenté par `PolicyEngine`,
   Sprint 1).
3. Périmètre déduit du serveur, jamais du client.
4. Moindre privilège (rôles à capacités minimales, IAM d'instance limité).
5. Secrets jamais en clair — SSM/KMS en prod, `EnvSecretProvider` en dev,
   `.env` dans `.gitignore` **avant le premier commit**, rédaction
   automatique dans les logs (`SecretRedactor`).
6. Tout accès sensible journalisé (login, scan, transfert, paiement,
   action admin — implémenté aux sprints correspondants).
7. Défense en profondeur — chaque invariant protégé à 2 niveaux minimum
   (SGBD + application), voir Source A §1.2.3 (I-1 à I-5).

**Implémentation Sprint 0** : règle 1 (permission par défaut), règle 5
(`EnvSecretProvider`/`FakeSecretProvider`, `.gitignore`, `SecretRedactor`,
`detect-secrets` en pre-commit + CI). Règles 2/3/4/6 nécessitent
`identity`/`PolicyEngine` (coquille posée, Sprint 1).
