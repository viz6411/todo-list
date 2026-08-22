"""Tests for the frontend API client module."""
import pytest
import sys
import os
import tempfile
import shutil

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def api_client():
    """Return a test client for the backend API."""
    tmpdir = tempfile.mkdtemp()
    storage_path = os.path.join(tmpdir, 'todos.json')
    from server import create_app
    app = create_app(storage_path)
    app.config['TESTING'] = True
    client = app.test_client()
    yield client
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def frontend_module(api_client):
    """Provide the frontend API client module bound to a test server."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend', 'js'))
    # We test the JS API client logic by calling the backend directly
    # The JS module uses fetch() which we can't call from Python,
    # so we test the API contract the frontend depends on.
    return api_client


def test_frontend_fetch_todos_returns_array(api_client):
    """Frontend expects GET /api/todos to return a JSON array."""
    resp = api_client.get('/api/todos')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    # Each item has expected shape
    for todo in data:
        assert 'id' in todo
        assert 'title' in todo
        assert 'completed' in todo


def test_frontend_create_todo_shape(api_client):
    """Frontend expects POST /api/todos to return the created todo object."""
    resp = api_client.post('/api/todos', json={"title": "Test item"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert 'id' in data
    assert data['title'] == 'Test item'
    assert data['completed'] is False


def test_frontend_update_todo_preserves_id(api_client):
    """Frontend expects PATCH to return the updated todo with same ID."""
    create = api_client.post('/api/todos', json={"title": "Original"})
    orig = create.get_json()
    resp = api_client.patch(f'/api/todos/{orig["id"]}', json={"completed": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['id'] == orig['id']
    assert data['completed'] is True


def test_frontend_delete_returns_204(api_client):
    """Frontend expects DELETE to return 204 with no body."""
    create = api_client.post('/api/todos', json={"title": "Delete me"})
    tid = create.get_json()['id']
    resp = api_client.delete(f'/api/todos/{tid}')
    assert resp.status_code == 204
    # No JSON body
    assert resp.data == b'' or resp.get_json() is None


def test_frontend_error_handling_400(api_client):
    """Frontend should handle 400 errors gracefully."""
    resp = api_client.post('/api/todos', json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'error' in data


def test_frontend_error_handling_404(api_client):
    """Frontend should handle 404 errors gracefully."""
    resp = api_client.patch('/api/todos/nonexistent-id', json={"completed": True})
    assert resp.status_code == 404
    data = resp.get_json()
    assert 'error' in data


def test_frontend_concurrent_operations(api_client):
    """Frontend should handle rapid sequential operations."""
    ids = []
    for i in range(5):
        resp = api_client.post('/api/todos', json={"title": f"Item {i}"})
        assert resp.status_code == 201
        ids.append(resp.get_json()['id'])

    # Toggle all to complete
    for tid in ids:
        resp = api_client.patch(f'/api/todos/{tid}', json={"completed": True})
        assert resp.status_code == 200

    # Verify all complete
    list_resp = api_client.get('/api/todos')
    todos = list_resp.get_json()
    assert len(todos) == 5
    for todo in todos:
        assert todo['completed'] is True
