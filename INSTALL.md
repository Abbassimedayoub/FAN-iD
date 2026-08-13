# Installation — FAN id (Sprint 0)

## Prérequis

| Outil | Version | Vérification |
|---|---|---|
| Docker + Docker Compose | Docker 24+/Compose v2 | `docker compose version` |
| Python | 3.12 | `python3.12 --version` (pour le dev hors Docker uniquement) |
| Node.js | 20 | `node --version` |
| Flutter SDK | 3.24.x stable | `flutter --version` |

Aucun compte AWS n'est requis pour le développement local du Sprint 0 —
`SECRET_PROVIDER=env` (voir `.env.example`) utilise `EnvSecretProvider`.

## 1. Cloner et configurer

```bash
git clone <repository> && cd fanid
cp .env.example .env
```

Ouvrir `.env` et ajuster `DJANGO_SECRET_KEY` si besoin (une valeur de
développement est déjà présente — **ne jamais utiliser cette valeur en
production**, voir `docs/adr/ADR-S-04.md`).

## 2. Démarrer la stack (8 services)

```bash
docker compose up --build
```

Services démarrés : `postgres`, `redis`, `api`, `ws`, `worker`, `beat`,
`nginx`, `otel-collector`. `api`/`ws`/`worker`/`beat` partagent la même
image (voir `backend/Dockerfile`, stage `dev`) mais des rôles différents
via `backend/docker/entrypoint.sh`.

## 3. Vérifier

```bash
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
curl -s http://localhost:8000/api/v1/health/ready | python3 -m json.tool
curl -s http://localhost:8000/metrics | head -20
open http://localhost:8000/swagger-ui/
```

## 4. Développement backend hors Docker (optionnel)

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp ../.env.example ../.env   # DATABASE_URL/REDIS_URL doivent alors pointer vers localhost
python manage.py migrate
python manage.py runserver
```

## 5. Tests

> **Hors Docker**, la suite exige que `DATABASE_URL`/`REDIS_URL` pointent vers
> `localhost` sur les ports publiés par le compose — les noms d'hôtes Docker du
> `.env` ne résolvent pas depuis la machine hôte :
>
> ```bash
> docker compose up -d postgres redis
> cp .env.local.example .env.local && set -a && . ./.env.local && set +a
> ```

```bash
cd backend
pytest                       # unitaires + intégration + concurrence, couverture >= 80% sur core
pytest apps/core/tests/test_trace_propagation.py -v   # test critique de propagation de trace
lint-imports                 # contrats d'architecture (import-linter)
black --check . && isort --check-only . && flake8 .
mypy apps/core
bandit -r apps config -ll
```

## 6. Frontend web (hors Docker au Sprint 0)

```bash
cd web
cp .env.example .env
npm install
npm run dev        # http://localhost:5173
npm run lint && npm run typecheck && npm run test -- --run
```

## 7. Mobile

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

## Cas limites documentés (§63 master prompt)

| Cas | Comportement attendu |
|---|---|
| `api` démarre avant que `postgres` soit prêt | `depends_on: condition: service_healthy` bloque le démarrage d'`api` jusqu'au healthcheck Postgres |
| Variable d'environnement critique manquante | `entrypoint.sh` refuse de démarrer avec un message explicite (`DJANGO_SECRET_KEY manquant`) |
| Redis indisponible au démarrage | `/api/v1/health/ready` renvoie `200` avec `status: degraded` (Redis n'est pas critique pour la liveness) |
| Deux relais Outbox concurrents | Aucun doublon — `SELECT FOR UPDATE SKIP LOCKED`, voir `apps/core/outbox/relay.py` et son test de concurrence |

## Limitation connue de cet environnement de génération

Voir `README.md` § « Limitation d'environnement de génération » et
`docs/implementation/SPRINT_TEST_REPORT.md`.
