"""
Encrypted model fields (Phase 4.3).

Values are plaintext in Python and ciphertext in the database. Reads are graceful
(see encryption.decrypt_str): legacy plaintext passes through, so the migration
that switches these columns to encrypted cannot corrupt existing rows.
"""

import json

from django.db import models

from .encryption import decrypt_str, encrypt_str


class EncryptedTextField(models.TextField):
    """TextField whose database value is Fernet-encrypted."""

    def get_prep_value(self, value):
        if value is None:
            return value
        return encrypt_str(str(value))

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return decrypt_str(value)


class EncryptedJSONField(models.TextField):
    """
    Stores a JSON-serializable value as Fernet-encrypted text.

    The DB column is text (opaque ciphertext). In the API the field is declared
    as serializers.JSONField so clients still send/receive JSON (see JobSerializer).
    """

    def get_prep_value(self, value):
        if value is None:
            return value
        return encrypt_str(json.dumps(value))

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return {}
        raw = decrypt_str(value)
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            # Legacy plaintext that isn't JSON — return as-is.
            return raw
