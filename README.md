# FAN id

Secure ticketing and access-control platform built around strong identity, device binding, dynamic QR codes, and real-time validation.

FAN id is a modular monolith combining Django/DRF/Channels/Celery, React 19 + TypeScript, Flutter, PostgreSQL, Redis, Nginx, and OpenTelemetry.

Architecture decisions, implementation plans, sprint documentation, and operational notes are available under `docs/`.

## Current status

The platform foundation is in place and the first mobile authentication milestone is complete.

### Mobile authentication

The Flutter application currently includes:

- authentication bootstrap and session restoration
- refresh-token based session recovery
- secure token storage
- device fingerprint generation and persistence
- login and registration
- minimum-age and terms-acceptance validation
- device-lock handling
- device-reset request and OTP confirmation
- return to login after a successful device reset
- session-expiration notification
- Riverpod-based authentication state management
- safe mapping of backend failures to user-facing messages

Current authentication entry flow:

```text
Splash
  |
  +--> Login
        |
        +--> Register
        |
        +--> Device Locked
                |
                +--> Reset Request
                        |
                        +--> Reset Confirmation
                                |
                                +--> Login
```

No placeholder authenticated home screen is introduced yet. The authenticated destination will be connected when the corresponding product feature is ready.

### Mobile quality status

Latest validated mobile state:

- 145 Flutter tests passing
- `flutter analyze` clean
- mobile coverage: 99.90%
- coverage quality gate passing

## Repository structure

```text
backend/    Django / DRF / Channels / Celery modular backend
web/        React 19 + TypeScript web application
mobile/     Flutter mobile application
infra/      Nginx, OpenTelemetry, monitoring, and infrastructure configuration
docs/       Architecture, ADRs, sprint plans, reports, and runbooks
scripts/    Repository quality and automation scripts
```

## Architecture

FAN id follows a modular-monolith architecture organized around domain bounded contexts such as `identity`, `organizing`, `catalog`, `ordering`, `payments`, `ticketing`, `access`, `notifying`, and `realtime`, with shared infrastructure under `core`.

Key principles include Domain-Driven Design, Zero Trust security, explicit application boundaries, transactional outbox, idempotent operations, concurrency control, structured observability, and secure device binding.

Architecture decisions are documented under `docs/adr/`.

## Requirements

| Tool | Version |
| --- | --- |
| Docker | 24+ |
| Docker Compose | v2 |
| Python | 3.12 |
| Node.js | 20 |
| Flutter | 3.24.x stable |

## Quick start

```bash
git clone <repository-url>
cd FAN-iD
cp .env.example .env
docker compose up --build
```

Useful endpoints:

```text
API health       http://localhost:8000/api/v1/health
API readiness    http://localhost:8000/api/v1/health/ready
Swagger UI       http://localhost:8000/swagger-ui/
Prometheus       http://localhost:8000/metrics
Nginx health     http://localhost:8080/api/v1/health
```

The local Docker Compose configuration may use remapped host ports to avoid conflicts with services already running on the development machine.

## Backend

For local backend development outside Docker:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver
```

Quality checks:

```bash
pytest
lint-imports
black --check .
isort --check-only .
flake8 .
mypy apps/core
bandit -r apps config -ll
```

Some test groups require PostgreSQL and Redis to be available.

## Web

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

Quality checks:

```bash
npm run lint
npm run typecheck
npm run test -- --run
```

## Mobile

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

For reproducible validation with Flutter 3.24.5:

```bash
docker run --rm \
  -v "$PWD/mobile:/source:ro" \
  ghcr.io/cirruslabs/flutter:3.24.5 \
  sh -lc '
    cp -R /source /tmp/mobile
    cd /tmp/mobile
    flutter pub get
    flutter analyze
    flutter test
  '
```

### Coverage gate

```bash
cd mobile
flutter test --coverage
cd ..
python3 scripts/coverage_gate.py check --stack mobile
```

The versioned baseline must never be lowered to make a failing build pass. If coverage legitimately increases after the full validation suite succeeds:

```bash
python3 scripts/coverage_gate.py bump --stack mobile
```

## Security

Development and production configuration must remain separate.

- never commit real credentials or production secrets
- never expose backend machine error codes directly to users
- keep refresh tokens in secure storage
- do not persist passwords between application screens
- map authentication failures to safe user-facing messages
- use dedicated secret-management infrastructure in production

## Observability

The platform includes structured logs, correlation IDs, distributed traces, RED/USE metrics, OpenTelemetry collection, and Prometheus-compatible metrics.

See `docs/OBSERVABILITY.md` and `infra/otel/`.

## Documentation

Useful project documentation includes:

```text
INSTALL.md
docs/adr/
docs/implementation/
docs/plan/
docs/OBSERVABILITY.md
```

Some historical sprint documents describe the repository state at the time they were written and may not represent the current implementation state.

## Development branch

Active development currently happens on `develop`.

Before pushing:

```bash
git fetch origin
git status
git diff --check
```

Avoid force-pushing shared development history.
