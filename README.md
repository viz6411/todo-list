# Todo List

A Flask-based todo list application with a web frontend, pluggable storage backends (local JSON file or Google Sheets), and a CI/CD pipeline.

## Features

- **REST API** — CRUD operations for todos via `/api/todos`
- **Web frontend** — Browser-based interface at `/`
- **Pluggable storage** — Local JSON file (default) or Google Sheets via service account
- **Settings management** — Persisted settings with `/api/settings` for backend configuration
- **Auto-backend selection** — Automatically uses Google Sheets when valid credentials are found
- **CI/CD** — GitHub Actions run linting (flake8) and tests (pytest) on every push

## Getting Started

```bash
pip install -r requirements.txt
python app.py
```

The app starts on `http://localhost:5000`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/todos` | List all todos |
| POST | `/api/todos` | Create a new todo (`{"title": "..."}`) |
| PATCH | `/api/todos/<id>` | Update a todo (`{"title": "...", "completed": true}`) |
| DELETE | `/api/todos/<id>` | Delete a todo |
| GET | `/api/settings` | Get current settings |
| POST | `/api/settings` | Save settings (`{"spreadsheet_id": "...", "service_account_file": "..."}`) |

## Storage Backends

- **JSON file** (default) — Todos stored in `backend/todos.json`
- **Google Sheets** — Set via `/api/settings` POST with `spreadsheet_id` and `service_account_file` paths

When settings contain valid Google Sheets credentials, the app auto-selects the Sheets backend on startup.

## Testing

```bash
pytest tests/ -v
```

71 tests cover API logic, frontend integration, settings management, and storage backends.

## CI/CD

GitHub Actions runs on every push to `main`:
1. Linting with flake8
2. Tests with pytest

## License

MIT
