"""Storage backends for the todo-list app.

Provides a uniform interface for persisting todos:
- JSONFileBackend: file-based JSON storage (default, for local dev)
- GoogleSheetsBackend: Google Sheets API via gspread + google-auth

Both backends expose load_todos() and save_todos() methods.
"""
import json
import os

import gspread
from gspread.exceptions import GSpreadException, WorksheetNotFound
from google.oauth2.service_account import Credentials as ServiceCredentials


COLUMNS = ["id", "title", "completed"]


class JSONFileBackend:
    """Read/write todos from a local JSON file."""

    def __init__(self, storage_path: str):
        self._path = storage_path

    def load_todos(self) -> list[dict]:
        if os.path.exists(self._path):
            with open(self._path, 'r') as f:
                content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
        return []

    def save_todos(self, todos: list[dict]) -> None:
        with open(self._path, 'w') as f:
            json.dump(todos, f, indent=2)


class GoogleSheetsBackend:
    """Read/write todos from a Google Sheet.

    Args:
        service_account_file: Path to the Google service account JSON key.
        spreadsheet_id: The Google Spreadsheet ID.
        sheet_name: Name of the worksheet to store todos in.
    """

    def __init__(
        self,
        service_account_file: str,
        spreadsheet_id: str,
        sheet_name: str = "Todos",
    ):
        self._service_account_file = service_account_file
        self._spreadsheet_id = spreadsheet_id
        self._sheet_name = sheet_name
        self._worksheet = None

        self._initialize()

    def _initialize(self) -> None:
        """Authenticate and ensure the sheet exists."""
        credentials = ServiceCredentials.from_service_account_file(
            self._service_account_file,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        gc = gspread.authorize(credentials)

        try:
            spreadsheet = gc.open_by_id(self._spreadsheet_id)
        except GSpreadException as exc:
            raise RuntimeError(f"Cannot open spreadsheet {self._spreadsheet_id}: {exc}") from exc

        # Ensure the worksheet exists
        try:
            self._worksheet = spreadsheet.worksheet(self._sheet_name)
        except WorksheetNotFound:
            self._worksheet = spreadsheet.add_worksheet(
                self._sheet_name, rows="100", cols="3"
            )

    def load_todos(self) -> list[dict]:
        """Load all todos from the sheet."""
        records = self._worksheet.get_all_records()
        # gspread returns string values; coerce completed to bool
        todos = []
        for rec in records:
            todo = {
                "id": rec.get("id", ""),
                "title": rec.get("title", ""),
                "completed": bool(rec.get("completed", False)),
            }
            todos.append(todo)
        return todos

    def save_todos(self, todos: list[dict]) -> None:
        """Write all todos to the sheet, replacing existing data."""
        rows = [COLUMNS]  # header row
        for todo in todos:
            rows.append([
                todo["id"],
                todo["title"],
                todo["completed"],
            ])
        self._worksheet.update(rows)


def create_backend(backend_type: str = "json", **kwargs):
    """Factory to create the appropriate storage backend.

    Args:
        backend_type: 'json' or 'sheets'.
        **kwargs: Passed to the backend constructor.
            - json: storage_path
            - sheets: service_account_file, spreadsheet_id, sheet_name
    """
    if backend_type == "json":
        storage_path = kwargs.get("storage_path")
        if storage_path is None:
            storage_path = os.path.join(
                os.path.dirname(__file__), "todos.json"
            )
        return JSONFileBackend(storage_path)
    elif backend_type == "sheets":
        return GoogleSheetsBackend(
            service_account_file=kwargs["service_account_file"],
            spreadsheet_id=kwargs["spreadsheet_id"],
            sheet_name=kwargs.get("sheet_name", "Todos"),
        )
    else:
        raise ValueError(f"Unknown backend_type: {backend_type!r}")
