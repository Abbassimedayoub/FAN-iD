"""Fallback WSGI configuration for deployments that do not require ASGI.
The Docker entrypoint uses Uvicorn/ASGI by default.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_wsgi_application()
