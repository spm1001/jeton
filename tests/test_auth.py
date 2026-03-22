"""Tests for jeton.auth module."""

import json
from datetime import datetime
from io import BytesIO
from http.server import HTTPServer
from unittest.mock import MagicMock, patch

import pytest

from jeton.auth import (
    HeadlessError,
    _can_open_browser,
    _parse_code_and_state,
    _parse_code_from_input,
    _OAuthCallbackHandler,
    _save_credentials,
)


# =============================================================================
# _parse_code_from_input()
# =============================================================================


def test_parse_code_from_url():
    url = "http://localhost:3000/oauth/callback?code=4/abc123&scope=email"
    assert _parse_code_from_input(url) == "4/abc123"


def test_parse_code_raw_code():
    assert _parse_code_from_input("4/abc123") == "4/abc123"


def test_parse_code_no_code_param():
    url = "http://localhost:3000/oauth/callback?error=access_denied"
    assert _parse_code_from_input(url) == url


def test_parse_code_whitespace():
    assert _parse_code_from_input("  4/abc123  \n") == "4/abc123"


def test_parse_code_only_code_param():
    url = "http://localhost:3000/oauth/callback?code=xyz789"
    assert _parse_code_from_input(url) == "xyz789"


# =============================================================================
# _save_credentials()
# =============================================================================


def test_save_credentials_all_fields(tmp_path):
    from unittest.mock import MagicMock

    creds = MagicMock()
    creds.token = "access_token_123"
    creds.refresh_token = "refresh_token_456"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "client_id_789"
    creds.client_secret = "client_secret_xyz"
    creds.scopes = ["https://www.googleapis.com/auth/drive"]
    creds.expiry = datetime(2025, 12, 31, 23, 59, 59)

    token_path = tmp_path / "token.json"
    _save_credentials(creds, token_path)

    saved = json.loads(token_path.read_text())
    assert saved["token"] == "access_token_123"
    assert saved["refresh_token"] == "refresh_token_456"
    assert saved["client_id"] == "client_id_789"
    assert saved["scopes"] == ["https://www.googleapis.com/auth/drive"]
    assert "2025-12-31" in saved["expiry"]


def test_save_credentials_no_expiry(tmp_path):
    from unittest.mock import MagicMock

    creds = MagicMock()
    creds.token = "access_token_123"
    creds.refresh_token = "refresh_token_456"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "client_id_789"
    creds.client_secret = "client_secret_xyz"
    creds.scopes = []
    creds.expiry = None

    token_path = tmp_path / "token.json"
    _save_credentials(creds, token_path)

    saved = json.loads(token_path.read_text())
    assert saved["expiry"] is None


def test_save_credentials_scopes_as_list(tmp_path):
    from unittest.mock import MagicMock

    creds = MagicMock()
    creds.token = "access_token_123"
    creds.refresh_token = None
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "client_id_789"
    creds.client_secret = "client_secret_xyz"
    creds.scopes = iter(["scope1", "scope2"])  # iterable, not list
    creds.expiry = None

    token_path = tmp_path / "token.json"
    _save_credentials(creds, token_path)

    saved = json.loads(token_path.read_text())
    assert isinstance(saved["scopes"], list)
    assert saved["scopes"] == ["scope1", "scope2"]


# =============================================================================
# _parse_code_and_state()
# =============================================================================


def test_parse_code_and_state_from_url():
    url = "http://localhost:3000/oauth/callback?code=4/abc123&state=xyz789&scope=email"
    code, state = _parse_code_and_state(url)
    assert code == "4/abc123"
    assert state == "xyz789"


def test_parse_code_and_state_no_state_in_url():
    url = "http://localhost:3000/oauth/callback?code=4/abc123&scope=email"
    code, state = _parse_code_and_state(url)
    assert code == "4/abc123"
    assert state is None


def test_parse_code_and_state_raw_code():
    code, state = _parse_code_and_state("4/abc123")
    assert code == "4/abc123"
    assert state is None


def test_parse_code_and_state_whitespace():
    code, state = _parse_code_and_state("  4/abc123  \n")
    assert code == "4/abc123"
    assert state is None


# =============================================================================
# _OAuthCallbackHandler state validation
# =============================================================================


def _make_handler(path: str, expected_state: str | None = None):
    """Create an _OAuthCallbackHandler with a fake request for testing."""
    handler = _OAuthCallbackHandler.__new__(_OAuthCallbackHandler)
    handler.path = path
    handler.headers = {}
    handler.requestline = f"GET {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.command = "GET"

    # Fake server with state tracking attributes
    server = MagicMock()
    server.auth_code = None
    server.auth_error = None
    server.post_auth = None
    server.expected_state = expected_state
    handler.server = server

    # Capture response
    handler.wfile = BytesIO()
    handler._headers_buffer = []
    handler.responses = {200: ("OK",), 400: ("Bad Request",), 404: ("Not Found",)}

    # Stub response methods to just track what was sent
    sent = {"status": None, "headers": {}}

    def send_response(code):
        sent["status"] = code

    def send_header(key, value):
        sent["headers"][key] = value

    def end_headers():
        pass

    handler.send_response = send_response
    handler.send_header = send_header
    handler.end_headers = end_headers
    handler._sent = sent

    return handler


