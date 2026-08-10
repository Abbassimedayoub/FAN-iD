# ADR-S-01 — Monolithe modulaire orienté domaine (DDD stratégique)

**Statut** : Accepté (Source A §1.5).

**Contexte** : 1 développeur, ~3 mois, cohérence transactionnelle forte
requise sur les invariants I-1 à I-5 (achat, scan, paiement).

**Options considérées** : (A) monolithe en couches techniques globales,
(B) monolithe modulaire par bounded context, (C) microservices.

**Décision** : B. Les invariants exigent des transactions ACID sur
plusieurs agrégats (catégorie + commande + billet) ; en microservices il
faudrait des sagas compensatoires pour chaque achat — complexité ×5 pour un
bénéfice nul à cette échelle.

**Bounded contexts** : `identity`, `organizing`, `catalog`, `ordering`,
`payments`, `ticketing`, `access`, `notifying`, `realtime`, autour d'un
noyau `core` qui ne dépend d'aucun d'eux (vérifié par `import-linter`,
voir `.importlinter` et `.github/workflows/ci-backend.yml`).

**Conséquences** : frontières explicites, extraction future possible ;
tests isolables par contexte ; discipline requise, outillée par
`import-linter` plutôt que laissée à la seule revue de code.

**Implémentation Sprint 0** : structure `backend/apps/{core,identity,
organizing,catalog,ordering,payments,ticketing,access,notifying,realtime}/`,
contrat `.importlinter` avec contrat `core-is-independent` (forbidden) et
`contexts-are-independent` (independence) — voir `.importlinter`.
