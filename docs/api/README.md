# docs/api/ — Documentation API générée

> Placeholder Sprint 0 (§78 master prompt — arborescence `docs/` cible ;
> correction P2.1 du bilan Sprint 0).

Aucun endpoint métier n'existe encore au Sprint 0 (§44/§80 master prompt).
Ce dossier accueillera, à partir du Sprint 1 :

- l'export figé du schéma OpenAPI 3 exposé par `/api/v1/schema/` (voir
  `docs/plan/SOURCE-B-sprint0.md` §3.2) à chaque tag de version ;
- la documentation Swagger/Redoc statique générée en CI pour archivage,
  indépendamment de l'instance en ligne.

## Déjà disponible au Sprint 0

- Le schéma OpenAPI est servi dynamiquement par l'API elle-même :
  `GET /api/v1/schema/` et `GET /swagger-ui/` (voir
  `backend/apps/core/urls.py` et `docs/plan/SOURCE-B-sprint0.md` §3.2).
- Le contrat d'erreur normalisé, gelé au Sprint 0, est documenté dans
  `docs/plan/SOURCE-B-sprint0.md` §3.3.

Aucun endpoint métier ⇒ aucun export figé à committer pour l'instant.
