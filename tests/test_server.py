"""Tests for the Flask app integrated with the storage backend."""
import os
import sys
import tempfile

import pytest

# Ensure backend/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.server import create_app


@pytest.fixture
def client():
    """A Flask test client using the JSON backend with a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
    tmp.close()
    app = create_app(backend_type="json", storage_path=tmp.name)
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c, tmp.name


class TestGetTodos:
    def test_returns_empty_list_when_no_todos(self, client):
        """GET /api/todos returns [] when storage is empty."""
        c, _ = client
        resp = c.get('/api/todos')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_saved_todos(self, client):
        """GET /api/todos returns todos that were previously saved."""
        c, path = client
        # Seed data directly
        import json
        seed = [{"id": "abc", "title": "Hello", "completed": False}]
        with open(path, 'w') as f:
            json.dump(seed, f)
        resp = c.get('/api/todos')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Hello"


class TestCreateTodo:
    def test_create_valid_todo(self, client):
        """POST /api/todos with valid title creates a todo."""
        c, _ = client
        resp = c.post('/api/todos',
                       json={"title": "Buy milk"},
                       content_type='application/json')
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy milk"
        assert data["completed"] is False
        assert "id" in data

    def test_create_missing_title(self, client):
        """POST /api/todos without title returns 400."""
        c, _ = client
        resp = c.post('/api/todos',
                       json={"completed": False},
                       content_type='application/json')
        assert resp.status_code == 400

    def test_create_empty_title(self, client):
        """POST /api/todos with empty/whitespace title returns 400."""
        c, _ = client
        resp = c.post('/api/todos',
                       json={"title": "   "},
                       content_type='application/json')
        assert resp.status_code == 400

    def test_persists_to_storage(self, client):
        """Created todo appears in subsequent GET."""
        c, _ = client
        c.post('/api/todos', json={"title": "Task 1"})
        resp = c.get('/api/todos')
        data = resp.get_json()
        assert any(t["title"] == "Task 1" for t in data)


class TestUpdateTodo:
    def test_update_title(self, client):
        """PATCH /api/todos/<id> updates the title."""
        c, _ = client
        create_resp = c.post('/api/todos', json={"title": "Old"})
        todo_id = create_resp.get_json()["id"]

        resp = c.patch(f'/api/todos/{todo_id}',
                        json={"title": "New"},
                        content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "New"

    def test_update_completed(self, client):
        """PATCH /api/todos/<id> can toggle completed."""
        c, _ = client
        create_resp = c.post('/api/todos', json={"title": "Task"})
        todo_id = create_resp.get_json()["id"]

        resp = c.patch(f'/api/todos/{todo_id}',
                        json={"completed": True},
                        content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()["completed"] is True

    def test_update_nonexistent(self, client):
        """PATCH unknown id returns 404."""
        c, _ = client
        resp = c.patch('/api/todos/does-not-exist',
                        json={"title": "X"},
                        content_type='application/json')
        assert resp.status_code == 404


class TestDeleteTodo:
    def test_delete_existing(self, client):
        """DELETE /api/todos/<id> removes the todo."""
        c, _ = client
        create_resp = c.post('/api/todos', json={"title": "ToDelete"})
        todo_id = create_resp.get_json()["id"]

        resp = c.delete(f'/api/todos/{todo_id}')
        assert resp.status_code == 204

        resp = c.get('/api/todos')
        remaining = resp.get_json()
        assert all(t["id"] != todo_id for t in remaining)

    def test_delete_nonexistent(self, client):
        """DELETE unknown id returns 404."""
        c, _ = client
        resp = c.delete('/api/todos/does-not-exist')
        assert resp.status_code == 404


class TestIndexRoute:
    def test_serves_frontend(self, client):
        """GET / returns the frontend index.html (or 404 if missing)."""
        c, _ = client
        resp = c.get('/')
        # May be 200 if frontend exists, or 404 if not — both are valid
        assert resp.status_code in (200, 404)
