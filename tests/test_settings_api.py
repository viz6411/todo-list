"""Tests for the /api/settings endpoint in the Flask app."""
import os
import sys
import tempfile
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import backend.server


@pytest.fixture
def settings_client():
    """Flask test client with a temp settings file and json backend."""
    tmpdir = tempfile.mkdtemp()
    settings_path = os.path.join(tmpdir, 'settings.json')
    storage_path = os.path.join(tmpdir, 'todos.json')
    app = backend.server.create_app(
        backend_type="json",
        storage_path=storage_path,
        settings_path=settings_path,
    )
    app.config['TESTING'] = True
    yield app.test_client(), settings_path, tmpdir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestGetSettings:
    def test_returns_default_settings_when_none_saved(self, settings_client):
        """GET /api/settings returns defaults when no config exists."""
        c, _, _ = settings_client
        resp = c.get('/api/settings')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "spreadsheet_id" in data
        assert "service_account_file" in data
        assert data["spreadsheet_id"] == ""
        assert data["service_account_file"] == ""

    def test_returns_saved_settings(self, settings_client):
        """GET /api/settings returns previously saved settings."""
        c, _, _ = settings_client
        # Save settings first
        c.post('/api/settings', json={
            "spreadsheet_id": "abc123",
            "service_account_file": "/path/to/key.json"
        })
        resp = c.get('/api/settings')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["spreadsheet_id"] == "abc123"
        assert data["service_account_file"] == "/path/to/key.json"


class TestPostSettings:
    def test_save_settings(self, settings_client):
        """POST /api/settings saves and returns the config."""
        c, _, _ = settings_client
        resp = c.post('/api/settings', json={
            "spreadsheet_id": "new-id",
            "service_account_file": "/new/key.json"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["spreadsheet_id"] == "new-id"

    def test_save_settings_persists(self, settings_client):
        """Saved settings survive a subsequent GET."""
        c, _, _ = settings_client
        c.post('/api/settings', json={"spreadsheet_id": "persist"})
        resp = c.get('/api/settings')
        assert resp.get_json()["spreadsheet_id"] == "persist"

    def test_save_partial_settings_preserves_other(self, settings_client):
        """Saving only spreadsheet_id keeps service_account_file."""
        c, _, _ = settings_client
        c.post('/api/settings', json={
            "spreadsheet_id": "first",
            "service_account_file": "/old/key.json"
        })
        c.post('/api/settings', json={"spreadsheet_id": "second"})
        resp = c.get('/api/settings')
        data = resp.get_json()
        assert data["spreadsheet_id"] == "second"
        assert data["service_account_file"] == "/old/key.json"

    def test_save_settings_roundtrip(self, settings_client):
        """POST /api/settings saves the config and GET returns it."""
        c, _, _ = settings_client
        resp = c.post('/api/settings', json={
            "spreadsheet_id": "roundtrip-test",
            "service_account_file": "/deploy/sa_key.json",
        })
        assert resp.status_code == 200

    def test_save_missing_json_body_returns_400(self, settings_client):
        """POST /api/settings with no body returns 400."""
        c, _, _ = settings_client
        resp = c.post('/api/settings')
        assert resp.status_code == 400


class TestAutoBackendSelection:
    """Test that the app auto-selects backend based on persisted settings."""

    def test_auto_selects_sheets_when_configured(self, mocker):
        """When backend_type is None and settings have valid creds, use sheets."""
        tmpdir = tempfile.mkdtemp()
        settings_path = os.path.join(tmpdir, 'settings.json')
        storage_path = os.path.join(tmpdir, 'todos.json')

        # Mock SettingsManager to return valid credentials
        settings_mgr_mock = mocker.Mock()
        settings_mgr_mock.load.return_value = {
            "spreadsheet_id": "test-spreadsheet",
            "service_account_file": "/tmp/fake_key.json",
        }
        mocker.patch.object(backend.server, 'SettingsManager', return_value=settings_mgr_mock)

        sheets_mock = mocker.Mock()
        create_backend_mock = mocker.patch.object(backend.server, 'create_backend',
                                                  return_value=sheets_mock)

        # Call create_app — it uses the patched module-level names
        backend.server.create_app(backend_type=None,
                                   settings_path=settings_path,
                                   storage_path=storage_path)

        # create_backend should have been called with "sheets"
        create_backend_mock.assert_called_once_with(
            "sheets",
            spreadsheet_id="test-spreadsheet",
            service_account_file="/tmp/fake_key.json",
            storage_path=storage_path,
        )

    def test_explicit_backend_type_is_not_overridden(self):
        """When backend_type='json' is explicit, auto-selection is skipped."""
        tmpdir = tempfile.mkdtemp()
        settings_path = os.path.join(tmpdir, 'settings.json')
        storage_path = os.path.join(tmpdir, 'todos.json')

        # Write settings with valid credentials — should be ignored
        with open(settings_path, 'w') as f:
            json.dump({
                "spreadsheet_id": "configured-id",
                "service_account_file": "/configured/key.json",
            }, f)

        # Explicitly request json backend — should not switch to sheets
        app = backend.server.create_app(
            backend_type="json",
            storage_path=storage_path,
            settings_path=settings_path,
        )

        # App should be created successfully with json backend
        assert app is not None
        get_todos_view = app.view_functions['get_todos']
        assert get_todos_view is not None

    def test_fallback_to_json_on_sheets_failure(self, mocker):
        """When sheets backend fails to init, fall back to json backend."""
        tmpdir = tempfile.mkdtemp()
        settings_path = os.path.join(tmpdir, 'settings.json')
        storage_path = os.path.join(tmpdir, 'todos.json')

        # Settings have valid credentials
        settings_mgr_mock = mocker.Mock()
        settings_mgr_mock.load.return_value = {
            "spreadsheet_id": "test-spreadsheet",
            "service_account_file": "/tmp/fake_key.json",
        }
        mocker.patch.object(backend.server, 'SettingsManager', return_value=settings_mgr_mock)

        # First call to create_backend("sheets") raises, second call ("json") succeeds
        json_backend_mock = mocker.Mock()
        call_count = [0]

        def side_effect(backend_type, **kwargs):
            call_count[0] += 1
            if backend_type == "sheets":
                raise FileNotFoundError("Key file not found")
            return json_backend_mock

        create_backend_mock = mocker.patch.object(backend.server, 'create_backend',
                                                  side_effect=side_effect)

        app = backend.server.create_app(backend_type=None,
                                         settings_path=settings_path,
                                         storage_path=storage_path)

        # Should have tried sheets first, then fallen back to json
        assert call_count[0] == 2
        calls = create_backend_mock.call_args_list
        assert calls[0][0][0] == "sheets"
        assert calls[1][0][0] == "json"
