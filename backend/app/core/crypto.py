"""Encryption of cloud credentials at rest.

Credentials are serialised to JSON and encrypted with Fernet (AES-128-CBC + HMAC-SHA256).
`CREDENTIALS_ENCRYPTION_KEYS` accepts a comma-separated list so keys can be rotated:
the first key encrypts, every key may decrypt (MultiFernet).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class CredentialDecryptionError(AppError):
    status_code = 500
    code = "credential_decryption_failed"


def _derive_dev_key(secret: str) -> bytes:
    # Development convenience only: derive a stable key from the JWT secret.
    return base64.urlsafe_b64encode(hashlib.sha256(f"mcmp-dev::{secret}".encode()).digest())


@lru_cache
def get_cipher() -> MultiFernet:
    settings = get_settings()
    keys = [k.encode() for k in settings.credentials_encryption_keys]
    if not keys:
        logger.warning(
            "CREDENTIALS_ENCRYPTION_KEYS not set; deriving a development key. "
            "Never run like this in production."
        )
        keys = [_derive_dev_key(settings.jwt_secret_key)]
    return MultiFernet([Fernet(k) for k in keys])


def encrypt_credentials(credentials: dict[str, Any]) -> str:
    payload = json.dumps(credentials, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return get_cipher().encrypt(payload).decode("ascii")


def decrypt_credentials(token: str) -> dict[str, Any]:
    try:
        raw = get_cipher().decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise CredentialDecryptionError(
            "Stored credentials could not be decrypted (encryption key mismatch?)"
        ) from exc
    return json.loads(raw)


def mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * 8 + value[-visible:]