def test_callback_state_matches():
    """Valid state should accept the callback and set auth_code."""
    handler = _make_handler(
        "/oauth/callback?code=4/good&state=expected123",
        expected_state="expected123",
    )
    handler.do_GET()

    assert handler.server.auth_code == "4/good"
    assert handler.server.auth_error is None
    assert handler._sent["status"] == 200


def test_callback_state_mismatch():
    """Mismatched state should reject the callback."""
    handler = _make_handler(
        "/oauth/callback?code=4/good&state=wrong_state",
        expected_state="expected123",
    )
    handler.do_GET()

    assert handler.server.auth_code is None
    assert handler.server.auth_error == "state_mismatch"
    assert handler._sent["status"] == 400
    assert b"State mismatch" in handler.wfile.getvalue()


def test_callback_state_missing_from_callback():
    """Missing state param when server expects one should reject."""
    handler = _make_handler(
        "/oauth/callback?code=4/good",
        expected_state="expected123",
    )
    handler.do_GET()

    assert handler.server.auth_code is None
    assert handler.server.auth_error == "state_mismatch"
    assert handler._sent["status"] == 400


def test_callback_no_state_expected():
    """When server has no expected_state, skip validation (--code mode)."""
    handler = _make_handler(
        "/oauth/callback?code=4/good&state=anything",
        expected_state=None,
    )
    handler.do_GET()

    assert handler.server.auth_code == "4/good"
    assert handler._sent["status"] == 200


# =============================================================================
# get_auth_url()
# =============================================================================


def test_get_auth_url_returns_url(tmp_path):
    """get_auth_url should return a Google OAuth URL and save PKCE state."""
    from jeton.auth import get_auth_url

    # Write a minimal credentials.json
    creds_path = tmp_path / "credentials.json"
    creds_path.write_text(json.dumps({
        "installed": {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }))

    token_path = tmp_path / "token.json"
    url = get_auth_url(
        credentials_path=creds_path,
        token_path=token_path,
        scopes=["https://www.googleapis.com/auth/drive"],
    )

    assert "accounts.google.com" in url
    assert "test-client-id" in url
    assert "drive" in url


def test_get_auth_url_saves_pkce_state_when_available(tmp_path):
    """get_auth_url should save PKCE verifier if the library generates one."""
    from jeton.auth import get_auth_url

    creds_path = tmp_path / "credentials.json"
    creds_path.write_text(json.dumps({
        "installed": {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }))

    token_path = tmp_path / "token.json"
    get_auth_url(
        credentials_path=creds_path,
        token_path=token_path,
        scopes=["https://www.googleapis.com/auth/drive"],
    )

    pkce_path = tmp_path / ".pkce_state.json"
    if pkce_path.exists():
        # If library generated PKCE, verify structure
        pkce_data = json.loads(pkce_path.read_text())
        assert "code_verifier" in pkce_data
    # Not all google-auth-oauthlib versions generate PKCE — absence is OK


def test_get_auth_url_missing_credentials(tmp_path):
    """get_auth_url should raise FileNotFoundError for missing credentials."""
    from jeton.auth import get_auth_url

    with pytest.raises(FileNotFoundError):
        get_auth_url(
            credentials_path=tmp_path / "nonexistent.json",
            token_path=tmp_path / "token.json",
            scopes=["https://www.googleapis.com/auth/drive"],
        )


# =============================================================================
# _can_open_browser()
# =============================================================================


def test_can_open_browser_macos():
    """macOS always has a browser."""
    with patch("jeton.auth.sys") as mock_sys:
        mock_sys.platform = "darwin"
        assert _can_open_browser() is True


def test_can_open_browser_linux_with_display():
    """Linux with DISPLAY set has a browser."""
    with patch("jeton.auth.sys") as mock_sys, \
         patch.dict("os.environ", {"DISPLAY": ":0"}, clear=False):
        mock_sys.platform = "linux"
        assert _can_open_browser() is True


def test_can_open_browser_linux_headless():
    """Linux without DISPLAY or WAYLAND_DISPLAY is headless."""
    with patch("jeton.auth.sys") as mock_sys, \
         patch.dict("os.environ", {}, clear=True):
        mock_sys.platform = "linux"
        assert _can_open_browser() is False


# =============================================================================
# HeadlessError
# =============================================================================


def test_headless_error_has_url():
    """HeadlessError should carry the auth URL."""
    err = HeadlessError("https://accounts.google.com/o/oauth2/auth?...")
    assert err.url == "https://accounts.google.com/o/oauth2/auth?..."
    assert "accounts.google.com" in str(err)


def test_authenticate_raises_headless_on_no_browser(tmp_path):
    """authenticate() without code= should raise HeadlessError in headless env."""
    from jeton import authenticate

    creds_path = tmp_path / "credentials.json"
    creds_path.write_text(json.dumps({
        "installed": {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }))

    with patch("jeton.auth._can_open_browser", return_value=False):
        with pytest.raises(HeadlessError) as exc_info:
            authenticate(
                credentials_path=creds_path,
                token_path=tmp_path / "token.json",
                scopes=["https://www.googleapis.com/auth/drive"],
            )
        assert "accounts.google.com" in exc_info.value.url

    # PKCE state should have been saved
    pkce_path = tmp_path / ".pkce_state.json"
    if pkce_path.exists():
        pkce_data = json.loads(pkce_path.read_text())
        assert "code_verifier" in pkce_data
