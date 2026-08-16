"""
Per-domain circuit breaker backed by Redis.

Three states:
- CLOSED   : normal. Requests flow. Consecutive failures are counted.
             At >= FAILURE_THRESHOLD consecutive failures, trip to OPEN.
- OPEN     : blocking. Requests are refused without touching the target.
             After COOLDOWN_SECONDS, the next check transitions to HALF_OPEN.
- HALF_OPEN: testing. One probe is allowed through.
             Probe success -> CLOSED. Probe failure -> OPEN (fresh cooldown).

State is keyed per-domain so all jobs hitting the same host share a breaker:
one job discovering an outage protects the rest.

Redis is the store because the check runs on every execution and must be
shared across all worker processes. We use short Lua-free atomic operations;
where races matter (the half-open probe), we rely on Redis SET NX semantics.
"""

import logging
import time
from urllib.parse import urlparse

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# --- Tunables (hardcoded defaults; could become settings later) ---
FAILURE_THRESHOLD = 5  # consecutive failures before opening
COOLDOWN_SECONDS = 60  # how long to stay OPEN before probing
STATE_TTL_SECONDS = 3600  # expire breaker keys after inactivity

# Circuit states
CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    A per-domain circuit breaker. Instantiate per execution; state lives in Redis.
    """

    def __init__(self, redis_client=None):
        if redis_client is None:
            # DB 0 is our general cache DB (broker is 1, results 2).
            redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.r = redis_client

    @staticmethod
    def domain_for(url: str) -> str:
        """Extract the host (domain) from a URL. This is the breaker key unit."""
        return urlparse(url).netloc or "unknown"

    def _keys(self, domain: str):
        return {
            "state": f"cb:{domain}:state",
            "failures": f"cb:{domain}:failures",
            "opened_at": f"cb:{domain}:opened_at",
            "probe_lock": f"cb:{domain}:probe_lock",
        }

    def allows_request(self, domain: str) -> tuple[bool, str]:
        """
        Decide whether a request to this domain may proceed.

        Returns (allowed, state) where state is the effective state at the
        moment of the decision. If OPEN's cooldown has elapsed, we transition
        to HALF_OPEN and allow exactly one probe (guarded by a lock).
        """
        keys = self._keys(domain)
        state = self.r.get(keys["state"]) or CLOSED

        if state == CLOSED:
            return True, CLOSED

        if state == OPEN:
            opened_at = self.r.get(keys["opened_at"])
            if opened_at is None:
                # Defensive: opened_at missing, treat as expired -> half-open.
                return self._try_enter_half_open(domain), HALF_OPEN
            elapsed = time.time() - float(opened_at)
            if elapsed >= COOLDOWN_SECONDS:
                return self._try_enter_half_open(domain), HALF_OPEN
            # Still cooling down -> block.
            return False, OPEN

        if state == HALF_OPEN:
            # Already half-open: only the probe holder proceeds. Others block.
            # The probe holder was granted when the state flipped to half-open.
            return self._try_enter_half_open(domain), HALF_OPEN

        # Unknown state -> fail safe to closed.
        return True, CLOSED

    def _try_enter_half_open(self, domain: str) -> bool:
        """
        Grant exactly one probe. Uses SET NX as a mutex: the first caller to
        acquire the probe lock is allowed through; concurrent callers are
        blocked until the probe resolves (or the lock TTL expires).
        """
        keys = self._keys(domain)
        # Mark state half-open (idempotent).
        self.r.set(keys["state"], HALF_OPEN, ex=STATE_TTL_SECONDS)
        # Acquire the single-probe lock. NX = only if not exists.
        acquired = self.r.set(keys["probe_lock"], "1", nx=True, ex=COOLDOWN_SECONDS)
        return bool(acquired)

    def record_success(self, domain: str) -> None:
        """A request succeeded. Reset to CLOSED and clear counters."""
        keys = self._keys(domain)
        pipe = self.r.pipeline()
        pipe.set(keys["state"], CLOSED, ex=STATE_TTL_SECONDS)
        pipe.delete(keys["failures"])
        pipe.delete(keys["opened_at"])
        pipe.delete(keys["probe_lock"])
        pipe.execute()

    def record_failure(self, domain: str) -> str:
        """
        A request failed. Increment consecutive failures; open the circuit if
        the threshold is reached. If we were HALF_OPEN, a failure re-opens with
        a fresh cooldown. Returns the resulting state.
        """
        keys = self._keys(domain)
        state = self.r.get(keys["state"]) or CLOSED

        if state == HALF_OPEN:
            # Probe failed -> back to OPEN with fresh cooldown.
            self._open(domain)
            return OPEN

        failures = self.r.incr(keys["failures"])
        self.r.expire(keys["failures"], STATE_TTL_SECONDS)

        if failures >= FAILURE_THRESHOLD:
            self._open(domain)
            return OPEN

        return CLOSED

    def _open(self, domain: str) -> None:
        """Transition to OPEN, stamping the time and clearing the probe lock."""
        keys = self._keys(domain)
        pipe = self.r.pipeline()
        pipe.set(keys["state"], OPEN, ex=STATE_TTL_SECONDS)
        pipe.set(keys["opened_at"], str(time.time()), ex=STATE_TTL_SECONDS)
        pipe.delete(keys["probe_lock"])
        pipe.delete(keys["failures"])
        pipe.execute()
        logger.warning("circuit OPENED for domain=%s", domain)

    def current_state(self, domain: str) -> str:
        """Read the current state without side effects (for inspection/tests)."""
        return self.r.get(self._keys(domain)["state"]) or CLOSED
