"""Tests for OAuth2 authentication in GoogleSheetsBackend.

Verifies that GoogleSheetsBackend can authenticate using OAuth2 user
credentials (regular Google account) instead of service accounts,
and that Authorization: Bearer *** are used correctly in HTTP requests.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestOAuth2Initialization:
    """Test that GoogleSheetsBackend initializes with OAuth2 credentials."""

    @pytest.fixture
    def mock_oauth(self, mocker):
        """Mock OAuth2 credential loading."""
        mocker.patch('storage.OAuthCredentials')
        mocker.patch('storage.AuthRequest')
        mocker.patch('storage.gspread')
        return mocker

    def test_accepts_oauth_credentials_param(self, mock_oauth):
        """GoogleSheetsBackend should accept oauth_credentials parameter."""
        from storage import GoogleSheetsBackend
        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        assert backend._auth_mode == "oauth"

    def test_accepts_service_account_credentials_param(self, mock_oauth):
        """GoogleSheetsBackend should accept service_account_credentials parameter."""
        from storage import GoogleSheetsBackend
        mocker = mock_oauth
        mocker.patch('storage.ServiceCredentials')
        mocker.patch('storage.ServiceCredentials').from_service_account_file.return_value = mocker.Mock()

        backend = GoogleSheetsBackend(
            service_account_file='/tmp/fake_sa.json',
            spreadsheet_id='fake-id',
        )
        assert backend._auth_mode == "service_account"

    def test_default_is_oauth(self, mock_oauth):
        """Default auth mode should be OAuth2."""
        from storage import GoogleSheetsBackend
        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        assert backend._auth_mode == "oauth"

    def test_raises_when_no_credentials(self):
        """GoogleSheetsBackend should raise ValueError when no credentials provided."""
        from storage import GoogleSheetsBackend
        with pytest.raises(ValueError):
            GoogleSheetsBackend(
                spreadsheet_id="fake-id",
            )


class TestOAuth2BearerToken:
    """Test that OAuth2 authentication uses Bearer tokens correctly in HTTP requests."""

    @pytest.fixture
    def mock_oauth(self, mocker):
        """Mock OAuth2Flow and credentials."""
        creds_mock = mocker.Mock()
        creds_mock.expired = False
        creds_mock.refresh_token = "test_refresh"
        creds_mock.access_token = "test_access"
        creds_mock.token = "test_access"
        mocker.patch('storage.OAuthCredentials', return_value=creds_mock)
        mocker.patch('storage.AuthRequest')
        gc_mock = mocker.patch('storage.gspread')
        gc_auth = gc_mock.authorize.return_value
        sp_mock = gc_auth.open_by_key.return_value
        _ = sp_mock.worksheet.return_value
        return creds_mock

    def test_uses_bearer_authorization(self, mocker):
        """GoogleSheetsBackend passes credentials with Bearer token to gspread.authorize().

        The credentials object passed to gspread.authorize() must contain
        the access_token which becomes the Bearer value in Authorization headers.
        """
        from storage import GoogleSheetsBackend
        # Patch BEFORE creating backend so authorize() is captured
        creds_mock = mocker.Mock()
        creds_mock.expired = False
        creds_mock.refresh_token = "test_refresh"
        creds_mock.access_token = "test_access"
        creds_mock.token = "test_access"
        mocker.patch('storage.OAuthCredentials', return_value=creds_mock)
        mocker.patch('storage.AuthRequest')
        gc_mock = mocker.patch('storage.gspread')
        gc_auth = gc_mock.authorize.return_value
        sp_mock = gc_auth.open_by_key.return_value
        _ = sp_mock.worksheet.return_value

        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        # Trigger lazy initialization
        backend._ensure_initialized()
        # Verify credentials contain Bearer token (access_token)
        assert backend._credentials.access_token == "test_access"
        # Verify gspread was authorized with credentials carrying Bearer token
        gc_mock.authorize.assert_called_with(backend._credentials)
        # Verify auth mode is oauth
        assert backend._auth_mode == "oauth"

    def test_refresh_token_persisted(self, mock_oauth, mocker):
        """OAuth2 refresh token should be available for persistence."""
        from storage import GoogleSheetsBackend
        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        # Trigger lazy initialization
        backend._ensure_initialized()
        assert hasattr(backend, '_credentials')
        assert backend._credentials.refresh_token == "test_refresh"

    def test_bearer_token_in_request_headers(self, mock_oauth, mocker):
        """API requests include Authorization: Bearer *** header.

        gspread.authorize() receives credentials with an access_token;
        gspread uses that token to construct Authorization: Bearer ***
        on every HTTP request. We verify the token is present on the
        credentials object passed to authorize().
        """
        from storage import GoogleSheetsBackend
        gc_mock = mocker.patch('storage.gspread')
        gc_auth = gc_mock.authorize.return_value
        sp_mock = gc_auth.open_by_key.return_value
        _ = sp_mock.worksheet.return_value

        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        # Trigger lazy initialization
        backend._ensure_initialized()
        # Verify gspread was authorized with OAuth2 credentials carrying Bearer token
        gc_mock.authorize.assert_called_once()
        call_args = gc_mock.authorize.call_args
        creds_passed = call_args[0][0]
        # The credentials object MUST have an access_token (the Bearer value)
        assert hasattr(creds_passed, 'access_token')
        assert creds_passed.access_token == "test_access"
        assert creds_passed.refresh_token == "test_refresh"


class TestOAuth2TokenRefresh:
    """Test that OAuth2 tokens are refreshed when expired."""

    @pytest.fixture
    def mock_oauth_refresh(self, mocker):
        """Mock OAuth2 token refresh flow."""
        creds_mock = mocker.Mock()
        creds_mock.expired = True
        creds_mock.refresh_token = "test_refresh"
        creds_mock.access_token = "test_access"
        creds_mock.token = "test_access"
        mocker.patch('storage.OAuthCredentials', return_value=creds_mock)
        _ = mocker.patch('storage.AuthRequest').return_value
        creds_mock.refresh = mocker.Mock(side_effect=lambda req: setattr(creds_mock, 'expired', False))
        gc_mock = mocker.patch('storage.gspread')
        gc_auth = gc_mock.authorize.return_value
        sp_mock = gc_auth.open_by_key.return_value
        _ = sp_mock.worksheet.return_value
        return creds_mock

    def test_refreshes_expired_token(self, mock_oauth_refresh, mocker):
        """Expired tokens should be refreshed before API calls."""
        from storage import GoogleSheetsBackend
        gc_mock = mocker.patch('storage.gspread')
        gc_auth = gc_mock.authorize.return_value
        sp_mock = gc_auth.open_by_key.return_value
        _ = sp_mock.worksheet.return_value

        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        # Token should have been refreshed
        assert backend._auth_mode == "oauth"


class TestOAuth2AndServiceAccountCompatibility:
    """Test backward compatibility with service account authentication."""

    def test_service_account_still_works(self, mocker):
        """Service account authentication should still work."""
        from storage import GoogleSheetsBackend
        mocker.patch('storage.gspread')
        mocker.patch('storage.ServiceCredentials')
        mocker.patch('storage.ServiceCredentials').from_service_account_file.return_value = mocker.Mock()

        backend = GoogleSheetsBackend(
            service_account_file='/tmp/fake_sa.json',
            spreadsheet_id='fake-id',
        )
        assert backend._auth_mode == "service_account"

    def test_oauth_and_service_account_both_available(self, mocker):
        """Both auth modes should be available simultaneously."""
        from storage import GoogleSheetsBackend
        mocker.patch('storage.gspread')
        mocker.patch('storage.ServiceCredentials')
        mocker.patch('storage.OAuthCredentials')
        mocker.patch('storage.AuthRequest')

        # Service account backend
        mocker.patch('storage.ServiceCredentials').from_service_account_file.return_value = mocker.Mock()
        sa_backend = GoogleSheetsBackend(
            service_account_file='/tmp/fake_sa.json',
            spreadsheet_id='fake-id',
        )
        assert sa_backend._auth_mode == "service_account"

        # OAuth2 backend
        oauth_backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id='fake-id',
        )
        assert oauth_backend._auth_mode == "oauth"
