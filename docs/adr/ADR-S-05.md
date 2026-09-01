# ADR-S-05 — Contrôle de concurrence hybride

**Statut** : Accepté — corrige la recommandation « optimistic locking
partout » de l'audit critique (Source A §1.1.2.C).

**Problème technique** : sur une ressource à très forte contention (une
`category` qui se vend en quelques secondes), le verrouillage optimiste
provoque un taux d'échec proche de 99% sous 100 acheteurs simultanés
(*livelock*). Le verrouillage pessimiste (`SELECT FOR UPDATE`) sérialise et
réussit en quelques millisecondes.

**Décision** — un mécanisme par profil de contention :

| Ressource | Contention | Mécanisme |
|---|---|---|
| `category` (achat) | Très élevée | Pessimiste `SELECT FOR UPDATE` + `CHECK(sold_count<=quota)` |
| `ticket` (scan) | Élevée | Pessimiste `SELECT FOR UPDATE` |
| `event`/`category` (édition) | Faible | Optimiste `version` + `If-Match` ⇒ `409 STALE_RESOURCE` |
| `product.stock_level` | Moyenne | Pessimiste à l'achat, optimiste à l'édition |
| `organizer.validation_status` | Très faible | Optimiste |

**Implémentation Sprint 0** : `apps/core/models.VersionedModel` (compteur
`version`, incrément via `F("version")+1` — voir tests
`apps/core/tests/test_models.py`). Le `SELECT FOR UPDATE` pessimiste et le
`409 STALE_RESOURCE`/`412` complets sont exercés à partir du Sprint 2
(première ressource optimiste réelle) — le Sprint 0 pose l'infrastructure
d'erreur (`ConflictError`, `StaleResourceError`, `PreconditionFailed` dans
`apps/core/exceptions.py`) sans encore de scénario métier.
