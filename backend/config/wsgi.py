"""WSGI de secours (déploiements qui n'exigent pas ASGI). L'entrypoint Docker
utilise Uvicorn/ASGI par défaut (§34 master prompt)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_wsgi_application()
