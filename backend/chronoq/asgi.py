"""
ASGI config for chronoq — HTTP + WebSocket.

ProtocolTypeRouter dispatches by protocol:
- "http"      → Django's normal HTTP handling (REST API, admin, etc.)
- "websocket" → Channels routing → our consumers

AuthMiddlewareStack is included for session-based auth support, though our
consumer authenticates via a query-string token itself.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chronoq.settings.dev")

# Initialize Django's app registry BEFORE importing anything that touches models
# or routing (consumers import models indirectly).
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from jobs.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
