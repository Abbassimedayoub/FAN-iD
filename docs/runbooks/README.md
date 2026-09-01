# docs/runbooks/ — Procédures opérationnelles

> Placeholder Sprint 0 (§78 master prompt — arborescence `docs/` cible ;
> correction P2.1 du bilan Sprint 0).

Aucune procédure de production n'est encore nécessaire au Sprint 0 (aucun
déploiement réel, voir `docs/plan/SOURCE-B-sprint0.md` §7.3 — l'environnement
AWS complet est transmis au Sprint 5). Ce dossier accueillera :

- la procédure de démarrage/arrêt propre de la stack (`docker compose up`
  / `down`, ordre des dépendances — voir déjà `README.md` et
  `docs/plan/SOURCE-B-sprint0.md` §6.3 pour les cas limites couverts) ;
- la procédure de reprise d'un enregistrement `idempotency_record` orphelin
  (déjà spécifiée dans `docs/adr/ADR-S-06.md`, à transformer en runbook
  opérationnel dès qu'un incident réel doit être traité en production) ;
- la procédure de purge/relance du relais Outbox en cas de blocage
  (`fanid_outbox_pending` qui ne redescend pas — voir
  `docs/adr/ADR-S-03.md` et `docs/adr/ADR-S-07.md`) ;
- la procédure de rotation des secrets SSM/KMS (Sprint 0 §5.1) ;
- les procédures de bascule et de rollback de déploiement (Sprint 5).

## Déjà en place au Sprint 0

Les cas limites d'infrastructure couverts par la CI et les tests (démarrage
avant PostgreSQL, variable d'environnement manquante, Redis indisponible au
démarrage, disque plein par les logs) sont documentés dans
`docs/plan/SOURCE-B-sprint0.md` §6.3 — ils ne nécessitent pas encore de
runbook manuel, la reprise étant automatique (healthchecks, retries).
