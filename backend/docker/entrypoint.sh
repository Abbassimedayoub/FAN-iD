#!/usr/bin/env bash
# Single entrypoint for the four application container roles: api, ws, worker,
# and beat. All roles share the same image; the entrypoint selects behavior.
set -euo pipefail

ROLE="${1:-api}"

echo "[entrypoint] rôle=${ROLE} en cours de démarrage..."

# Fail fast when critical environment variables are missing. Django settings
# validate them again during application startup.
: "${DJANGO_SECRET_KEY:?DJANGO_SECRET_KEY manquant — le conteneur refuse de démarrer}"
: "${DATABASE_URL:?DATABASE_URL manquant — le conteneur refuse de démarrer}"

case "$ROLE" in
  api)
    if [[ "${DJANGO_SETTINGS_MODULE:-}" == "config.settings.prod" ]]; then
      python manage.py migrate --check
    else
      python manage.py migrate --noinput
    fi

    exec python -m uvicorn config.asgi:application       --host 0.0.0.0       --port "${PORT:-8000}"       --workers "${WEB_CONCURRENCY:-2}"
    ;;
  ws)
    exec python -m uvicorn config.asgi:application --host 0.0.0.0 --port 8001 --workers 1
    ;;
  worker)
    echo "[entrypoint] validation Django avant démarrage du worker..."
    python manage.py check --fail-level ERROR

    if [[ "${DJANGO_SETTINGS_MODULE:-}" == "config.settings.prod" ]]; then
      python manage.py migrate --check
    fi

    python -c 'import jwt; print("[entrypoint] PyJWT import OK")'
    exec celery -A config worker --loglevel=INFO --concurrency=2
    ;;
  beat)
    echo "[entrypoint] validation Django avant démarrage de beat..."
    python manage.py check --fail-level ERROR

    if [[ "${DJANGO_SETTINGS_MODULE:-}" == "config.settings.prod" ]]; then
      python manage.py migrate --check
    fi

    python -c 'import jwt; print("[entrypoint] PyJWT import OK")'
    # Static schedule from config.settings.base.CELERY_BEAT_SCHEDULE; no
    # DatabaseScheduler is used for this deployment.
    exec celery -A config beat --loglevel=INFO
    ;;
  *)
    echo "[entrypoint] rôle inconnu: ${ROLE} (attendu: api|ws|worker|beat)" >&2
    exit 1
    ;;
esac
