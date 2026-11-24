"""
Security tests: the SSRF guard on target URLs and the registration flag.
"""

import pytest
from rest_framework.test import APIClient

from jobs.serializers import JobSerializer
from jobs.validators import UnsafeTargetURLError, validate_public_url

# ---- SSRF validator (pure; IP-literal URLs avoid real DNS in CI) ----


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://0.0.0.0/",
        "ftp://example.com/",
        "file:///etc/passwd",
    ],
)
def test_validate_public_url_blocks_unsafe(url):
    with pytest.raises(UnsafeTargetURLError):
        validate_public_url(url)


@pytest.mark.parametrize("url", ["http://8.8.8.8/", "https://1.1.1.1/"])
def test_validate_public_url_allows_public(url):
    # Public IP literals resolve to themselves; must not raise.
    validate_public_url(url)


# ---- Serializer enforcement (gated on ALLOW_PRIVATE_TARGET_URLS) ----


@pytest.mark.django_db
def test_job_serializer_rejects_private_url_when_ssrf_on(settings):
    settings.ALLOW_PRIVATE_TARGET_URLS = False
    serializer = JobSerializer(
        data={
            "name": "evil",
            "target_url": "http://169.254.169.254/latest/meta-data/",
            "schedule_cron": "* * * * *",
        }
    )
    assert not serializer.is_valid()
    assert "target_url" in serializer.errors


@pytest.mark.django_db
def test_job_serializer_allows_private_url_in_dev(settings):
    # Dev/test default: private targets are permitted (localhost webhooks).
    settings.ALLOW_PRIVATE_TARGET_URLS = True
    serializer = JobSerializer(
        data={
            "name": "local",
            "target_url": "http://127.0.0.1:9000/hook",
            "schedule_cron": "* * * * *",
        }
    )
    assert serializer.is_valid(), serializer.errors


# ---- Registration flag ----


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Reset the shared login-scope throttle counter around each test."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_register_disabled_returns_403(settings):
    settings.ENABLE_REGISTRATION = False
    resp = APIClient().post(
        "/api/auth/register/",
        {"username": "newbie", "password": "pw-xyz-123-abc"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_register_enabled_creates_user_and_token(settings, django_user_model):
    settings.ENABLE_REGISTRATION = True
    resp = APIClient().post(
        "/api/auth/register/",
        {"username": "newbie", "password": "pw-xyz-123-abc"},
        format="json",
    )
    assert resp.status_code == 201
    assert "token" in resp.data
    assert django_user_model.objects.filter(username="newbie").exists()


@pytest.mark.django_db
def test_register_rejects_duplicate_username(settings, django_user_model):
    settings.ENABLE_REGISTRATION = True
    django_user_model.objects.create_user("taken", password="pw-xyz-123-abc")
    resp = APIClient().post(
        "/api/auth/register/",
        {"username": "taken", "password": "pw-xyz-123-abc"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_registration_config_reports_flag(settings):
    settings.ENABLE_REGISTRATION = True
    resp = APIClient().get("/api/auth/config/")
    assert resp.status_code == 200
    assert resp.data["registration_enabled"] is True
