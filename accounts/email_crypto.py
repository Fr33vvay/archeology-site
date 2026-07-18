"""Обратимное шифрование email (Fernet) и хеш для поиска/логина."""

from __future__ import annotations

import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_email(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()


def is_email_hash(value: str | None) -> bool:
    return bool(value) and bool(_HASH_RE.match(value))


def _fernet_key() -> bytes:
    key = getattr(settings, "EMAIL_ENCRYPTION_KEY", None) or getattr(
        settings, "FERNET_KEY", None
    )
    if key:
        if isinstance(key, str):
            key = key.encode("ascii")
        return key
    # Локально/в тестах — стабильный ключ из SECRET_KEY (не для production).
    if settings.DEBUG or getattr(settings, "EMAIL_ENCRYPTION_ALLOW_DERIVED_KEY", False):
        digest = hashlib.sha256(
            f"email-enc:{settings.SECRET_KEY}".encode("utf-8")
        ).digest()
        import base64

        return base64.urlsafe_b64encode(digest)
    raise ImproperlyConfigured(
        "Для шифрования email нужен EMAIL_ENCRYPTION_KEY (или FERNET_KEY) в окружении."
    )


def get_fernet() -> Fernet:
    return Fernet(_fernet_key())


def encrypt_email(plaintext: str) -> str:
    text = normalize_email(plaintext)
    if not text:
        return ""
    return get_fernet().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_email(token: str) -> str:
    if not token:
        return ""
    try:
        return get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise ValueError("Не удалось расшифровать email") from exc
