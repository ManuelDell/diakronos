"""Authenticated encryption for Google credentials/tokens; never log input.

The application SECRET_KEY must be backed up and remain stable. Ciphertexts
are versioned, domain-separated and never accepted as plaintext on read.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.settings import settings

PREFIX = "fernet:v1:"


def _cipher():
    if not settings.secret_key or settings.secret_key == "insecure-dev-key":
        raise ValidationError("Google-Credentials brauchen einen sicheren SECRET_KEY.")
    key = hashlib.sha256(b"diakronos/google/v1\0" + settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(value: str) -> str:
    return PREFIX + _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    try:
        if not value.startswith(PREFIX):
            raise InvalidToken
        return _cipher().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise ValidationError("Google-Credentials konnten nicht entschluesselt werden.") from None
