"""
Real-time execution updates: publish execution state changes to the WebSocket
channel-layer group for a job. Consumers subscribed to that group push the
update to connected browsers.

Called from the executor (a Celery worker process) — different process from the
ASGI/Daphne process where WebSocket connections live. The Redis channel layer
bridges them.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def publish_execution_update(execution):
    """
    Publish one execution's current state to its job's group.

    Safe to call from sync Celery task code — async_to_sync drives the async
    channel-layer API. Never raises into the caller: a channel-layer hiccup
    must not break job execution (real-time is best-effort; the DB is the
    source of truth, and polling is the fallback).
    """
    try:
        layer = get_channel_layer()
        if layer is None:
            return

        group = f"job_{execution.job.public_id}"
        payload = {
            "type": "execution.update",  # routed to consumer.execution_update
            "data": {
                "type": "execution_update",
                "execution": {
                    "public_id": str(execution.public_id),
                    "status": execution.status,
                    "attempt_number": execution.attempt_number,
                    "http_status_code": execution.http_status_code,
                    "scheduled_for": (
                        execution.scheduled_for.isoformat() if execution.scheduled_for else None
                    ),
                    "started_at": (
                        execution.started_at.isoformat() if execution.started_at else None
                    ),
                    "finished_at": (
                        execution.finished_at.isoformat() if execution.finished_at else None
                    ),
                },
            },
        }
        async_to_sync(layer.group_send)(group, payload)
    except Exception:
        # Best-effort: log and swallow. Real-time updates must never break jobs.
        logger.exception(
            "Failed to publish execution update for execution=%s",
            getattr(execution, "public_id", "?"),
        )
