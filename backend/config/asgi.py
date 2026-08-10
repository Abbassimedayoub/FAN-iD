"""
Configuration ASGI — sert HTTP (DRF) et WebSocket (Channels) sous le même
protocole, conforme à Source A §1.4.2 (ASGI/Gunicorn-Uvicorn).
Les routes WebSocket métier seront ajoutées par `apps.realtime` aux sprints
suivants ; le Sprint 0 ne fait que préparer le routage (§1 master prompt :
"WebSocket doit être préparé", pas implémenté).
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

# Coquille vide : aucune route WebSocket métier au Sprint 0.
websocket_urlpatterns: list = []

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
