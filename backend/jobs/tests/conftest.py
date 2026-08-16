"""
Shared pytest fixtures for the jobs test suite.
"""

import pytest
import redis
from django.conf import settings


@pytest.fixture(autouse=True)
def clear_redis_state():
    """
    Circuit breaker (cb:*) and alert throttle (alert:*) state live in Redis,
    which is NOT rolled back between tests the way the database is. Without
    clearing it, state leaks across tests: a domain that tripped the breaker
    shows as circuit_open elsewhere; an alert throttle key blocks a later
    test's alert.

    autouse=True → runs for every test in the suite. We flush both key
    prefixes before and after each test so every test starts clean.
    """
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    def _flush():
        for pattern in ("cb:*", "alert:*"):
            for key in r.scan_iter(pattern):
                r.delete(key)

    _flush()
    yield
    _flush()


@pytest.fixture(autouse=True)
def celery_eager(settings):
    """
    Run Celery tasks synchronously in tests so .delay()/.apply_async() execute
    inline instead of queueing to a worker that isn't running during tests.
    pytest-django's `settings` fixture scopes this override to each test.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
