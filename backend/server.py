"""Todo-list backend API with file-based JSON storage."""
import json
import os
import uuid
from flask import Flask, jsonify, request


def create_app(storage_path=None):
    """Create and configure the Flask app."""
    if storage_path is None:
        storage_path = os.path.join(os.path.dirname(__file__), 'todos.json')

    app = Flask(__name__)
    app.config['STORAGE_PATH'] = storage_path

    def load_todos():
        if os.path.exists(storage_path):
            with open(storage_path, 'r') as f:
                return json.load(f)
        return []

    def save_todos(todos):
        with open(storage_path, 'w') as f:
            json.dump(todos, f, indent=2)

    @app.route('/api/todos', methods=['GET'])
    def get_todos():
        todos = load_todos()
        return jsonify(todos), 200

    @app.route('/api/todos', methods=['POST'])
    def create_todo():
        data = request.get_json()
        if not data or 'title' not in data:
            return jsonify({"error": "title is required"}), 400

        todo = {
            "id": str(uuid.uuid4()),
            "title": data["title"],
            "completed": False
        }
        todos = load_todos()
        todos.append(todo)
        save_todos(todos)
        return jsonify(todo), 201

    @app.route('/api/todos/<todo_id>', methods=['PATCH'])
    def update_todo(todo_id):
        data = request.get_json()
        todos = load_todos()
        for todo in todos:
            if todo["id"] == todo_id:
                if "title" in data:
                    todo["title"] = data["title"]
                if "completed" in data:
                    todo["completed"] = data["completed"]
                save_todos(todos)
                return jsonify(todo), 200
        return jsonify({"error": "not found"}), 404

    @app.route('/api/todos/<todo_id>', methods=['DELETE'])
    def delete_todo(todo_id):
        todos = load_todos()
        filtered = [t for t in todos if t["id"] != todo_id]
        if len(filtered) == len(todos):
            return jsonify({"error": "not found"}), 404
        save_todos(filtered)
        return '', 204

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
