# ADR-S-03 — Event-Driven interne via Transactional Outbox

**Statut** : Accepté — remplace la recommandation Kafka/SQS-SNS de l'audit
critique (Source A §1.1.2.B).

**Justification du refus de Kafka/SQS en V1** : déploiement cible = un EC2
unique ; Kafka exige un cluster (coût opérationnel > coût de toute
l'application) ; le volume réel (quelques milliers d'événements/match) est
3 à 6 ordres de grandeur sous ce pour quoi Kafka est dimensionné.

**Décision** : pattern Outbox — écriture de l'événement dans la même
transaction que la donnée métier, relais Celery Beat (`SELECT ... FOR
UPDATE SKIP LOCKED`), port `EventPublisher` comme point d'extension vers
un broker distribué en V2 sans refonte.

**Contrat d'événement (stable, versionné)** :
```
{ event_id, event_type, event_version, aggregate_type, aggregate_id,
  occurred_at, correlation_id, causation_id, actor_id, payload{...} }
```

**Garanties** : atomicité producteur/événement (même transaction),
*at-least-once*, ordre par agrégat (`aggregate_type, aggregate_id,
sequence`), retry exponentiel (2s, 8s, 32s, 2min, 8min) puis `DEAD` après 5
tentatives + alerte, consommateurs obligatoirement idempotents
(`consumed_event(consumer_name, event_id)` en PK composite).

**Implémentation Sprint 0** : `apps/core/outbox/{models,publisher,relay,
consumer,tasks}.py`, tables `outbox_event`/`consumed_event`
(`apps/core/migrations/0001_infrastructure.py`), tests de concurrence
(`apps/core/tests/test_outbox.py` : rollback ⇒ aucun événement, deux
relais concurrents ⇒ aucun doublon, 5 échecs ⇒ `DEAD`).

**Correction post-bilan (P1.C.1)** : `relay_batch()` tient les verrous
`SELECT FOR UPDATE SKIP LOCKED` pour la durée de tout le lot — un
consumer qui ferait un appel réseau direct dans `handle()` tiendrait ces
verrous pendant la latence réseau (même risque que §24 master prompt,
appliqué au relais). `BaseConsumer.defer(callback)` (`transaction.
on_commit`) est désormais l'unique mécanisme sanctionné pour tout effet
de bord réseau d'un consumer — testé par
`apps/core/tests/test_outbox_consumer_contract.py` (le callback ne
s'exécute qu'après le commit, jamais après un rollback).
