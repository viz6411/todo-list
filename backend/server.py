"""Todo-list backend API with pluggable storage backend and frontend."""
import logging
import os
import sys
import uuid
from flask import Flask, jsonify, request, send_from_directory

logger = logging.getLogger(__name__)

# Support both `from backend.server import ...` and `from server import ...`
try:
    from .storage import create_backend
    from .settings import SettingsManager
except ImportError:
    # Fallback: run as top-level module (e.g. old tests do `from server import ...`)
    _here = os.path.dirname(__file__)
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from storage import create_backend
    from settings import SettingsManager


def create_app(backend_type=None, **backend_kwargs):
    """Create and configure the Flask app.

    Args:
        backend_type: 'json' (default) or 'sheets'.
            When None (the default), the app checks persisted settings and
            auto-selects 'sheets' if valid credentials are found.  Pass an
            explicit value to disable auto-selection.
            For backward compatibility, passing a path ending in .json is
            treated as the old-style storage_path argument.
        **backend_kwargs: Keyword args forwarded to the backend factory.
            - json: storage_path
            - sheets: service_account_file, spreadsheet_id, sheet_name
            - settings_path: path to the settings JSON file (optional)
    """
    # Legacy: create_app("/path/to/todos.json")
    if isinstance(backend_type, str) and backend_type.endswith(".json"):
        backend_kwargs.setdefault("storage_path", backend_type)
        backend_type = "json"

    # Extract settings_path before passing to backend factory
    settings_path = backend_kwargs.pop("settings_path", None)
    if settings_path is None:
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
    settings_mgr = SettingsManager(settings_path)

    # Auto-select backend only when backend_type is not explicitly set
    if backend_type is None:
        persisted = settings_mgr.load()
        if persisted.get("spreadsheet_id") and persisted.get("service_account_file"):
            backend_type = "sheets"
            backend_kwargs.setdefault("spreadsheet_id", persisted["spreadsheet_id"])
            backend_kwargs.setdefault("service_account_file", persisted["service_account_file"])

            # Try to initialize sheets backend; fall back to json on failure
            try:
                storage = create_backend(backend_type, **backend_kwargs)
            except Exception:
                logger.warning(
                    "Auto-selection of Google Sheets backend failed; "
                    "falling back to JSON backend. Error: %s",
                    str(sys.exc_info()[1]),
                )
                backend_type = "json"
                backend_kwargs.pop("spreadsheet_id", None)
                backend_kwargs.pop("service_account_file", None)

                storage_path = backend_kwargs.pop("storage_path", None)
                if storage_path is None:
                    storage_path = os.path.join(os.path.dirname(__file__), "todos.json")
                backend_kwargs["storage_path"] = storage_path

                storage = create_backend(backend_type, **backend_kwargs)
    else:
        # backend_type was explicitly set — use it directly
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

    @app.route('/api/settings', methods=['GET'])
    def get_settings():
        config = settings_mgr.load()
        return jsonify(config), 200

    @app.route('/api/settings', methods=['POST'])
    def save_settings():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "invalid or missing JSON body"}), 400
        settings_mgr.save(data)
        return jsonify(settings_mgr.load()), 200

    @app.route('/')
    def index():
        return send_from_directory(frontend_dir, 'index.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
