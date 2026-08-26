"""Settings persistence for Google Sheets connection config.

Sensitive fields (oauth_credentials, service_account_file path) are
encrypted at rest using Fernet encryption when an encryption key is
available. Non-sensitive fields (spreadsheet_id, sheet_name) are stored
in plaintext.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# Fields that should be encrypted when storing sensitive data.
_SENSITIVE_FIELDS = frozenset([
    "oauth_credentials",
    "service_account_file",
    "service_account_credentials",
    "refresh_token",
    "access_token",
])


class SettingsManager:
    """Save/load Google Sheets connection settings to a JSON file.

    Sensitive values are automatically encrypted on save and decrypted
    on load when an encryption key is available.
    """

    DEFAULTS = {
        "spreadsheet_id": "",
        "service_account_file": "",
        "oauth_credentials": "",
        "sheet_name": "Todos",
    }

    def __init__(self, settings_path: str, encryption_key_path: str | None = None):
        self._path = settings_path
        self._key_path = encryption_key_path
        self._encrypt_fn = None
        self._decrypt_fn = None
        self._setup_encryption()

    def _setup_encryption(self) -> None:
        """Load encryption functions if a key file exists."""
        if self._key_path and os.path.exists(self._key_path):
            try:
                from encryption import encrypt, decrypt, load_key
                key = load_key(self._key_path)
                self._encrypt_fn = lambda data: encrypt(key, data)
                self._decrypt_fn = lambda data: decrypt(key, data)
                logger.info("Encryption enabled for settings (key: %s)", self._key_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load encryption key %s; settings will be stored unencrypted. Error: %s",
                    self._key_path, exc,
                )

    def _is_sensitive(self, key: str) -> bool:
        """Check if a setting key contains sensitive data."""
        return key in _SENSITIVE_FIELDS

    def _encrypt_value(self, value) -> str | None:
        """Encrypt a value if encryption is available."""
        if self._encrypt_fn and value:
            if isinstance(value, dict):
                value = json.dumps(value)
            try:
                token = self._encrypt_fn(str(value))
                # Fernet returns bytes; decode to base64 string for JSON storage
                return token.decode("utf-8")
            except Exception as exc:
                logger.warning("Encryption failed for value: %s", exc)
                return str(value) if value else None
        # No encryption — preserve the original value type
        return value

    def _decrypt_value(self, value, key: str):
        """Decrypt a value if it's sensitive and encryption is available."""
        if value is None:
            return None
        if self._decrypt_fn and self._is_sensitive(key):
            try:
                # value is stored as base64 string; encode to bytes for Fernet
                token = value.encode("utf-8") if isinstance(value, str) else value
                decrypted = self._decrypt_fn(token)
                # Try to parse as JSON (for dict credentials)
                try:
                    return json.loads(decrypted)
                except (json.JSONDecodeError, ValueError):
                    return decrypted
            except Exception as exc:
                logger.warning(
                    "Decryption failed for %s; returning raw value. Error: %s",
                    key, exc,
                )
                return value
        return value

    def load(self) -> dict:
        """Load settings from disk, merging with defaults."""
        defaults = dict(self.DEFAULTS)
        if os.path.exists(self._path):
            with open(self._path, 'r') as f:
                content = f.read().strip()
            if content:
                try:
                    data = json.loads(content)
                    # Decrypt sensitive fields
                    for key in data:
                        if self._is_sensitive(key):
                            data[key] = self._decrypt_value(data[key], key)
                    defaults.update(data)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Corrupted settings file %s; falling back to defaults. Error: %s",
                        self._path, exc,
                    )
        return defaults

    def save(self, config: dict) -> None:
        """Save settings to disk, merging with existing values.

        Sensitive fields are encrypted before storage.
        """
        existing = self.load()
        existing.update(config)
        # Encrypt sensitive fields before saving
        to_save = {}
        for key, value in existing.items():
            if self._is_sensitive(key):
                to_save[key] = self._encrypt_value(value)
            else:
                to_save[key] = value
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w') as f:
            json.dump(to_save, f, indent=2)

    def get_encrypted_settings(self) -> dict:
        """Return the raw (encrypted) settings on disk."""
        if os.path.exists(self._path):
            with open(self._path, 'r') as f:
                content = f.read().strip()
            if content:
                return json.loads(content)
        return {}
