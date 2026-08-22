"""Tests for the todo-list backend API."""
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_get_todos_returns_empty_list(app):
    """GET /api/todos should return an empty list when no todos exist."""
    client = app.test_client()
    response = client.get('/api/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_create_todo_returns_201(app):
    """POST /api/todos with valid payload should create a todo and return 201."""
    client = app.test_client()
    payload = {"title": "Buy groceries"}
    response = client.post('/api/todos', json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "Buy groceries"
    assert "id" in data
    assert data["completed"] is False


def test_get_todos_after_create(app):
    """GET /api/todos should include a newly created todo."""
    client = app.test_client()
    client.post('/api/todos', json={"title": "Test todo"})
    response = client.get('/api/todos')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["title"] == "Test todo"


def test_update_todo(app):
    """PATCH /api/todos/<id> should update the todo."""
    client = app.test_client()
    create_resp = client.post('/api/todos', json={"title": "Original"})
    todo_id = create_resp.get_json()["id"]
    response = client.patch(f'/api/todos/{todo_id}', json={"title": "Updated"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "Updated"


def test_delete_todo(app):
    """DELETE /api/todos/<id> should remove the todo."""
    client = app.test_client()
    create_resp = client.post('/api/todos', json={"title": "To delete"})
    todo_id = create_resp.get_json()["id"]
    response = client.delete(f'/api/todos/{todo_id}')
    assert response.status_code == 204
    # Verify it's gone
    get_resp = client.get('/api/todos')
    assert len(get_resp.get_json()) == 0


def test_create_todo_missing_title_returns_400(app):
    """POST /api/todos without title should return 400."""
    client = app.test_client()
    response = client.post('/api/todos', json={})
    assert response.status_code == 400


def test_toggle_todo_completed(app):
    """PATCH /api/todos/<id> with completed flag should toggle completion."""
    client = app.test_client()
    create_resp = client.post('/api/todos', json={"title": "Do something"})
    todo_id = create_resp.get_json()["id"]
    response = client.patch(f'/api/todos/{todo_id}', json={"completed": True})
    assert response.status_code == 200
    data = response.get_json()
    assert data["completed"] is True


@pytest.fixture
def app():
    """Create a fresh test app with empty storage."""
    import tempfile
    import shutil
    # Create a temp dir for test storage
    tmpdir = tempfile.mkdtemp()
    storage_path = os.path.join(tmpdir, 'todos.json')
    # Import after tmpdir is set so we can override
    from server import create_app
    app = create_app(storage_path)
    app.config['TESTING'] = True
    yield app
    shutil.rmtree(tmpdir, ignore_errors=True)
