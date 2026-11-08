"""
Field encryption (secrets at rest) — Phase 4.3.

Job.headers and Job.body can hold credentials (Authorization bearer tokens, API
keys). They are encrypted at rest with Fernet (authenticated AES-128-CBC + HMAC)
so the database only ever holds ciphertext; the worker decrypts transparently
when it fires the job.

Keys: settings.FIELD_ENCRYPTION_KEYS is a list of Fernet keys. The FIRST key
encrypts; ALL are tried on decrypt (MultiFernet) — so you rotate by PREPENDING a
new key and keeping the old one until every row has been re-encrypted. If no keys
are set, one is DERIVED from DJANGO_SECRET_KEY so dev/test/CI work with no extra
config; production must set explicit FIELD_ENCRYPTION_KEYS.

Reads are graceful: decrypt_str() returns its input unchanged when that input is
not a valid token, so legacy plaintext rows keep working during a rollout.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings


def _derive_key_from_secret() -> str:
    """A valid Fernet key deterministically derived from DJANGO_SECRET_KEY."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode()


def _get_fernet() -> MultiFernet:
    keys = [k for k in getattr(settings, "FIELD_ENCRYPTION_KEYS", []) if k]
    if not keys:
        keys = [_derive_key_from_secret()]
    return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])


def encrypt_str(plaintext: str) -> str:
    """Encrypt a string, returning a Fernet token (str)."""
    if plaintext is None:
        plaintext = ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_str(token: str) -> str:
    """
    Decrypt a Fernet token. If the input is not a valid token (e.g. legacy
    plaintext written before encryption was enabled), return it unchanged.
    """
    if token is None:
        return ""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return token
