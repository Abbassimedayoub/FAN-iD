# ADR-S-08 — Migrations Django avec politique expand/contract

**Statut** : Accepté — remplace Flyway/Liquibase (recommandation refusée
de l'audit critique, Source A §1.1.2.A : outils JVM incompatibles avec la
stack Django imposée par le dossier d'architecture).

**Règles opposables en PR** :
- `sqlmigrate` joint à toute migration touchant une table > 10 000 lignes.
- Index créés en `CONCURRENTLY` (`atomic = False`) — un `CREATE INDEX`
  classique verrouille la table en écriture.
- Aucun `NOT NULL` sans valeur par défaut sur table peuplée.
- Backfill par lots dans une migration séparée, jamais dans la même que
  l'ajout de colonne.
- Réversibilité obligatoire (`RunPython(forward, reverse)`).
- `django-migration-linter` bloquant en CI (voir
  `.github/workflows/ci-backend.yml`).

**Implémentation Sprint 0** : `apps/core/migrations/0001_infrastructure.py`
et `apps/identity/migrations/0001_initial.py` — écrites à la main dans cet
environnement (pas d'accès réseau pour installer Django et faire tourner
`makemigrations`, voir `docs/implementation/SPRINT_TEST_REPORT.md`). À
valider par un `makemigrations --check --dry-run` réel avant le premier
merge — c'est précisément la porte que `ci-backend.yml` fait passer.
