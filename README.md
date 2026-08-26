# Todo List

A web-based todo list application built with Flask (backend) and vanilla JavaScript (frontend). Supports pluggable storage backends — local JSON file for development, Google Sheets for cloud persistence.

## Features

- Create, update, toggle, and delete todos via a clean web UI
- Filter todos: All / Active / Completed
- Pluggable storage backends:
  - **JSON file** — zero-config, perfect for local development
  - **Google Sheets** — cloud persistence via gspread + google-auth
- RESTful JSON API (`/api/todos`)
- Responsive design, works on mobile

## Requirements

- Python 3.10+
- Docker and Docker Compose (for containerized deployment)
- (Optional) A Google account for Google Sheets backend

## Quick Start

### Option A — Run directly

```bash
# Clone the repo
git clone https://github.com/viz6411/todo-list.git
cd todo-list

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server (defaults to JSON storage, port 5000)
python backend/server.py
```

Open http://localhost:5000 in your browser.

### Option B — Docker Compose

```bash
# Clone the repo
git clone https://github.com/viz6411/todo-list.git
cd todo-list

# Build and start
docker compose up --build -d

# The app is available at http://localhost:5000
```

To stop:

```bash
docker compose down
```

## Configuration

### Storage Backend Selection

The app supports two storage backends, selected at startup:

#### JSON File (default)

No configuration needed. Data is stored in `backend/todos.json`.

To customize the storage path, pass `STORAGE_PATH` as an environment variable:

```bash
STORAGE_PATH=/path/to/custom.json python backend/server.py
```

#### Google Sheets

Set the following environment variables:

| Variable | Description |
|---|---|
| `BACKEND_TYPE` | Set to `sheets` to enable Google Sheets backend |
| `SERVICE_ACCOUNT_FILE` | Path to the Google service account JSON key file |
| `SPREADSHEET_ID` | The Google Spreadsheet ID (from the URL) |
| `SHEET_NAME` | Worksheet name (default: `Todos`) |

Example:

```bash
export BACKEND_TYPE=sheets
export SERVICE_ACCOUNT_FILE=/keys/sa.json
export SPREADSHEET_ID=1BxiMVs0XRA5nFMzKZb7ZnKlBbNPDsr
export SHEET_NAME=MyTodos

python backend/server.py
```

### Google Sheets Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Create a **service account** and download the JSON key file
5. Create a Google Spreadsheet and copy its ID from the URL
6. Share the spreadsheet with the service account email (editor access)

## API Reference

All API endpoints return JSON.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/todos` | List all todos |
| `POST` | `/api/todos` | Create a new todo |
| `PATCH` | `/api/todos/<id>` | Update a todo |
| `DELETE` | `/api/todos/<id>` | Delete a todo |

### Create Todo

```bash
curl -X POST http://localhost:5000/api/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy groceries"}'
```

Response (201):

```json
{"id": "a1b2c3d4-...", "title": "Buy groceries", "completed": false}
```

### Update Todo

```bash
curl -X PATCH http://localhost:5000/api/todos/<id> \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

### Delete Todo

```bash
curl -X DELETE http://localhost:5000/api/todos/<id>
```

## Project Structure

```
todo-list/
├── backend/
│   ├── server.py        # Flask app with REST API
│   ├── storage.py       # Pluggable storage backends
│   └── wsgi.py          # WSGI entry point
├── frontend/
│   ├── index.html       # Web UI
│   ├── css/style.css    # Styles
│   └── js/app.js        # Frontend logic
├── tests/               # pytest test suite
├── requirements.txt     # Python dependencies
├── docker-compose.yml   # Docker Compose configuration
├── Dockerfile           # Multi-stage Docker build
└── wsgi.py              # Root-level WSGI entry point
```

## Running Tests

```bash
# With virtual environment activated:
pytest tests/ -v

# Or via Docker:
docker compose run --rm app pytest tests/ -v
```

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `BACKEND_TYPE` | `json` | Storage backend: `json` or `sheets` |
| `STORAGE_PATH` | `backend/todos.json` | Path to the JSON storage file |
| `SERVICE_ACCOUNT_FILE` | — | Path to Google service account JSON key |
| `SPREADSHEET_ID` | — | Google Spreadsheet ID |
| `SHEET_NAME` | `Todos` | Worksheet name |

## License

MIT
