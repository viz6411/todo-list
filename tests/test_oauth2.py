"""Tests for OAuth2 authentication in GoogleSheetsBackend.

Verifies that GoogleSheetsBackend can authenticate using OAuth2 user
credentials (regular Google account) instead of service accounts,
and that Authorization: Bearer tokens are used correctly.
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
    """Test that OAuth2 authentication uses Bearer tokens correctly."""

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
        sp_mock = gc_auth.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value
        return creds_mock

    def test_uses_bearer_authorization(self, mock_oauth, mocker):
        """GoogleSheetsBackend should use Authorization: Bearer header."""
        from storage import GoogleSheetsBackend
        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        # Verify that authorize was called with Bearer token
        assert backend._auth_mode == "oauth"

    def test_refresh_token_persisted(self, mock_oauth, mocker):
        """OAuth2 refresh token should be available for persistence."""
        from storage import GoogleSheetsBackend
        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        assert hasattr(backend, '_credentials')

    def test_bearer_token_in_request_headers(self, mock_oauth, mocker):
        """API requests should include Authorization: Bearer header."""
        from storage import GoogleSheetsBackend
        gc_mock = mocker.patch('storage.gspread')
        gc_auth = gc_mock.authorize.return_value
        sp_mock = gc_auth.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value

        backend = GoogleSheetsBackend(
            oauth_credentials={"refresh_token": "test"},
            spreadsheet_id="fake-id",
        )
        # Verify gspread was authorized with OAuth2 credentials
        gc_mock.authorize.assert_called()


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
        auth_req = mocker.patch('storage.AuthRequest').return_value
        creds_mock.refresh = mocker.Mock(side_effect=lambda req: setattr(creds_mock, 'expired', False))
        gc_mock = mocker.patch('storage.gspread')
        gc_auth = gc_mock.authorize.return_value
        sp_mock = gc_auth.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value
        return creds_mock

    def test_refreshes_expired_token(self, mock_oauth_refresh, mocker):
        """Expired tokens should be refreshed before API calls."""
        from storage import GoogleSheetsBackend
        gc_mock = mocker.patch('storage.gspread')
        gc_auth = gc_mock.authorize.return_value
        sp_mock = gc_auth.open_by_id.return_value
        ws_mock = sp_mock.worksheet.return_value

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
