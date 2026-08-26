"""Storage backends for the todo-list app.

Provides a uniform interface for persisting todos:
- JSONFileBackend: file-based JSON storage (default, for local dev)
- GoogleSheetsBackend: Google Sheets API via OAuth2 or service account

Both backends expose load_todos() and save_todos() methods.
"""
import json
import os
import tempfile

import gspread
from gspread.exceptions import GSpreadException, WorksheetNotFound
from google.oauth2.service_account import Credentials as ServiceCredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request as AuthRequest
from google_auth_oauthlib.flow import InstalledAppFlow

# Support both package import (backend.storage) and direct import (storage)
try:
    from . import encryption
except ImportError:
    import encryption

COLUMNS = ["id", "title", "completed"]


class GoogleSheetsBackend:
    """Read/write todos from a Google Sheet.

    Args:
        oauth_credentials: OAuth2 credentials dict or token file path.
            When provided, uses OAuth2 (regular Google account) auth.
        service_account_file: Path to the Google service account JSON key.
            Legacy auth mode — still supported for backward compatibility.
        service_account_credentials: Service account credentials dict.
            Alternative to service_account_file.
        spreadsheet_id: The Google Spreadsheet ID.
        sheet_name: Name of the worksheet to store todos in.
    """

    def __init__(
        self,
        oauth_credentials=None,
        service_account_file=None,
        service_account_credentials=None,
        spreadsheet_id=None,
        sheet_name="Todos",
    ):
        self._oauth_credentials = oauth_credentials
        self._service_account_file = service_account_file
        self._service_account_credentials = service_account_credentials
        self._spreadsheet_id = spreadsheet_id
        self._sheet_name = sheet_name
        self._worksheet = None
        self._credentials = None
        self._temp_files = []

        # Determine auth mode
        if oauth_credentials:
            self._auth_mode = "oauth"
        elif service_account_file or service_account_credentials:
            self._auth_mode = "service_account"
        else:
            raise ValueError(
                "Must provide either oauth_credentials or "
                "service_account_file/service_account_credentials"
            )

        self._initialize()

    def __del__(self):
        """Clean up temporary decrypted files."""
        for path in self._temp_files:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass
        self._temp_files.clear()

    def _decrypt_file(self, path: str) -> str:
        """Detect .encrypted files, decrypt to temp location, return path."""
        if not path.endswith(".encrypted"):
            return path

        key_path = os.path.join(os.path.dirname(path), ".encryption_key")
        if not os.path.exists(key_path):
            raise FileNotFoundError(
                f"Encrypted credential {path} requires key at {key_path}"
            )

        key = encryption.load_encryption_key(key_path)
        encrypted_data = open(path, "rb").read()
        plaintext = encryption.decrypt(key, encrypted_data)

        temp_path = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        )
        temp_path.write(plaintext)
        temp_path.close()
        self._temp_files.append(temp_path.name)
        return temp_path.name

    def _initialize(self) -> None:
        """Authenticate and ensure the sheet exists."""
        if self._auth_mode == "oauth":
            self._init_oauth()
        else:
            self._init_service_account()

        # Open spreadsheet
        try:
            spreadsheet = self._gc.open_by_id(self._spreadsheet_id)
        except GSpreadException as exc:
            raise RuntimeError(
                f"Cannot open spreadsheet {self._spreadsheet_id}: {exc}"
            ) from exc

        # Ensure the worksheet exists
        try:
            self._worksheet = spreadsheet.worksheet(self._sheet_name)
        except WorksheetNotFound:
            self._worksheet = spreadsheet.add_worksheet(
                self._sheet_name, rows="100", cols="3"
            )

    def _init_oauth(self) -> None:
        """Authenticate using OAuth2 credentials."""
        creds = self._oauth_credentials
        if isinstance(creds, str):
            # Load token from file path (may be encrypted)
            creds_path = self._decrypt_file(creds)
            with open(creds_path) as f:
                creds = json.load(f)

        # Build credentials object
        self._credentials = OAuthCredentials(
            token=creds.get("access_token", ""),
            refresh_token=creds.get("refresh_token", ""),
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
            token_uri="https://oauth2.googleapis.com/token",
        )

        # Refresh if expired
        if self._credentials.expired:
            self._credentials.refresh(AuthRequest())

        self._gc = gspread.authorize(self._credentials)

    def _init_service_account(self) -> None:
        """Authenticate using service account credentials."""
        if self._service_account_file:
            # Detect .encrypted credential files, decrypt to temp
            cred_path = self._decrypt_file(self._service_account_file)
            credentials = ServiceCredentials.from_service_account_file(
                cred_path,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
        elif self._service_account_credentials:
            credentials = ServiceCredentials.from_service_account_info(
                self._service_account_credentials,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
        else:
            raise ValueError("No service account credentials provided")

        self._credentials = credentials
        self._gc = gspread.authorize(credentials)

    def load_todos(self) -> list[dict]:
        """Load all todos from the sheet."""
        records = self._worksheet.get_all_records()
        todos = []
        for rec in records:
            todo = {
                "id": rec.get("id", ""),
                "title": rec.get("title", ""),
                "completed": str(rec.get("completed", "False")).lower()
                in ("true", "1", "yes"),
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
            - sheets: oauth_credentials, service_account_file,
              service_account_credentials, spreadsheet_id, sheet_name
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
            oauth_credentials=kwargs.get("oauth_credentials"),
            service_account_file=kwargs.get("service_account_file"),
            service_account_credentials=kwargs.get(
                "service_account_credentials"
            ),
            spreadsheet_id=kwargs["spreadsheet_id"],
            sheet_name=kwargs.get("sheet_name", "Todos"),
        )
    else:
        raise ValueError(f"Unknown backend_type: {backend_type!r}")


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
