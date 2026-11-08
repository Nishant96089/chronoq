"""
Tests for API rate limiting (Phase 4.2).

We pin the throttle rates and cache directly on the DRF throttle base class via
monkeypatch, rather than overriding REST_FRAMEWORK in settings. DRF caches the
parsed rate and cache backend at the class level the first time throttling runs,
so a per-test settings override is unreliable once an earlier test in the suite
has already exercised throttling (passes alone, fails in the full suite).
Patching SimpleRateThrottle directly is deterministic and auto-reverts.
"""

import uuid

import pytest
from django.core.cache.backends.locmem import LocMemCache
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from jobs.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LOW_RATES = {"burst": "3/min", "sustained": "3/min", "login": "3/min"}


@pytest.fixture
def throttle_env(monkeypatch):
    """
    Pin low rates + a fresh, isolated in-memory throttle store on the throttle
    base class. Unique cache name per test => no count leakage between tests.
    Both patches revert automatically after the test.
    """
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", LOW_RATES)
    fresh_cache = LocMemCache(f"throttle-{uuid.uuid4()}", {})
    monkeypatch.setattr(SimpleRateThrottle, "cache", fresh_cache)
    return fresh_cache


@pytest.fixture
def auth_client():
    user = UserFactory()
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


class TestUserThrottle:
    def test_burst_limit_trips_429(self, throttle_env, auth_client):
        statuses = [auth_client.get("/api/jobs/").status_code for _ in range(5)]
        # First 3 allowed, then throttled.
        assert statuses[:3] == [200, 200, 200]
        assert 429 in statuses[3:]

    def test_under_limit_all_ok(self, throttle_env, auth_client):
        statuses = [auth_client.get("/api/jobs/").status_code for _ in range(3)]
        assert statuses == [200, 200, 200]


class TestLoginThrottle:
    def test_login_brute_force_trips_429(self, throttle_env):
        client = APIClient()
        statuses = []
        for _ in range(5):
            resp = client.post(
                "/api/auth/token/",
                {"username": "admin", "password": "wrong-guess"},
            )
            statuses.append(resp.status_code)
        # Bad creds normally 400; once the login scope is exceeded -> 429.
        assert 429 in statuses
