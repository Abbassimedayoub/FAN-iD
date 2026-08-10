# FAN id — Plateforme de billetterie sécurisée

Monolithe modulaire orienté domaine (Django/DRF/Channels/Celery + React 19 +
Flutter) livrant une billetterie à QR dynamique TOTP et contrôle d'accès
temps réel. Voir `docs/plan/` pour l'architecture complète et le plan de
développement par sprint.

**État actuel : Sprint 0 — Plateforme, chaîne de livraison et observabilité.**
Aucune fonctionnalité métier n'est implémentée à ce stade — voir
`docs/implementation/SPRINT_STATUS.md` pour le détail.

## Démarrage rapide

```bash
git clone <repository> && cd fanid
cp .env.example .env
docker compose up --build
```

Puis vérifier :

- API : http://localhost:8000/api/v1/health
- Readiness : http://localhost:8000/api/v1/health/ready
- Swagger : http://localhost:8000/swagger-ui/
- Métriques Prometheus : http://localhost:8000/metrics
- Nginx (edge) : http://localhost:8080/api/v1/health

Voir `INSTALL.md` pour le détail des prérequis, `docs/OBSERVABILITY.md` pour la
chaîne de traces/logs/métriques.

## Structure du dépôt

```
backend/    Django/DRF/Channels/Celery — bounded contexts sous apps/
web/        React 19 + TypeScript strict (dashboard organisateur/admin)
mobile/     Flutter — app Fan + mode Scanner
infra/      Nginx, collecteur OTel, monitoring, scripts
docs/       Plan de développement, ADR, runbooks, traçabilité Sprint 0
```

## Architecture

- **Monolithe modulaire DDD** (ADR-S-01) — bounded contexts en apps Django :
  `identity`, `organizing`, `catalog`, `ordering`, `payments`, `ticketing`,
  `access`, `notifying`, `realtime`, autour d'un noyau `core` indépendant.
- **Zero Trust** (ADR-S-04), **concurrence hybride** pessimiste/optimiste
  (ADR-S-05), **Transactional Outbox** au lieu d'un broker distribué
  (ADR-S-03), **observabilité de premier ordre** dès ce Sprint 0 (ADR-S-07).
- Détail complet et justifications : `docs/adr/ADR-S-01.md` à `ADR-S-08.md`.

## Limitation d'environnement de génération (transparence, voir rapport final)

Ce code a été écrit dans un environnement sandbox sans accès réseau à PyPI,
npm ou au daemon Docker — il n'a donc **pas** pu être installé ni exécuté
dans cet environnement. Il a été relu ligne à ligne pour la cohérence avec
Source A/B et vérifié syntaxiquement (`py_compile` sur 100% des fichiers
Python). Voir `docs/implementation/SPRINT_TEST_REPORT.md` pour le détail
exact de ce qui est prouvé vs. ce qui reste à exécuter sur une machine avec
accès réseau/Docker.
