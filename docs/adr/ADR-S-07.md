# ADR-S-07 — Observabilité de premier ordre, dès le Sprint 0

**Statut** : Accepté (Source A §1.5).

**Décision** : l'instrumentation est une exigence fonctionnelle livrée au
Sprint 0, pas une option de fin de projet.

**Trois piliers** : traces (OpenTelemetry, propagation W3C `traceparent`
jusque dans Celery et les consumers WebSocket), logs (JSON structuré,
`correlation_id` sur 100% des lignes, rédaction automatique), métriques
(RED par service, USE par ressource).

**Métriques métier obligatoires** : `fanid_scan_total{result,reason}`,
`fanid_scan_duration_seconds`, `fanid_purchase_total{status}`,
`fanid_stock_hold_active`, `fanid_outbox_pending`, `fanid_outbox_dead`,
`fanid_totp_verification_total{result}`.

**Justification** : `fanid_outbox_pending` qui croît sans redescendre est
le signal d'un relais arrêté — panne silencieuse, sans erreur HTTP, que
seule une métrique métier révèle.

**Implémentation Sprint 0** : voir `OBSERVABILITY.md` pour la chaîne
complète. Point technique critique validé par un test dédié :
`apps/core/tests/test_trace_propagation.py` (propagation du traceparent à
travers Celery — coefficient ×2 justifié sur ce bloc, Source B §2.4).
