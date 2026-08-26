"""Tests for Fernet encryption utilities in backend/encryption.py."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestGenerateEncryptionKey:
    """Test generate_encryption_key function."""

    def test_returns_bytes(self):
        """generate_encryption_key should return bytes."""
        from encryption import generate_encryption_key
        key = generate_encryption_key()
        assert isinstance(key, bytes)

    def test_returns_fernet_valid_size(self):
        """Key must be 44 bytes (Fernet base64-encoded standard size)."""
        from encryption import generate_encryption_key
        key = generate_encryption_key()
        assert len(key) == 44

    def test_different_keys_each_call(self):
        """Each call should produce a unique key."""
        from encryption import generate_encryption_key
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        assert key1 != key2


class TestEncryptDecrypt:
    """Test encrypt and decrypt functions."""

    def test_encrypt_returns_bytes(self):
        """encrypt should return bytes (the token)."""
        from encryption import generate_encryption_key, encrypt
        key = generate_encryption_key()
        token = encrypt(key, b"secret data")
        assert isinstance(token, bytes)

    def test_decrypt_returns_original(self):
        """decrypt should return the original plaintext as str."""
        from encryption import generate_encryption_key, encrypt, decrypt
        key = generate_encryption_key()
        original = "sensitive secret value"
        token = encrypt(key, original)
        result = decrypt(key, token)
        assert result == original

    def test_encrypt_decrypt_string(self):
        """encrypt/decrypt should work with str input (auto-encoded)."""
        from encryption import generate_encryption_key, encrypt, decrypt
        key = generate_encryption_key()
        original = "my secret string"
        token = encrypt(key, original)
        result = decrypt(key, token)
        assert result == original

    def test_different_keys_cannot_decrypt(self):
        """A token encrypted with one key should fail with another key."""
        from encryption import generate_encryption_key, encrypt, decrypt
        from cryptography.fernet import InvalidToken
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        token = encrypt(key1, "secret")
        with pytest.raises(InvalidToken):
            decrypt(key2, token)

    def test_encrypt_json_credentials(self):
        """encrypt should handle JSON credential strings."""
        import json
        from encryption import generate_encryption_key, encrypt, decrypt
        key = generate_encryption_key()
        creds = json.dumps({"client_id": "abc", "client_secret": "xyz"})
        token = encrypt(key, creds)
        result = decrypt(key, token)
        assert result == creds


class TestSaveLoadKey:
    """Test save_encryption_key and load_encryption_key."""

    def test_save_creates_file(self):
        """save_encryption_key should write the key to disk."""
        from encryption import generate_encryption_key, save_encryption_key
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            key = generate_encryption_key()
            save_encryption_key(path, key)
            assert os.path.exists(path)
        finally:
            os.unlink(path)

    def test_load_returns_saved_key(self):
        """load_encryption_key should return the exact saved key."""
        from encryption import generate_encryption_key, save_encryption_key, load_encryption_key
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            key = generate_encryption_key()
            save_encryption_key(path, key)
            loaded = load_encryption_key(path)
            assert loaded == key
        finally:
            os.unlink(path)

    def test_load_missing_file_raises(self):
        """load_encryption_key should raise FileNotFoundError for missing file."""
        from encryption import load_encryption_key
        with pytest.raises(FileNotFoundError):
            load_encryption_key("/nonexistent/path/to/key")

    def test_roundtrip_save_decrypt(self):
        """Key saved and loaded should still decrypt original data."""
        from encryption import generate_encryption_key, save_encryption_key, load_encryption_key, encrypt, decrypt
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            key = generate_encryption_key()
            token = encrypt(key, "test secret")
            save_encryption_key(path, key)
            loaded_key = load_encryption_key(path)
            assert decrypt(loaded_key, token) == "test secret"
        finally:
            os.unlink(path)
