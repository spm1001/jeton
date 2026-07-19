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


def test_save_credentials_preserves_unknown_keys(tmp_path):
    """Unknown top-level keys (e.g. _identity) survive a refresh round-trip."""
    from unittest.mock import MagicMock

    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({
        "token": "old_access_token",
        "refresh_token": "refresh_token_456",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client_id_789",
        "client_secret": "client_secret_xyz",
        "scopes": ["https://www.googleapis.com/auth/drive"],
        "expiry": "2025-01-01T00:00:00",
        "_identity": {"email": "user@example.com", "sub": "12345"},
        "_audit": "labelled-by-mise",
    }))

    creds = MagicMock()
    creds.token = "new_access_token"
    creds.refresh_token = "refresh_token_456"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "client_id_789"
    creds.client_secret = "client_secret_xyz"
    creds.scopes = ["https://www.googleapis.com/auth/drive"]
    creds.expiry = datetime(2025, 12, 31, 23, 59, 59)

    _save_credentials(creds, token_path)

    saved = json.loads(token_path.read_text())
    assert saved["token"] == "new_access_token"
    assert saved["_identity"] == {"email": "user@example.com", "sub": "12345"}
    assert saved["_audit"] == "labelled-by-mise"


def test_save_credentials_handles_corrupt_existing_file(tmp_path):
    """A corrupt existing token file should not block a refresh write."""
    from unittest.mock import MagicMock

    token_path = tmp_path / "token.json"
    token_path.write_text("not valid json{{{")

    creds = MagicMock()
    creds.token = "new_access_token"
    creds.refresh_token = "refresh_token_456"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "client_id_789"
    creds.client_secret = "client_secret_xyz"
    creds.scopes = []
    creds.expiry = None

    _save_credentials(creds, token_path)

    saved = json.loads(token_path.read_text())
    assert saved["token"] == "new_access_token"


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
        # If library generated PKCE, verify keyed structure (1.4.0 schema)
        pkce_data = json.loads(pkce_path.read_text())
        flows = pkce_data.get("flows", {})
        assert flows, "expected at least one keyed flow entry"
        assert all("code_verifier" in entry for entry in flows.values())
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

    # PKCE state should have been saved under the flow's state key, so the
    # --code path still works after the HeadlessError (1.4.0 keyed schema)
    pkce_path = tmp_path / ".pkce_state.json"
    if pkce_path.exists():
        pkce_data = json.loads(pkce_path.read_text())
        flows = pkce_data.get("flows", {})
        assert flows, "expected at least one keyed flow entry"
        assert all("code_verifier" in entry for entry in flows.values())


# =============================================================================
# PKCE keyed state — the two-flow race (mise-zikesa)
# =============================================================================

from urllib.parse import parse_qs as _parse_qs, urlparse as _urlparse

from jeton.auth import (
    _pkce_challenge,
    _pkce_consume,
    _pkce_lookup,
    _pkce_persist,
    _pkce_read,
    _pkce_verify_minted,
    authenticate,
    get_auth_url,
)

