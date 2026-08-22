"""Integration tests for frontend against backend API."""
import pytest
import sys
import os
import tempfile
import shutil
import subprocess
import time
import requests

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def api_server():
    """Start a test backend server."""
    tmpdir = tempfile.mkdtemp()
    storage_path = os.path.join(tmpdir, 'todos.json')
    
    from server import create_app
    app = create_app(storage_path)
    app.config['TESTING'] = True
    
    # Use werkzeug test client for integration testing
    client = app.test_client()
    yield client
    
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestFrontendAPI:
    """Tests that verify the frontend can interact with the backend API."""
    
    def test_list_todos_initial_empty(self, api_server):
        """Frontend should get empty list on initial load."""
        resp = api_server.get('/api/todos')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_add_todo_and_list(self, api_server):
        """Frontend can add a todo and see it in the list."""
        # Add
        create_resp = api_server.post('/api/todos', json={"title": "Learn TDD"})
        assert create_resp.status_code == 201
        created = create_resp.get_json()
        assert created["id"] is not None
        
        # List
        list_resp = api_server.get('/api/todos')
        assert list_resp.status_code == 200
        todos = list_resp.get_json()
        assert len(todos) == 1
        assert todos[0]["title"] == "Learn TDD"
    
    def test_toggle_completed(self, api_server):
        """Frontend can mark a todo as complete."""
        create_resp = api_server.post('/api/todos', json={"title": "Do laundry"})
        todo_id = create_resp.get_json()["id"]
        
        update_resp = api_server.patch(f'/api/todos/{todo_id}', json={"completed": True})
        assert update_resp.status_code == 200
        data = update_resp.get_json()
        assert data["completed"] is True
        
        # Verify in list
        list_resp = api_server.get('/api/todos')
        todos = list_resp.get_json()
        for todo in todos:
            if todo["id"] == todo_id:
                assert todo["completed"] is True
    
    def test_delete_todo(self, api_server):
        """Frontend can delete a todo."""
        create_resp = api_server.post('/api/todos', json={"title": "Old task"})
        todo_id = create_resp.get_json()["id"]
        
        del_resp = api_server.delete(f'/api/todos/{todo_id}')
        assert del_resp.status_code == 204
        
        list_resp = api_server.get('/api/todos')
        assert len(list_resp.get_json()) == 0
    
    def test_add_todo_missing_title_rejected(self, api_server):
        """API rejects todos without title — frontend should handle this."""
        resp = api_server.post('/api/todos', json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
    
    def test_multiple_todos_crud(self, api_server):
        """Full CRUD cycle with multiple todos."""
        # Create multiple
        for title in ["Task A", "Task B", "Task C"]:
            resp = api_server.post('/api/todos', json={"title": title})
            assert resp.status_code == 201
        
        # List should have 3
        list_resp = api_server.get('/api/todos')
        assert len(list_resp.get_json()) == 3
        
        # Update middle one
        todos = list_resp.get_json()
        middle_id = todos[1]["id"]
        update_resp = api_server.patch(f'/api/todos/{middle_id}', json={"completed": True})
        assert update_resp.status_code == 200
        
        # Delete last one
        last_id = list_resp.get_json()[2]["id"]
        del_resp = api_server.delete(f'/api/todos/{last_id}')
        assert del_resp.status_code == 204
        
        # Should have 2 left
        final_list = api_server.get('/api/todos')
        final_data = final_list.get_json()
        assert len(final_data) == 2
