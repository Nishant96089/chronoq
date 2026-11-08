"""
Tests for field encryption (Phase 4.3).
"""

import pytest
from cryptography.fernet import Fernet
from django.db import connection
from django.test import override_settings

from jobs.encryption import decrypt_str, encrypt_str
from jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


class TestEncryptHelpers:
    def test_round_trip(self):
        assert decrypt_str(encrypt_str("secret")) == "secret"

    def test_ciphertext_differs_from_plaintext(self):
        token = encrypt_str("Bearer abc123")
        assert token != "Bearer abc123"
        assert "Bearer" not in token

    def test_graceful_passthrough_for_plaintext(self):
        # A value that isn't a valid Fernet token comes back unchanged.
        assert decrypt_str("not-a-token") == "not-a-token"

    def test_key_rotation(self):
        key_a = Fernet.generate_key().decode()
        key_b = Fernet.generate_key().decode()
        with override_settings(FIELD_ENCRYPTION_KEYS=[key_a]):
            token = encrypt_str("secret")
        # Rotate: new primary key_b, old key_a still accepted for decrypt.
        with override_settings(FIELD_ENCRYPTION_KEYS=[key_b, key_a]):
            assert decrypt_str(token) == "secret"
            new_token = encrypt_str("secret2")
        # New key alone decrypts the new token.
        with override_settings(FIELD_ENCRYPTION_KEYS=[key_b]):
            assert decrypt_str(new_token) == "secret2"


class TestEncryptedFields:
    def test_transparent_round_trip(self):
        job = JobFactory(
            headers={"Authorization": "Bearer topsecret"},
            body="api_key=supersecret",
        )
        job.refresh_from_db()
        assert job.headers == {"Authorization": "Bearer topsecret"}
        assert job.body == "api_key=supersecret"

    def test_ciphertext_at_rest(self):
        job = JobFactory(
            headers={"Authorization": "Bearer topsecret"},
            body="api_key=supersecret",
        )
        with connection.cursor() as c:
            c.execute("SELECT headers, body FROM jobs_job WHERE id = %s", [job.id])
            raw_headers, raw_body = c.fetchone()
        # Raw stored values must NOT contain the plaintext secrets...
        assert "topsecret" not in raw_headers
        assert "supersecret" not in raw_body
        # ...and look like Fernet tokens.
        assert raw_headers.startswith("gAAAA")
        assert raw_body.startswith("gAAAA")
