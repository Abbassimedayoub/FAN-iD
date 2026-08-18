# docs/plan/ — Sources de vérité du plan de développement

Ce dossier rend le dépôt **auto-suffisant** (§78 master prompt : un
développeur qui n'a jamais ouvert le projet doit pouvoir comprendre les
décisions d'architecture sans accès à un outil externe).

- [`SOURCE-A-architecture.md`](./SOURCE-A-architecture.md) — Section 1 du
  plan de développement v2 : réponse à l'audit critique, C4 (contexte,
  conteneurs, composants, flux de référence), les 8 ADR stratégiques
  (ADR-S-01 à ADR-S-08). Référencée comme **« Source A »** dans le master
  prompt d'implémentation du Sprint 0 et dans `docs/adr/`.
- [`SOURCE-B-sprint0.md`](./SOURCE-B-sprint0.md) — spécification
  opérationnelle complète du Sprint 0 (périmètre, architecture technique,
  spec backend/frontend, sécurité/performance/observabilité, stratégie de
  test, livrables et checklist qualité). Référencée comme **« Source B »**.

Le reste du plan de développement (Sprints 1 à 5, roadmap réévaluée,
annexes/registres) vit dans le projet Claude source (`plan-dev-v2/`) et
n'est pas dupliqué ici tant que ces sprints n'ont pas démarré — il sera
copié dans ce dossier au démarrage de chacun, selon le même principe.

## Hiérarchie des sources (rappel, §3 master prompt)

1. Décision explicite de `SOURCE-A-architecture.md`.
2. Exigence explicite de `SOURCE-B-sprint0.md`.
3. ADR accepté (`docs/adr/`).
4. Règle explicite d'un fichier d'instructions agent (`CLAUDE.md`,
   `.github/copilot-instructions.md` — aucun présent à ce jour).
5. Code existant / conventions du repository.
6. Connaissance générale d'ingénierie.

Toute divergence entre le code et ces documents doit être traitée comme une
régression et documentée dans `docs/implementation/SPRINT_DECISIONS.md`.
