"""Todo-list backend API with pluggable storage backend and frontend."""
import os
import sys
import uuid
from flask import Flask, jsonify, request, send_from_directory

# Support both `from backend.server import ...` and `from server import ...`
try:
    from .storage import create_backend
except ImportError:
    # Fallback: run as top-level module (e.g. old tests do `from server import ...`)
    _here = os.path.dirname(__file__)
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from storage import create_backend


def create_app(backend_type="json", **backend_kwargs):
    """Create and configure the Flask app.

    Args:
        backend_type: 'json' (default) or 'sheets'.
            For backward compatibility, passing a path ending in .json is
            treated as the old-style storage_path argument.
        **backend_kwargs: Keyword args forwarded to the backend factory.
            - json: storage_path
            - sheets: service_account_file, spreadsheet_id, sheet_name
    """
    # Legacy: create_app("/path/to/todos.json")
    if isinstance(backend_type, str) and backend_type.endswith(".json"):
        backend_kwargs.setdefault("storage_path", backend_type)
        backend_type = "json"

    if backend_type == "json":
        storage_path = backend_kwargs.pop("storage_path", None)
        if storage_path is None:
            storage_path = os.path.join(os.path.dirname(__file__), "todos.json")
        backend_kwargs["storage_path"] = storage_path

    storage = create_backend(backend_type, **backend_kwargs)

    # Frontend static files live in ../frontend relative to this file
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')

    app = Flask(__name__, static_folder=frontend_dir, static_url_path='/static')

    @app.route('/api/todos', methods=['GET'])
    def get_todos():
        todos = storage.load_todos()
        return jsonify(todos), 200

    @app.route('/api/todos', methods=['POST'])
    def create_todo():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "title is required"}), 400
        title = data.get("title", "")
        if not title or not str(title).strip():
            return jsonify({"error": "title is required and cannot be empty"}), 400

        todo = {
            "id": str(uuid.uuid4()),
            "title": str(title).strip(),
            "completed": False
        }
        todos = storage.load_todos()
        todos.append(todo)
        storage.save_todos(todos)
        return jsonify(todo), 201

    @app.route('/api/todos/<todo_id>', methods=['PATCH'])
    def update_todo(todo_id):
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "invalid or missing JSON body"}), 400
        todos = storage.load_todos()
        for todo in todos:
            if todo["id"] == todo_id:
                if "title" in data:
                    todo["title"] = data["title"]
                if "completed" in data:
                    todo["completed"] = data["completed"]
                storage.save_todos(todos)
                return jsonify(todo), 200
        return jsonify({"error": "not found"}), 404

    @app.route('/api/todos/<todo_id>', methods=['DELETE'])
    def delete_todo(todo_id):
        todos = storage.load_todos()
        filtered = [t for t in todos if t["id"] != todo_id]
        if len(filtered) == len(todos):
            return jsonify({"error": "not found"}), 404
        storage.save_todos(filtered)
        return '', 204

    @app.route('/')
    def index():
        return send_from_directory(frontend_dir, 'index.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
