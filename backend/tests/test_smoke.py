"""Smoke tests. Real tests come with Phase 1."""


def test_smoke():
    assert 1 + 1 == 2


def test_django_imports():
    """Sanity check: Django settings load correctly."""
    from django.conf import settings

    assert settings.DEBUG is True or settings.DEBUG is False
