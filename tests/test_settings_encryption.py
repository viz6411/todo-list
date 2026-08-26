"""Integration tests for SettingsManager with encryption.

Verifies that SettingsManager correctly encrypts sensitive fields
on save and decrypts them on load when an encryption key is available.
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def encryption_key_path(tmp_path):
    """Create a Fernet encryption key file."""
    from encryption import generate_key, save_key
    key = generate_key()
    key_file = tmp_path / ".encryption_key"
    save_key(str(key_file), key)
    return str(key_file)


@pytest.fixture
def settings_path(tmp_path):
    """Create a settings file path."""
    return str(tmp_path / "settings.json")


class TestSettingsManagerEncryption:
    """Test SettingsManager with encryption enabled."""

    def test_encrypts_sensitive_fields_on_save(self, settings_path, encryption_key_path):
        """Sensitive fields should be encrypted when saved."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path, encryption_key_path=encryption_key_path)

        mgr.save({
            "oauth_credentials": {"refresh_token": "secret_token_123"},
            "spreadsheet_id": "visible-id-123",
        })

        # Read raw file — sensitive fields should be encrypted
        with open(settings_path) as f:
            raw = json.load(f)

        # oauth_credentials should NOT be the original dict
        assert raw["oauth_credentials"] != {"refresh_token": "secret_token_123"}
        # spreadsheet_id should be plaintext
        assert raw["spreadsheet_id"] == "visible-id-123"

    def test_decrypts_sensitive_fields_on_load(self, settings_path, encryption_key_path):
        """Sensitive fields should be decrypted when loaded."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path, encryption_key_path=encryption_key_path)

        mgr.save({
            "oauth_credentials": {"refresh_token": "secret_token_123"},
            "spreadsheet_id": "visible-id-123",
        })

        # Reload and verify decryption
        loaded = mgr.load()
        assert loaded["oauth_credentials"] == {"refresh_token": "secret_token_123"}
        assert loaded["spreadsheet_id"] == "visible-id-123"

    def test_save_load_roundtrip(self, settings_path, encryption_key_path):
        """Save and load should produce identical data."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path, encryption_key_path=encryption_key_path)

        original = {
            "oauth_credentials": {"refresh_token": "abc", "client_id": "xyz"},
            "service_account_file": "/path/to/key.json",
            "spreadsheet_id": "my-spreadsheet",
            "sheet_name": "Tasks",
        }
        mgr.save(original)

        loaded = mgr.load()
        assert loaded["oauth_credentials"] == original["oauth_credentials"]
        assert loaded["service_account_file"] == original["service_account_file"]
        assert loaded["spreadsheet_id"] == original["spreadsheet_id"]
        assert loaded["sheet_name"] == original["sheet_name"]

    def test_without_encryption_key_stores_plaintext(self, settings_path):
        """Without encryption key, settings are stored as-is."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path)

        mgr.save({
            "oauth_credentials": {"refresh_token": "token"},
            "spreadsheet_id": "visible-id",
        })

        with open(settings_path) as f:
            raw = json.load(f)

        assert raw["oauth_credentials"] == {"refresh_token": "token"}

    def test_without_encryption_key_loads_plaintext(self, settings_path):
        """Without encryption key, settings load as-is."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path)

        mgr.save({
            "oauth_credentials": {"refresh_token": "token"},
        })

        loaded = mgr.load()
        assert loaded["oauth_credentials"] == {"refresh_token": "token"}

    def test_encrypted_settings_different_from_original(self, settings_path, encryption_key_path):
        """Encrypted values on disk should look different from originals."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path, encryption_key_path=encryption_key_path)

        mgr.save({
            "refresh_token": "my_secret_refresh",
        })

        raw = mgr.get_encrypted_settings()
        assert raw["refresh_token"] != "my_secret_refresh"

    def test_service_account_credentials_encrypted(self, settings_path, encryption_key_path):
        """Service account credentials should be encrypted."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path, encryption_key_path=encryption_key_path)

        mgr.save({
            "service_account_credentials": {"type": "service_account", "project_id": "test"},
        })

        raw = mgr.get_encrypted_settings()
        assert raw["service_account_credentials"] != {"type": "service_account", "project_id": "test"}

    def test_service_account_file_encrypted(self, settings_path, encryption_key_path):
        """Service account file path should be encrypted."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path, encryption_key_path=encryption_key_path)

        mgr.save({
            "service_account_file": "/secrets/my-service-key.json",
        })

        raw = mgr.get_encrypted_settings()
        assert raw["service_account_file"] != "/secrets/my-service-key.json"

    def test_empty_oauth_credentials_handled(self, settings_path, encryption_key_path):
        """Empty oauth_credentials should be handled gracefully."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path, encryption_key_path=encryption_key_path)

        mgr.save({
            "oauth_credentials": "",
            "spreadsheet_id": "test-id",
        })

        loaded = mgr.load()
        assert loaded["spreadsheet_id"] == "test-id"

    def test_merge_existing_settings(self, settings_path, encryption_key_path):
        """Saving new settings should merge with existing ones."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path, encryption_key_path=encryption_key_path)

        mgr.save({
            "spreadsheet_id": "first-id",
            "oauth_credentials": {"refresh_token": "first"},
        })

        mgr.save({
            "sheet_name": "CustomSheet",
        })

        loaded = mgr.load()
        assert loaded["spreadsheet_id"] == "first-id"
        assert loaded["sheet_name"] == "CustomSheet"


class TestSettingsManagerSensitivity:
    """Test that sensitive field detection works correctly."""

    def test_is_sensitive_oauth_credentials(self, settings_path):
        """oauth_credentials should be considered sensitive."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path)
        assert mgr._is_sensitive("oauth_credentials") is True

    def test_is_sensitive_refresh_token(self, settings_path):
        """refresh_token should be considered sensitive."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path)
        assert mgr._is_sensitive("refresh_token") is True

    def test_is_sensitive_spreadsheet_id(self, settings_path):
        """spreadsheet_id should NOT be considered sensitive."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path)
        assert mgr._is_sensitive("spreadsheet_id") is False

    def test_is_sensitive_sheet_name(self, settings_path):
        """sheet_name should NOT be considered sensitive."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path)
        assert mgr._is_sensitive("sheet_name") is False


class TestSettingsManagerDefaults:
    """Test that defaults include OAuth2 fields."""

    def test_defaults_include_oauth_credentials(self, settings_path):
        """DEFAULTS should include oauth_credentials."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path)
        assert "oauth_credentials" in mgr.DEFAULTS

    def test_defaults_include_sheet_name(self, settings_path):
        """DEFAULTS should include sheet_name."""
        from settings import SettingsManager
        mgr = SettingsManager(settings_path)
        assert "sheet_name" in mgr.DEFAULTS
