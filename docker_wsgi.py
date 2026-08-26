"""Container WSGI entry point — reads backend config from environment variables."""
import os
import sys

# Add backend dir to path so `from server import ...` works
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from server import create_app

backend_type = os.environ.get("BACKEND_TYPE", "json")
storage_path = os.environ.get("STORAGE_PATH", os.path.join(_backend_dir, "todos.json"))

if backend_type == "json":
    app = create_app(backend_type="json", storage_path=storage_path)
elif backend_type == "sheets":
    service_account_file = os.environ.get("SERVICE_ACCOUNT_FILE", "")
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "")
    sheet_name = os.environ.get("SHEET_NAME", "Todos")
    app = create_app(
        backend_type="sheets",
        service_account_file=service_account_file,
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
    )
else:
    raise ValueError(f"Unknown BACKEND_TYPE: {backend_type!r}")
