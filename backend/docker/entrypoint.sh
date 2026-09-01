#!/usr/bin/env bash
# Point d'entrée unique pour les 4 conteneurs applicatifs (api/ws/worker/beat).
# Les 4 conteneurs partagent la même image (§1.4.2 Source A) : c'est cet entrypoint
# qui les différencie, pas l'image.
set -euo pipefail

ROLE="${1:-api}"

echo "[entrypoint] rôle=${ROLE} en cours de démarrage..."

# Le démarrage échoue explicitement si une variable critique manque (§40/§41) —
# vérifié ici pour un retour rapide, et re-vérifié par config.settings au chargement.
: "${DJANGO_SECRET_KEY:?DJANGO_SECRET_KEY manquant — le conteneur refuse de démarrer}"
: "${DATABASE_URL:?DATABASE_URL manquant — le conteneur refuse de démarrer}"

case "$ROLE" in
  api)
    python manage.py migrate --noinput
    exec python -m uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 2
    ;;
  ws)
    exec python -m uvicorn config.asgi:application --host 0.0.0.0 --port 8001 --workers 1
    ;;
  worker)
    echo "[entrypoint] validation Django avant démarrage du worker..."
    python manage.py check --fail-level ERROR
    python -c 'import jwt; print("[entrypoint] PyJWT import OK")'
    exec celery -A config worker --loglevel=INFO --concurrency=2
    ;;
  beat)
    echo "[entrypoint] validation Django avant démarrage de beat..."
    python manage.py check --fail-level ERROR
    python -c 'import jwt; print("[entrypoint] PyJWT import OK")'
    # Planification statique (config.settings.base.CELERY_BEAT_SCHEDULE) : pas de
    # DatabaseScheduler au Sprint 0 (voir commentaire dans settings/base.py).
    exec celery -A config beat --loglevel=INFO
    ;;
  *)
    echo "[entrypoint] rôle inconnu: ${ROLE} (attendu: api|ws|worker|beat)" >&2
    exit 1
    ;;
esac
