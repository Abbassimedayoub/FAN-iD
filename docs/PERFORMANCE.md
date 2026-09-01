# PERFORMANCE.md — FAN id

> Placeholder Sprint 0 (§78 master prompt — arborescence `docs/` cible).
> Cibles de performance posées au Sprint 0 (Source B §5.2) ; mesures
> réelles à consigner ici à partir de l'exécution effective sur une
> machine avec Docker (voir `docs/implementation/SPRINT_TEST_REPORT.md`).

## Cibles définies au Sprint 0

| Élément | Cible | Vérification |
|---|---|---|
| Démarrage à froid de l'API | < 8 s | Mesure au démarrage du conteneur |
| `/api/v1/health` | < 20 ms | Test de charge léger |
| Durée de la CI backend | < 6 min | `ci-backend.yml` (cache pip, `pytest -n auto`) |
| Taille de l'image Docker (prod) | < 400 Mo | Vérifié par `.github/workflows/deploy.yml` |
| Surcharge de l'instrumentation OTel | < 5 % de latence | Comparaison avec/sans OTel sur `/health` |

## Mesures réelles

**Non renseignées** — nécessitent une exécution réelle de la stack
(bloquée dans l'environnement de génération de ce Sprint 0, voir
`docs/implementation/SPRINT_TEST_REPORT.md`). À compléter après le premier
`docker compose up` + `ab`/`k6` sur une machine avec Docker.

## Scénarios de charge prévus (Sprint 5)

Détail dans le plan de développement
(`plan-dev-v2/08-sprint-5-production.md`) : p95 scan < 300ms, 100 achats
concurrents → exactement 50 gagnants (contention réaliste sur `category`).
