"""Fernet encryption utilities for tokens and secrets.

Provides key generation, encrypt/decrypt, and key persistence.
Used to protect sensitive data (OAuth2 tokens, service account keys)
at rest on disk.
"""
import os

from cryptography.fernet import Fernet


def generate_encryption_key() -> bytes:
    """Generate a new Fernet encryption key (32 bytes)."""
    return Fernet.generate_key()


def encrypt(key: bytes, data: str | bytes) -> bytes:
    """Encrypt *data* with *key* and return the Fernet token.

    Args:
        key: Fernet key (bytes).
        data: Plaintext — pass as ``str`` or ``bytes``.

    Returns:
        The encrypted Fernet token (bytes).
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return Fernet(key).encrypt(data)


def decrypt(key: bytes, token: bytes) -> str:
    """Decrypt a Fernet *token* with *key* and return the plaintext as ``str``.

    Raises ``cryptography.fernet.InvalidToken`` on key mismatch or
    corrupted data.
    """
    return Fernet(key).decrypt(token).decode("utf-8")


def save_encryption_key(path: str, key: bytes) -> None:
    """Save *key* to *path* on disk.

    Creates parent directories if they don't exist.
    """
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "wb") as f:
        f.write(key)


def load_encryption_key(path: str) -> bytes:
    """Load a Fernet key from *path*.

    Raises ``FileNotFoundError`` if the key file doesn't exist.
    """
    with open(path, "rb") as f:
        return f.read()


# Aliases for convenience
generate_key = generate_encryption_key
save_key = save_encryption_key
load_key = load_encryption_key
