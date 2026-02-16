"""Tests for jeton.auth module."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from jeton.auth import (
    SCOPE_SHORTCUTS,
    TokenStatus,
    _parse_code_from_input,
    _save_credentials,
    expand_scopes,
)


# =============================================================================
# expand_scopes()
# =============================================================================


# When given a shortcut like "drive.readonly", it should return the full Google URL
def test_expand_scopes_shortcut():
    result = expand_scopes(["drive.readonly"])
    assert result == ["https://www.googleapis.com/auth/drive.readonly"]


# When given a full URL, it should pass it through unchanged
def test_expand_scopes_full_url_passthrough():
    url = "https://www.googleapis.com/auth/calendar"
    result = expand_scopes([url])
    assert result == [url]


# When given a mix of shortcuts and URLs, it should expand only the shortcuts
def test_expand_scopes_mixed():
    result = expand_scopes(["drive.readonly", "https://custom.scope/foo"])
    assert result[0] == "https://www.googleapis.com/auth/drive.readonly"
    assert result[1] == "https://custom.scope/foo"


# When given an unknown shortcut, it should pass it through unchanged (not crash)
def test_expand_scopes_unknown_shortcut():
    result = expand_scopes(["unknown.scope"])
    assert result == ["unknown.scope"]


# When given an empty list, it should return an empty list
def test_expand_scopes_empty():
    result = expand_scopes([])
    assert result == []


# When given multiple known shortcuts, it should expand all of them
def test_expand_scopes_multiple_shortcuts():
    result = expand_scopes(["drive.readonly", "sheets", "gmail.send"])
    assert len(result) == 3
    assert all(url.startswith("https://www.googleapis.com/auth/") for url in result)


# =============================================================================
# TokenStatus.check()
# =============================================================================


# When the file doesn't exist, it should report exists=False and valid=False
def test_token_status_missing_file(tmp_path):
    status = TokenStatus.check(tmp_path / "nonexistent.json")
    assert status.exists is False
    assert status.valid is False
    assert "not found" in status.error.lower()


# When the file contains invalid JSON, it should report exists=True but valid=False with an error
def test_token_status_corrupt_json(tmp_path):
    bad_file = tmp_path / "token.json"
    bad_file.write_text("{ not valid json")
    status = TokenStatus.check(bad_file)
    assert status.exists is True
    assert status.valid is False
    assert status.error is not None
    assert "failed to read" in status.error.lower()


# When the token is expired but has a refresh_token, it should report valid=True (can refresh)
def test_token_status_expired_but_refreshable(tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({
        "token": "access123",
        "refresh_token": "refresh456",
        "expiry": "2020-01-01T00:00:00Z",
        "scopes": ["https://www.googleapis.com/auth/drive"]
    }))
    status = TokenStatus.check(token_file)
    assert status.expired is True
    assert status.can_refresh is True
    assert status.valid is True


# When the token is expired and has no refresh_token, it should report valid=False
def test_token_status_expired_no_refresh(tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({
        "token": "access123",
        "expiry": "2020-01-01T00:00:00Z",
        "scopes": ["https://www.googleapis.com/auth/drive"]
    }))
    status = TokenStatus.check(token_file)
    assert status.expired is True
    assert status.can_refresh is False
    assert status.valid is False


# When the token hasn't expired yet, it should report valid=True and expired=False
def test_token_status_not_expired(tmp_path):
    token_file = tmp_path / "token.json"
    future_expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    token_file.write_text(json.dumps({
        "token": "access123",
        "refresh_token": "refresh456",
        "expiry": future_expiry,
        "scopes": ["https://www.googleapis.com/auth/drive"]
    }))
    status = TokenStatus.check(token_file)
    assert status.expired is False
    assert status.valid is True


# When the expiry field is missing, it should still work (assume not expired)
def test_token_status_no_expiry_field(tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({
        "token": "access123",
        "refresh_token": "refresh456",
        "scopes": ["https://www.googleapis.com/auth/drive"]
    }))
    status = TokenStatus.check(token_file)
    assert status.expires_at is None
    assert status.expired is False
    assert status.valid is True


# When the expiry field is malformed, it should handle it gracefully
def test_token_status_malformed_expiry(tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({
        "token": "access123",
        "refresh_token": "refresh456",
        "expiry": "not-a-date",
        "scopes": ["https://www.googleapis.com/auth/drive"]
    }))
    status = TokenStatus.check(token_file)
    assert status.expires_at is None
    assert status.valid is True  # no expiry means not expired


# When scopes are missing from token, it should return empty list
def test_token_status_no_scopes(tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({
        "token": "access123",
        "refresh_token": "refresh456",
    }))
    status = TokenStatus.check(token_file)
    assert status.scopes == []


# =============================================================================
# TokenStatus.expires_in
# =============================================================================


# When token expires in the future, it should return a positive timedelta
def test_token_status_expires_in_future(tmp_path):
    token_file = tmp_path / "token.json"
    future_expiry = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    token_file.write_text(json.dumps({
        "token": "access123",
        "expiry": future_expiry,
    }))
    status = TokenStatus.check(token_file)
    assert status.expires_in is not None
    assert status.expires_in.total_seconds() > 0
    assert status.expires_in.total_seconds() < 31 * 60  # less than 31 minutes


# When token is already expired, it should return None
def test_token_status_expires_in_past(tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({
        "token": "access123",
        "expiry": "2020-01-01T00:00:00Z",
    }))
    status = TokenStatus.check(token_file)
    assert status.expires_in is None


# When expires_at is None, it should return None
def test_token_status_expires_in_no_expiry(tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({
        "token": "access123",
    }))
    status = TokenStatus.check(token_file)
    assert status.expires_in is None


# =============================================================================
# _parse_code_from_input()
# =============================================================================


# When given a full redirect URL with ?code=XXX, it should extract just the code
def test_parse_code_from_url():
    url = "http://localhost:3000/oauth/callback?code=4/abc123&scope=email"
    result = _parse_code_from_input(url)
    assert result == "4/abc123"


# When given just the raw code string, it should return it unchanged
def test_parse_code_raw_code():
    code = "4/abc123"
    result = _parse_code_from_input(code)
    assert result == "4/abc123"


# When given a URL without a code parameter, it should return the input as-is
def test_parse_code_no_code_param():
    url = "http://localhost:3000/oauth/callback?error=access_denied"
    result = _parse_code_from_input(url)
    assert result == url


# When given whitespace around the input, it should trim it
def test_parse_code_whitespace():
    result = _parse_code_from_input("  4/abc123  \n")
    assert result == "4/abc123"


# When given a URL with only a code parameter, it should extract it
def test_parse_code_only_code_param():
    url = "http://localhost:3000/oauth/callback?code=xyz789"
    result = _parse_code_from_input(url)
    assert result == "xyz789"


# =============================================================================
# _save_credentials()
# =============================================================================


# When given valid credentials, it should write JSON with all required fields
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


# When credentials have no expiry, it should write expiry as null
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


# When credentials have scopes, it should write them as a list
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
