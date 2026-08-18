# ADR-S-02 — CQRS léger (séparation des modèles de lecture, pas des bases)

**Statut** : Accepté (Source A §1.5).

**Options** : (A) aucun CQRS, (B) séparation lecture/écriture dans le même
stockage, (C) CQRS complet avec bases séparées et projections asynchrones.

**Décision** : B, avec une exception ciblée en C pour les métriques
temps réel (`event_metrics_snapshot`, alimentée par Outbox — Sprint 4).

**Justification** : une base unique absorbe largement les profils de
lecture/écriture opposés à cette volumétrie ; C introduirait une
cohérence à terme sur des données que l'utilisateur attend immédiates
(« j'ai acheté, où est mon billet ? »).

**Mise en œuvre (posée au Sprint 0, exercée à partir du Sprint 2)** :
`services/` (écriture, invariants, transactions) vs `selectors.py`
(lecture, aucun effet de bord) dans chaque bounded context ; serializers de
lecture ≠ serializers d'écriture.

**Sprint 0** : aucun contexte métier n'a encore de `services/`/`selectors.py`
(coquilles vides, §80 master prompt) — cet ADR fige la convention que les
sprints suivants doivent respecter dès leur premier commit.
