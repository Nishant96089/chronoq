"""
Health endpoints for load balancers and orchestrators.

- /healthz (liveness): the process is up and can serve. No external I/O, so a
  slow database never tricks the orchestrator into killing a healthy container.
- /readyz (readiness): dependencies (DB, Redis) are reachable. Returns 503 when
  they are not, so a rolling deploy / load balancer stops routing to a container
  that can't actually do work yet.

Both are plain Django views — deliberately outside DRF, so no auth, no
throttling, and no pagination touch them.
"""

from django.conf import settings
from django.db import connections
from django.http import JsonResponse


def healthz(request):
    """Liveness: 200 as long as the ASGI app can run at all."""
    return JsonResponse({"status": "ok"})


def readyz(request):
    """Readiness: 200 only if DB and Redis are reachable, else 503."""
    checks = {}

    try:
        connections["default"].cursor().execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"

    healthy = all(v == "ok" for v in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )
