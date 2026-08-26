"""Tests for settings persistence: save/load Google Sheets connection config."""
import json
import os
import sys
import tempfile

import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def settings_path(tmp_path):
    return str(tmp_path / 'settings.json')


@pytest.fixture
def settings(settings_path):
    from settings import SettingsManager
    return SettingsManager(settings_path)


class TestSettingsManager:
    """Test the SettingsManager for persisting Google Sheets connection settings."""

    def test_load_returns_empty_when_file_missing(self, settings):
        """load should return default empty dict when config file does not exist."""
        result = settings.load()
        assert result["spreadsheet_id"] == ""
        assert result["service_account_file"] == ""
        assert result["oauth_credentials"] == ""
        assert result["sheet_name"] == "Todos"

    def test_save_and_load_roundtrip(self, settings):
        """save then load should return the same values."""
        config = {
            "spreadsheet_id": "abc123",
            "service_account_file": "/path/to/key.json"
        }
        settings.save(config)
        loaded = settings.load()
        assert loaded["spreadsheet_id"] == "abc123"
        assert loaded["service_account_file"] == "/path/to/key.json"

    def test_save_overwrites_previous(self, settings):
        """Saving a new config should replace the old one."""
        settings.save({"spreadsheet_id": "old", "service_account_file": "/old"})
        settings.save({"spreadsheet_id": "new", "service_account_file": "/new"})
        loaded = settings.load()
        assert loaded["spreadsheet_id"] == "new"
        assert loaded["service_account_file"] == "/new"

    def test_load_persists_across_instantiation(self, settings_path):
        """Settings survive creating a new SettingsManager instance."""
        from settings import SettingsManager
        mgr1 = SettingsManager(settings_path)
        mgr1.save({"spreadsheet_id": "persisted", "service_account_file": "/key"})
        # New instance reads the same file
        mgr2 = SettingsManager(settings_path)
        loaded = mgr2.load()
        assert loaded["spreadsheet_id"] == "persisted"

    def test_save_partial_config_keeps_missing_fields(self, settings):
        """Saving only spreadsheet_id should not erase service_account_file."""
        settings.save({"spreadsheet_id": "initial", "service_account_file": "/key"})
        settings.save({"spreadsheet_id": "updated"})
        loaded = settings.load()
        assert loaded["spreadsheet_id"] == "updated"
        assert loaded["service_account_file"] == "/key"

    def test_save_creates_parent_directory(self, tmp_path):
        """save should create parent directories if they don't exist."""
        from settings import SettingsManager
        deep = str(tmp_path / 'sub' / 'dir' / 'settings.json')
        mgr = SettingsManager(deep)
        mgr.save({"spreadsheet_id": "x", "service_account_file": "/y"})
        assert os.path.exists(deep)

    def test_load_returns_defaults_for_partial_file(self, settings, settings_path):
        """If the file has only spreadsheet_id, service_account_file defaults to ''."""
        with open(settings_path, 'w') as f:
            json.dump({"spreadsheet_id": "partial"}, f)
        loaded = settings.load()
        assert loaded["spreadsheet_id"] == "partial"
        assert loaded["service_account_file"] == ""
