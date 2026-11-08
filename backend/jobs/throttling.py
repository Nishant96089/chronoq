"""
API rate limiting (Phase 4.2).

Two per-user limits applied together (DRF supports stacked throttle classes):
- Burst (short window): absorbs normal spikes, blocks floods.
- Sustained (long window): bounds total volume even if paced under the burst cap.

The login endpoint gets its own tight scoped throttle (brute-force guard),
configured on the view via ScopedRateThrottle scope="login" (see chronoq/urls.py).

Throttle counters live in Django's cache. In a multi-process / multi-node
deployment that cache MUST be shared (Redis) — see CACHES in settings — or each
gunicorn worker counts independently and the effective limit is N x the config.
"""

from rest_framework.throttling import UserRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """Short-window per-user cap. Rate from DEFAULT_THROTTLE_RATES['burst']."""

    scope = "burst"


class SustainedRateThrottle(UserRateThrottle):
    """Long-window per-user cap. Rate from DEFAULT_THROTTLE_RATES['sustained']."""

    scope = "sustained"
