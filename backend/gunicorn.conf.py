"""
Gunicorn configuration for chronoq (production).

We serve the ASGI app (HTTP + WebSocket) with Uvicorn workers under Gunicorn:
- Gunicorn gives mature process supervision: graceful SIGHUP reloads, worker
  recycling (max_requests) to cap slow memory growth, and lifecycle hooks.
- Uvicorn workers speak ASGI, so Channels WebSocket consumers work — which
  plain WSGI (the old prod CMD) could never do.

The child_exit hook is load-bearing: chronoq exports Prometheus metrics in
multiprocess mode, and each dying worker must be marked dead so its shared
metric files are reaped. Without it, recycled workers leak stale series and
/metrics slowly drifts.
"""

import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Uvicorn worker = ASGI. Required for WebSockets.
worker_class = "uvicorn.workers.UvicornWorker"

# Async workers each handle many concurrent connections, so we need far fewer
# than the sync (2*CPU+1) rule of thumb. Modest default; override per-host.
workers = int(os.getenv("WEB_CONCURRENCY", "2"))

# Recycle workers periodically to bound memory growth from any slow leak.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# Worker liveness timeout. Async workers rarely block, so this guards true hangs
# rather than long requests; keep comfortably above the slowest HTTP handler.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Logs to stdout/stderr so the container runtime collects them.
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")


def child_exit(server, worker):
    """Reap a dead worker's Prometheus multiprocess metric files."""
    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
    except Exception:
        # Never let metrics bookkeeping crash worker shutdown.
        pass
