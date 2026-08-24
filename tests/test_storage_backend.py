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
        # gspread returns all cell values as strings
        ws_mock.get_all_records.return_value = [
            {"id": "t1", "title": "Todo 1", "completed": "False"},
            {"id": "t2", "title": "Todo 2", "completed": "True"},
        ]

        todos = sheets_backend.load_todos()
        assert len(todos) == 2
        assert todos[0]["title"] == "Todo 1"
        assert todos[0]["completed"] is False  # "False" string -> False
        assert todos[1]["completed"] is True   # "True" string -> True

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

    def test_load_todos_completed_coercion_various_strings(self, sheets_backend, mock_gspread):
        """load_todos should coerce various string representations of completed."""
        gc_mock = mock_gspread.authorize.return_value
        sp_mock = gc_mock.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value
        ws_mock.get_all_records.return_value = [
            {"id": "c1", "title": "A", "completed": "True"},
            {"id": "c2", "title": "B", "completed": "1"},
            {"id": "c3", "title": "C", "completed": "yes"},
            {"id": "c4", "title": "D", "completed": "False"},
            {"id": "c5", "title": "E", "completed": "0"},
            {"id": "c6", "title": "F", "completed": "no"},
        ]

        todos = sheets_backend.load_todos()
        assert todos[0]["completed"] is True   # "True"
        assert todos[1]["completed"] is True   # "1"
        assert todos[2]["completed"] is True   # "yes"
        assert todos[3]["completed"] is False  # "False"
        assert todos[4]["completed"] is False  # "0"
        assert todos[5]["completed"] is False  # "no"

    def test_save_and_load_roundtrip(self, sheets_backend, mock_gspread):
        """Full roundtrip: save_todos writes to sheet, load_todos reads back.

        gspread returns all cell values as strings, so booleans written as
        True/False become 'True'/'False' strings on read-back. The coercion
        in load_todos converts them back to proper booleans.

        The mock is wired so that rows captured by save_todos (via update)
        are fed back through get_all_records as string-valued dicts —
        simulating real gspread behaviour — and then load_todos reads them.
        """
        gc_mock = mock_gspread.authorize.return_value
        sp_mock = gc_mock.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value

        # Shared state between save and load: save_todos calls update(rows),
        # and load_todos calls get_all_records() which returns the saved rows.
        saved_rows = []

        def capture_update(rows):
            """save_todos calls ws.update(rows) — capture the rows."""
            saved_rows[:] = rows

        def fake_get_all_records():
            """load_todos calls ws.get_all_records() — return saved rows as strings."""
            if len(saved_rows) <= 1:
                return []
            header = saved_rows[0]
            return [dict(zip(header, row)) for row in saved_rows[1:]]

        ws_mock.update.side_effect = capture_update
        ws_mock.get_all_records.side_effect = fake_get_all_records

        # --- STEP 1: save ---
        input_todos = [
            {"id": "r1", "title": "Roundtrip", "completed": False},
            {"id": "r2", "title": "Done", "completed": True},
        ]
        sheets_backend.save_todos(input_todos)

        # --- STEP 2: load ---
        loaded = sheets_backend.load_todos()

        # --- STEP 3: verify roundtrip ---
        assert len(loaded) == 2
        assert loaded[0]["id"] == "r1"
        assert loaded[0]["title"] == "Roundtrip"
        assert loaded[0]["completed"] is False
        assert loaded[1]["id"] == "r2"
        assert loaded[1]["title"] == "Done"
        assert loaded[1]["completed"] is True

    def test_init_fails_on_spreadsheet_error(self, mocker):
        """__init__ should raise RuntimeError when spreadsheet cannot be opened."""
        mocker.patch('storage.ServiceCredentials').from_service_account_file.return_value = mocker.Mock()
        from gspread.exceptions import GSpreadException
        gs_mock = mocker.patch('storage.gspread')
        gc_mock = gs_mock.authorize.return_value
        gc_mock.open_by_id.side_effect = GSpreadException("Access denied")

        import pytest
        with pytest.raises(RuntimeError, match="Cannot open spreadsheet"):
            from storage import GoogleSheetsBackend
            GoogleSheetsBackend(
                service_account_file='/tmp/fake_sa.json',
                spreadsheet_id='bad-id',
                sheet_name='Todos',
            )

    def test_load_todos_handles_missing_fields(self, sheets_backend, mock_gspread):
        """load_todos should handle records with missing columns gracefully."""
        gc_mock = mock_gspread.authorize.return_value
        sp_mock = gc_mock.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value
        ws_mock.get_all_records.return_value = [
            {"id": "m1", "title": "Has all fields", "completed": "False"},
            {"id": "m2"},  # missing title and completed
            {"title": "No ID", "completed": "True"},  # missing id
        ]

        todos = sheets_backend.load_todos()
        assert len(todos) == 3
        assert todos[0]["completed"] is False
        assert todos[1]["title"] == ""
        assert todos[1]["completed"] is False
        assert todos[2]["id"] == ""
        assert todos[2]["completed"] is True


    def test_create_backend_sheets_type(self, mocker):
        """create_backend with backend_type='sheets' should return GoogleSheetsBackend."""
        mocker.patch('storage.gspread')
        mocker.patch('storage.ServiceCredentials').from_service_account_file.return_value = mocker.Mock()
        from storage import create_backend, GoogleSheetsBackend
        backend = create_backend(
            backend_type='sheets',
            service_account_file='/tmp/fake.json',
            spreadsheet_id='fake-id',
        )
        assert isinstance(backend, GoogleSheetsBackend)

    def test_create_backend_invalid_type_raises(self):
        """create_backend with unknown type should raise ValueError."""
        from storage import create_backend
        import pytest
        with pytest.raises(ValueError, match="Unknown backend_type"):
            create_backend(backend_type='invalid')


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