_CLIENT_CONFIG = {
    "installed": {
        "client_id": "test-client.apps.googleusercontent.com",
        "client_secret": "test-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


@pytest.fixture
def creds_file(tmp_path):
    p = tmp_path / "credentials.json"
    p.write_text(json.dumps(_CLIENT_CONFIG))
    return p


@pytest.fixture
def token_path(tmp_path):
    return tmp_path / "token.json"


def _url_param(url: str, name: str) -> str:
    return _parse_qs(_urlparse(url).query)[name][0]


def _fake_creds():
    creds = MagicMock()
    creds.token = "access-token"
    creds.refresh_token = "refresh-token"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "test-client"
    creds.client_secret = "test-secret"
    creds.scopes = ["scope-a"]
    creds.expiry = None
    return creds


def test_two_mints_do_not_clobber(creds_file, token_path):
    """The race that burned a consent click: mint B must not orphan URL A."""
    url1 = get_auth_url(creds_file, token_path, ["scope-a"])
    url2 = get_auth_url(creds_file, token_path, ["scope-a"])
    state1, state2 = _url_param(url1, "state"), _url_param(url2, "state")

    flows = _pkce_read(token_path.parent / ".pkce_state.json")["flows"]
    assert set(flows) == {state1, state2}
    # Each URL's challenge must match ITS OWN persisted verifier — url1's
    # verifier surviving mint 2 is the whole point.
    assert _pkce_challenge(flows[state1]["code_verifier"]) == _url_param(url1, "code_challenge")
    assert _pkce_challenge(flows[state2]["code_verifier"]) == _url_param(url2, "code_challenge")


def test_redeem_selects_by_state_and_leaves_sibling(creds_file, token_path):
    url1 = get_auth_url(creds_file, token_path, ["scope-a"])
    url2 = get_auth_url(creds_file, token_path, ["scope-a"])
    state1, state2 = _url_param(url1, "state"), _url_param(url2, "state")
    pkce_path = token_path.parent / ".pkce_state.json"
    verifier1 = _pkce_read(pkce_path)["flows"][state1]["code_verifier"]

    captured = {}

    def fake_exchange(flow, code):
        captured["verifier"] = flow.code_verifier
        return _fake_creds()

    with patch("jeton.auth._exchange_code", side_effect=fake_exchange):
        authenticate(
            creds_file, token_path, ["scope-a"],
            code=f"http://localhost:3000/oauth/callback?code=4/abc&state={state1}",
        )

    assert captured["verifier"] == verifier1
    flows_after = _pkce_read(pkce_path)["flows"]
    assert state1 not in flows_after  # consumed
    assert state2 in flows_after      # sibling intact


def test_bare_code_with_two_flows_refuses(creds_file, token_path):
    get_auth_url(creds_file, token_path, ["scope-a"])
    get_auth_url(creds_file, token_path, ["scope-a"])
    with patch("jeton.auth._exchange_code") as exchange:
        with pytest.raises(ValueError, match="redirect URL"):
            authenticate(creds_file, token_path, ["scope-a"], code="4/bare")
    exchange.assert_not_called()  # refusal happens BEFORE Google — code survives


def test_bare_code_single_flow_redeems_and_cleans_up(creds_file, token_path):
    url = get_auth_url(creds_file, token_path, ["scope-a"])
    pkce_path = token_path.parent / ".pkce_state.json"
    verifier = _pkce_read(pkce_path)["flows"][_url_param(url, "state")]["code_verifier"]

    captured = {}

    def fake_exchange(flow, code):
        captured["verifier"] = flow.code_verifier
        return _fake_creds()

    with patch("jeton.auth._exchange_code", side_effect=fake_exchange):
        authenticate(creds_file, token_path, ["scope-a"], code="4/bare")

    assert captured["verifier"] == verifier
    assert not pkce_path.exists()  # last entry consumed -> file removed


def test_state_arg_selects_among_flows_for_bare_code(creds_file, token_path):
    get_auth_url(creds_file, token_path, ["scope-a"])
    url2 = get_auth_url(creds_file, token_path, ["scope-a"])
    state2 = _url_param(url2, "state")
    pkce_path = token_path.parent / ".pkce_state.json"
    verifier2 = _pkce_read(pkce_path)["flows"][state2]["code_verifier"]

    captured = {}

    def fake_exchange(flow, code):
        captured["verifier"] = flow.code_verifier
        return _fake_creds()

    with patch("jeton.auth._exchange_code", side_effect=fake_exchange):
        authenticate(creds_file, token_path, ["scope-a"], code="4/bare", state=state2)

    assert captured["verifier"] == verifier2


def test_legacy_single_verifier_still_redeems(creds_file, token_path):
    pkce_path = token_path.parent / ".pkce_state.json"
    pkce_path.write_text(json.dumps({"code_verifier": "legacy-verifier"}))

    captured = {}

    def fake_exchange(flow, code):
        captured["verifier"] = flow.code_verifier
        return _fake_creds()

    with patch("jeton.auth._exchange_code", side_effect=fake_exchange):
        authenticate(creds_file, token_path, ["scope-a"], code="4/bare")

    assert captured["verifier"] == "legacy-verifier"
    assert not pkce_path.exists()


def test_unknown_state_raises_before_google(creds_file, token_path):
    get_auth_url(creds_file, token_path, ["scope-a"])
    with patch("jeton.auth._exchange_code") as exchange:
        with pytest.raises(ValueError, match="No PKCE verifier"):
            authenticate(
                creds_file, token_path, ["scope-a"],
                code="http://localhost:3000/oauth/callback?code=4/abc&state=NOSUCH",
            )
    exchange.assert_not_called()


def test_no_state_file_raises_before_google(creds_file, token_path):
    with patch("jeton.auth._exchange_code") as exchange:
        with pytest.raises(ValueError, match="No PKCE state"):
            authenticate(creds_file, token_path, ["scope-a"], code="4/bare")
    exchange.assert_not_called()


def test_verify_minted_catches_clobber(creds_file, token_path):
    url = get_auth_url(creds_file, token_path, ["scope-a"])
    state = _url_param(url, "state")
    pkce_path = token_path.parent / ".pkce_state.json"
    # Simulate a same-instant clobber: the persisted verifier no longer
    # matches the URL about to be handed out.
    _pkce_persist(pkce_path, state, "attacker-or-sibling-overwrote-this")
    with pytest.raises(RuntimeError, match="PKCE self-check failed"):
        _pkce_verify_minted(pkce_path, state, url)


def test_mint_prunes_stale_entries(creds_file, token_path):
    pkce_path = token_path.parent / ".pkce_state.json"
    stale = {"flows": {"old-state": {"code_verifier": "v", "created_at": 1.0}}}
    pkce_path.write_text(json.dumps(stale))
    url = get_auth_url(creds_file, token_path, ["scope-a"])
    flows = _pkce_read(pkce_path)["flows"]
    assert "old-state" not in flows
    assert _url_param(url, "state") in flows
