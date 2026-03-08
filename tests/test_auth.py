"""Tests for jeton.auth module."""

import json
from datetime import datetime

import pytest

from jeton.auth import _parse_code_from_input, _save_credentials


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
