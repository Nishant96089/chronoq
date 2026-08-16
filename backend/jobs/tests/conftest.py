"""
Shared pytest fixtures for the jobs test suite.
"""

import pytest
import redis
from django.conf import settings


@pytest.fixture(autouse=True)
def clear_circuit_breaker():
    """
    Circuit breaker state lives in Redis, which is NOT rolled back between
    tests the way the database is. Without clearing it, failures from one
    test trip the breaker and leak into later tests (e.g. a domain that
    accumulated 5 failures shows as circuit_open in an unrelated test).

    autouse=True → runs for every test automatically. We flush the breaker
    keys (cb:*) before each test so every test starts with all circuits closed.
    """
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    for key in r.scan_iter("cb:*"):
        r.delete(key)
    yield
    # Clean up after too, so state doesn't leak to the next test session.
    for key in r.scan_iter("cb:*"):
        r.delete(key)
