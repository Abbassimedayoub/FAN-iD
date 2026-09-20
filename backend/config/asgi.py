"""
ASGI configuration serving HTTP (DRF) and WebSocket (Channels) over the same
protocol. Business WebSocket routes will be added by `apps.realtime` in later
sprints; Sprint 0 only prepares the routing layer.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

# Empty shell: no business WebSocket routes are exposed in Sprint 0.
websocket_urlpatterns: list = []

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
