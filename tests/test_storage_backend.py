"""Tests for storage backend abstraction: JSONFileBackend and GoogleSheetsBackend."""
import pytest
import os
import sys
import tempfile
import shutil

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def json_storage_path(tmp_path):
    """A temporary file path for JSON backend tests."""
    return str(tmp_path / 'todos.json')


@pytest.fixture
def json_backend(json_storage_path):
    """A JSONFileBackend instance with a fresh temp file."""
    from storage import JSONFileBackend
    return JSONFileBackend(json_storage_path)


class TestJSONFileBackend:
    """Test the JSON file-based storage backend."""

    def test_load_empty_when_file_missing(self, json_backend):
        """load_todos should return [] when the file does not exist."""
        todos = json_backend.load_todos()
        assert todos == []

    def test_save_and_load_roundtrip(self, json_backend):
        """save_todos then load_todos should return the same data."""
        todos = [
            {"id": "a1", "title": "First", "completed": False},
            {"id": "a2", "title": "Second", "completed": True},
        ]
        json_backend.save_todos(todos)
        loaded = json_backend.load_todos()
        assert len(loaded) == 2
        assert loaded[0]["title"] == "First"
        assert loaded[0]["completed"] is False
        assert loaded[1]["title"] == "Second"
        assert loaded[1]["completed"] is True

    def test_save_overwrites_previous(self, json_backend):
        """Saving a new list should replace the old data."""
        json_backend.save_todos([{"id": "x", "title": "Old", "completed": False}])
        json_backend.save_todos([{"id": "y", "title": "New", "completed": True}])
        loaded = json_backend.load_todos()
        assert len(loaded) == 1
        assert loaded[0]["title"] == "New"


class TestGoogleSheetsBackend:
    """Test the Google Sheets storage backend (mocked)."""

    @pytest.fixture
    def mock_gspread(self, mocker):
        """Mock gspread and credentials for testing without real API calls."""
        gs_mock = mocker.patch('storage.gspread')
        mocker.patch('storage.ServiceCredentials')
        return gs_mock

    @pytest.fixture
    def sheets_backend(self, mock_gspread, mocker):
        """A GoogleSheetsBackend instance with mocked gspread."""
        # Make from_service_account_file return a mock credentials
        mocker.patch('storage.ServiceCredentials').from_service_account_file.return_value = mocker.Mock()
        from storage import GoogleSheetsBackend
        return GoogleSheetsBackend(
            service_account_file='/tmp/fake_sa.json',
            spreadsheet_id='fake-spreadsheet-id',
            sheet_name='Todos'
        )

    def test_init_creates_sheet_if_missing(self, mock_gspread, mocker):
        """__init__ should create the sheet if it does not exist."""
        from storage import GoogleSheetsBackend
        from gspread.exceptions import WorksheetNotFound
        # Configure mocks BEFORE constructing the backend so _initialize()
        # sees the right behaviour.
        mocker.patch('storage.ServiceCredentials').from_service_account_file.return_value = mocker.Mock()
        gc_mock = mock_gspread.authorize.return_value
        sp_mock = gc_mock.open_by_id.return_value
        sp_mock.worksheet.side_effect = WorksheetNotFound('Sheet not found')

        GoogleSheetsBackend(
            service_account_file='/tmp/fake_sa.json',
            spreadsheet_id='fake-spreadsheet-id',
            sheet_name='Todos',
        )
        sp_mock.add_worksheet.assert_called_once()

    def test_load_todos_empty_sheet(self, sheets_backend, mock_gspread):
        """load_todos on an empty sheet returns []."""
        gc_mock = mock_gspread.authorize.return_value
        sp_mock = gc_mock.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value
        ws_mock.get_all_records.return_value = []

        todos = sheets_backend.load_todos()
        assert todos == []

    def test_load_todos_with_data(self, sheets_backend, mock_gspread):
        """load_todos should return todos from sheet records."""
        gc_mock = mock_gspread.authorize.return_value
        sp_mock = gc_mock.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value
        ws_mock.get_all_records.return_value = [
            {"id": "t1", "title": "Todo 1", "completed": False},
            {"id": "t2", "title": "Todo 2", "completed": True},
        ]

        todos = sheets_backend.load_todos()
        assert len(todos) == 2
        assert todos[0]["title"] == "Todo 1"
        assert todos[1]["completed"] is True

    def test_save_todos_writes_rows(self, sheets_backend, mock_gspread):
        """save_todos should clear and write rows to the sheet."""
        gc_mock = mock_gspread.authorize.return_value
        sp_mock = gc_mock.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value

        todos = [
            {"id": "a1", "title": "First", "completed": False},
            {"id": "a2", "title": "Second", "completed": True},
        ]
        sheets_backend.save_todos(todos)

        ws_mock.update.assert_called_once()
        # Verify the data passed to update
        call_args = ws_mock.update.call_args
        data = call_args[0][0]
        assert data[0] == ["id", "title", "completed"]  # header row
        assert data[1][0] == "a1"
        assert data[1][1] == "First"
        assert data[2][1] == "Second"

    def test_save_todos_empty_list(self, sheets_backend, mock_gspread):
        """save_todos with empty list should write only header."""
        gc_mock = mock_gspread.authorize.return_value
        sp_mock = gc_mock.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value

        sheets_backend.save_todos([])

        call_args = ws_mock.update.call_args
        data = call_args[0][0]
        assert len(data) == 1  # only header
        assert data[0] == ["id", "title", "completed"]


class TestStorageBackendInterface:
    """Test that both backends satisfy the StorageBackend interface."""

    def test_json_backend_has_required_methods(self, json_backend):
        """JSONFileBackend must have load_todos and save_todos."""
        assert hasattr(json_backend, 'load_todos')
        assert hasattr(json_backend, 'save_todos')
        assert callable(json_backend.load_todos)
        assert callable(json_backend.save_todos)

    def test_sheets_backend_has_required_methods(self, mocker):
        """GoogleSheetsBackend must have load_todos and save_todos."""
        mocker.patch('storage.gspread')
        mocker.patch('storage.ServiceCredentials').from_service_account_file.return_value = mocker.Mock()
        from storage import GoogleSheetsBackend
        backend = GoogleSheetsBackend(
            service_account_file='/tmp/fake.json',
            spreadsheet_id='fake-id',
            sheet_name='Todos'
        )
        assert hasattr(backend, 'load_todos')
        assert hasattr(backend, 'save_todos')
        assert callable(backend.load_todos)
        assert callable(backend.save_todos)
