# GDPR.md — FAN id

> Placeholder Sprint 0 (§78 master prompt — arborescence `docs/` cible).
> Le Sprint 0 ne traite aucune donnée personnelle métier (aucune table
> métier créée, §44 master prompt) — ce document sera rempli à partir du
> Sprint 1 (identité : premières données personnelles réelles).

## Portée prévue (à compléter)

- Registre des traitements (données collectées par bounded context : email,
  nom, téléphone si applicable, données de paiement — jamais stockées en
  clair, sous-traitées à Stripe).
- Base légale par traitement (exécution du contrat pour l'achat de billets,
  consentement pour les communications marketing).
- Durées de conservation par table (déjà posées au niveau infrastructure :
  `idempotency_record` 24h, `outbox_event` publiés purgés à 30 jours — voir
  `docs/adr/ADR-S-03.md`, `ADR-S-06.md`).
- Procédure d'anonymisation/suppression sur demande (droit à l'effacement) —
  spécifiée dans le plan de développement, Sprint 5
  (`plan-dev-v2/08-sprint-5-production.md`, algorithme d'anonymisation).
- Sous-traitants (Stripe, AWS SES, hébergeur AWS) et transferts hors UE le
  cas échéant.
- DPO / point de contact.

## État Sprint 0

Aucune donnée personnelle traitée — coquilles de bounded contexts vides,
aucune table métier (§44/§80 master prompt).
