"""Password, opaque token, CSRF, and API key primitives."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from laoliuliu.config import Settings

_PASSWORD_HASHER = PasswordHasher()


class SecretDecryptionError(ValueError):
    """Raised when an encrypted application secret cannot be opened."""


def normalize_username(value: str) -> str:
    """Return the canonical lowercase username or raise ValueError."""

    normalized = value.strip().lower()
    if not 3 <= len(normalized) <= 64:
        raise ValueError("username must contain 3 to 64 characters")
    if not normalized.replace("_", "").replace("-", "").isalnum():
        raise ValueError("username may contain letters, numbers, hyphens, underscores")
    return normalized


def validate_password(value: str) -> None:
    """Validate the minimum password policy."""

    if not 12 <= len(value) <= 256:
        raise ValueError("password must contain 12 to 256 characters")
    if not any(character.isalpha() for character in value):
        raise ValueError("password must contain a letter")
    if not any(character.isdigit() for character in value):
        raise ValueError("password must contain a digit")


def hash_password(value: str) -> str:
    """Hash a validated password with Argon2id."""

    validate_password(value)
    return _PASSWORD_HASHER.hash(value)


def verify_password(password_hash: str, value: str) -> bool:
    """Return whether the supplied password matches the Argon2id hash."""

    try:
        return _PASSWORD_HASHER.verify(password_hash, value)
    except (VerifyMismatchError, InvalidHashError):
        return False


def generate_password() -> str:
    """Generate a high-entropy temporary password satisfying policy."""

    return f"L6-{secrets.token_urlsafe(18)}-9"


def generate_token() -> str:
    """Generate a high-entropy browser or CSRF token."""

    return secrets.token_urlsafe(32)


def digest_secret(value: str, settings: Settings) -> str:
    """HMAC a secret before persistence."""

    pepper = settings.session_pepper.get_secret_value().encode("utf-8")
    return hmac.new(pepper, value.encode("utf-8"), hashlib.sha256).hexdigest()


def secrets_match(value: str, expected_digest: str, settings: Settings) -> bool:
    """Compare a presented secret with a persisted digest."""

    return hmac.compare_digest(digest_secret(value, settings), expected_digest)


def encrypt_api_key(value: str, settings: Settings) -> str:
    """Encrypt an API key for storage at rest."""

    return (
        Fernet(settings.ai_encryption_key.get_secret_value().encode("ascii"))
        .encrypt(value.encode("utf-8"))
        .decode("ascii")
    )


def decrypt_api_key(value: str, settings: Settings) -> str:
    """Decrypt a stored API key without logging it."""

    try:
        return (
            Fernet(settings.ai_encryption_key.get_secret_value().encode("ascii"))
            .decrypt(value.encode("ascii"))
            .decode("utf-8")
        )
    except (InvalidToken, ValueError) as error:
        raise SecretDecryptionError("stored API key cannot be decrypted") from error
