"""Tests for frontend interaction with the settings API."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.server import create_app


@pytest.fixture
def settings_app_client():
    """Flask test client with settings endpoint."""
    tmpdir = tempfile.mkdtemp()
    settings_path = os.path.join(tmpdir, 'settings.json')
    storage_path = os.path.join(tmpdir, 'todos.json')
    app = create_app(
        backend_type="json",
        storage_path=storage_path,
        settings_path=settings_path,
    )
    app.config['TESTING'] = True
    yield app.test_client(), settings_path
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestFrontendSettingsAPI:
    """Test that the frontend can interact with the settings API."""

    def test_get_settings_returns_valid_json(self, settings_app_client):
        """GET /api/settings returns parseable JSON with expected fields."""
        c, _ = settings_app_client
        resp = c.get('/api/settings')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "spreadsheet_id" in data
        assert "service_account_file" in data

    def test_post_settings_and_verify_get(self, settings_app_client):
        """POST then GET /api/settings roundtrips correctly."""
        c, _ = settings_app_client
        c.post('/api/settings', json={
            "spreadsheet_id": "test-spreadsheet",
            "service_account_file": "/path/to/key.json"
        })
        resp = c.get('/api/settings')
        data = resp.get_json()
        assert data["spreadsheet_id"] == "test-spreadsheet"

    def test_settings_persists_across_requests(self, settings_app_client):
        """Settings survive multiple GET/POST cycles."""
        c, _ = settings_app_client
        c.post('/api/settings', json={"spreadsheet_id": "first"})
        resp1 = c.get('/api/settings')
        assert resp1.get_json()["spreadsheet_id"] == "first"
        c.post('/api/settings', json={"spreadsheet_id": "second"})
        resp2 = c.get('/api/settings')
        assert resp2.get_json()["spreadsheet_id"] == "second"
