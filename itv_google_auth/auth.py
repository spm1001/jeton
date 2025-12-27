"""
Google OAuth with dual-mode support.

Modes:
1. Auto (default): localhost server, auto-opens browser
2. Manual (--manual): paste redirect URL
3. Non-interactive (--manual --code URL): for scripting/Claude Code

Based on patterns from infra-mcp-workspace and itv-mit-team-meeting-workflow,
with scope mismatch handling from xmas-nice-things.
"""

from __future__ import annotations

import json
import os
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from itv_google_auth.callback import ERROR_HTML, NO_CODE_HTML, POST_AUTH_HTML, SUCCESS_HTML

# Scope shortcuts for convenience
SCOPE_SHORTCUTS = {
    # Drive
    "drive": "https://www.googleapis.com/auth/drive",
    "drive.readonly": "https://www.googleapis.com/auth/drive.readonly",
    "drive.file": "https://www.googleapis.com/auth/drive.file",
    # Gmail
    "gmail": "https://www.googleapis.com/auth/gmail.modify",
    "gmail.readonly": "https://www.googleapis.com/auth/gmail.readonly",
    "gmail.send": "https://www.googleapis.com/auth/gmail.send",
    # Sheets, Slides, Docs
    "sheets": "https://www.googleapis.com/auth/spreadsheets",
    "sheets.readonly": "https://www.googleapis.com/auth/spreadsheets.readonly",
    "slides": "https://www.googleapis.com/auth/presentations",
    "slides.readonly": "https://www.googleapis.com/auth/presentations.readonly",
    "docs": "https://www.googleapis.com/auth/documents",
    "docs.readonly": "https://www.googleapis.com/auth/documents.readonly",
    # Calendar
    "calendar": "https://www.googleapis.com/auth/calendar",
    "calendar.readonly": "https://www.googleapis.com/auth/calendar.readonly",
    # Contacts & Directory
    "contacts.readonly": "https://www.googleapis.com/auth/contacts.readonly",
    "directory.readonly": "https://www.googleapis.com/auth/directory.readonly",
    "admin.directory.user.readonly": "https://www.googleapis.com/auth/admin.directory.user.readonly",
    # Apps Script
    "script.projects": "https://www.googleapis.com/auth/script.projects",
    "script.deployments": "https://www.googleapis.com/auth/script.deployments",
    # Logging
    "logging.read": "https://www.googleapis.com/auth/logging.read",
}


def expand_scopes(scopes: list[str]) -> list[str]:
    """Expand scope shortcuts to full URLs.

    Args:
        scopes: List of scope shortcuts (e.g., 'drive.readonly') or full URLs

    Returns:
        List of full scope URLs
    """
    return [SCOPE_SHORTCUTS.get(s, s) for s in scopes]


@dataclass
class TokenStatus:
    """Status of an OAuth token."""

    valid: bool
    exists: bool
    expired: bool
    can_refresh: bool
    expires_at: datetime | None
    scopes: list[str]
    error: str | None = None

    @property
    def expires_in(self) -> timedelta | None:
        """Time until token expires, or None if unknown/expired."""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.utcnow()
        return delta if delta.total_seconds() > 0 else None

    @classmethod
    def check(cls, token_path: str | Path) -> TokenStatus:
        """Check the status of a token file without loading credentials.

        Args:
            token_path: Path to token.json file

        Returns:
            TokenStatus with details about the token
        """
        token_path = Path(token_path)

        if not token_path.exists():
            return cls(
                valid=False,
                exists=False,
                expired=False,
                can_refresh=False,
                expires_at=None,
                scopes=[],
                error="Token file not found"
            )

        try:
            token_data = json.loads(token_path.read_text())
        except (json.JSONDecodeError, IOError) as e:
            return cls(
                valid=False,
                exists=True,
                expired=False,
                can_refresh=False,
                expires_at=None,
                scopes=[],
                error=f"Failed to read token file: {e}"
            )

        # Parse expiry
        expires_at = None
        if token_data.get("expiry"):
            try:
                expires_at = datetime.fromisoformat(token_data["expiry"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        expired = expires_at is not None and expires_at < datetime.utcnow()
        can_refresh = bool(token_data.get("refresh_token"))
        scopes = token_data.get("scopes", [])

        # Token is valid if not expired, or if expired but can refresh
        valid = (not expired) or can_refresh

        return cls(
            valid=valid,
            exists=True,
            expired=expired,
            can_refresh=can_refresh,
            expires_at=expires_at,
            scopes=scopes,
        )


def load_credentials(
    token_path: str | Path,
    credentials_path: str | Path | None = None,
    scopes: list[str] | None = None,
) -> Credentials | None:
    """Load existing credentials from token file.

    Automatically refreshes if the token is expired but has a refresh_token.

    Args:
        token_path: Path to token.json file
        credentials_path: Path to credentials.json (needed for refresh)
        scopes: Expected scopes (for validation, optional)

    Returns:
        Valid Credentials object, or None if token doesn't exist or is invalid
    """
    token_path = Path(token_path)
    if not token_path.exists():
        return None

    try:
        token_data = json.loads(token_path.read_text())
    except (json.JSONDecodeError, IOError):
        return None

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    # Set expiry if available
    if token_data.get("expiry"):
        try:
            creds._expiry = datetime.fromisoformat(
                token_data["expiry"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_credentials(creds, token_path)
        except Exception:
            return None

    return creds if creds.valid else None


def authenticate(
    credentials_path: str | Path,
    token_path: str | Path,
    scopes: list[str],
    manual_mode: bool = False,
    code: str | None = None,
    port: int = 3000,
    post_auth: dict | None = None,
) -> Credentials:
    """Run OAuth flow and save resulting token.

    Args:
        credentials_path: Path to credentials.json from GCP Console
        token_path: Where to save the resulting token
        scopes: List of scopes (can use shortcuts like 'drive.readonly')
        manual_mode: If True, user pastes redirect URL instead of localhost server
        code: Pre-provided auth code or redirect URL (for non-interactive use)
        port: Port for localhost callback server (default 3000)
        post_auth: Optional dict for post-auth action screen. Keys:
            - copy_value: Value to display for copying
            - copy_label: Label for the copy value (e.g., "GCP Project Number")
            - message: Instructions to show the user
            - button_url: URL the button opens
            - button_label: Button text (e.g., "Open Settings →")

    Returns:
        Valid Credentials object

    Raises:
        FileNotFoundError: If credentials.json doesn't exist
        ValueError: If authentication fails
        TimeoutError: If auto mode times out waiting for callback
    """
    credentials_path = Path(credentials_path)
    token_path = Path(token_path)

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {credentials_path}\n"
            "Download OAuth client credentials from GCP Console:\n"
            "https://console.cloud.google.com/apis/credentials"
        )

    # Expand scope shortcuts
    scopes = expand_scopes(scopes)

    # Allow OAuth scope to change without raising error
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

    redirect_uri = f"http://localhost:{port}/oauth/callback"

    flow = Flow.from_client_secrets_file(
        str(credentials_path),
        scopes=scopes,
        redirect_uri=redirect_uri,
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    print("OAuth Authentication")
    print("=" * 50)
    print()

    if manual_mode or code:
        auth_code = _manual_flow(auth_url, code, post_auth)
    else:
        auth_code = _auto_flow(auth_url, port, post_auth)

    # Exchange code for tokens (with scope mismatch handling)
    creds = _exchange_code(flow, auth_code)

    # Save
    _save_credentials(creds, token_path)

    print(f"Token saved to {token_path}")
    print(f"Scopes: {', '.join(creds.scopes or [])}")
    print()
    print("Authentication successful!")

    return creds


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle OAuth callback GET request."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/oauth/callback":
            code = params.get("code", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(ERROR_HTML.format(error=error).encode())
                self.server.auth_code = None
                self.server.auth_error = error
                return

            if code:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()

                # Use post-auth page if configured, otherwise simple success
                post_auth = getattr(self.server, "post_auth", None)
                if post_auth:
                    import html
                    html_content = POST_AUTH_HTML.format(
                        copy_value=html.escape(str(post_auth.get("copy_value", ""))),
                        copy_label=html.escape(str(post_auth.get("copy_label", "Value"))),
                        message=html.escape(str(post_auth.get("message", ""))),
                        button_url=html.escape(str(post_auth.get("button_url", "#"))),
                        button_label=html.escape(str(post_auth.get("button_label", "Continue"))),
                    )
                    self.wfile.write(html_content.encode())
                else:
                    self.wfile.write(SUCCESS_HTML.encode())

                self.server.auth_code = code
                return

            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(NO_CODE_HTML.encode())
            self.server.auth_code = None
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


def _auto_flow(auth_url: str, port: int, post_auth: dict | None = None) -> str:
    """Auto server mode: localhost receives callback automatically."""
    print("Auto Server Mode (Local Development)")
    print("=" * 50)
    print()
    print("Authorization URL:")
    print(auth_url)
    print()

    # Try to open browser
    try:
        webbrowser.open(auth_url)
        print("Browser opened automatically")
    except Exception:
        print("Could not auto-open browser - please copy URL manually")
    print()

    print(f"Starting OAuth server on http://localhost:{port}/oauth/callback")
    print("Waiting for authorization...")
    print()

    server = HTTPServer(("localhost", port), _OAuthCallbackHandler)
    server.auth_code = None
    server.auth_error = None
    server.post_auth = post_auth

    def run_server():
        while server.auth_code is None and server.auth_error is None:
            server.handle_request()

    thread = Thread(target=run_server, daemon=True)
    thread.start()

    # Wait for code with timeout
    timeout = 300  # 5 minutes
    start = time.time()
    while server.auth_code is None and server.auth_error is None:
        if time.time() - start > timeout:
            raise TimeoutError("OAuth authorization timed out after 5 minutes")
        time.sleep(0.5)

    if server.auth_error:
        raise ValueError(f"OAuth error: {server.auth_error}")

    print("Authorization code received")
    return server.auth_code


def _manual_flow(auth_url: str, code_arg: str | None = None, post_auth: dict | None = None) -> str:
    """Manual mode: user copies redirect URL and pastes."""
    print("Manual Code Mode (Remote/SSH Development)")
    print("=" * 50)
    print()
    print("1. Copy this URL and open in your browser:")
    print()
    print(auth_url)
    print()
    print("2. Sign in and grant permissions")
    print("3. You'll be redirected to localhost (connection will fail - that's OK!)")
    print("4. Copy the ENTIRE failed redirect URL from your browser")
    print("   Example: http://localhost:3000/oauth/callback?code=4/XXX&scope=...")
    print("   Or just copy the code value: 4/XXX")

    if code_arg:
        print()
        print("Using code from command-line argument")
        code = _parse_code_from_input(code_arg)
    else:
        print("5. Paste below")
        print()
        try:
            user_input = input("Paste the full redirect URL or just the code: ")
            code = _parse_code_from_input(user_input.strip())
        except (EOFError, KeyboardInterrupt):
            print("\n\nAuthentication cancelled")
            sys.exit(1)

    if not code:
        raise ValueError("Could not extract authorization code from input")

    # Show post-auth info in terminal for manual mode
    if post_auth:
        print()
        print("=" * 50)
        print(f"{post_auth.get('copy_label', 'Value')}: {post_auth.get('copy_value', '')}")
        print()
        print(post_auth.get("message", ""))
        print()
        print(f"Open: {post_auth.get('button_url', '')}")
        print("=" * 50)

    return code


def _parse_code_from_input(input_str: str) -> str:
    """Extract authorization code from URL or raw code."""
    input_str = input_str.strip()

    # Try to parse as full URL
    try:
        parsed = urlparse(input_str)
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if code:
            return code
    except Exception:
        pass

    # Return as-is (assume it's just the code)
    return input_str


def _exchange_code(flow: Flow, code: str) -> Credentials:
    """Exchange authorization code for tokens.

    Handles the "Scope has changed" error that can occur with incremental auth.
    """
    print()
    print("Exchanging authorization code for tokens...")

    try:
        flow.fetch_token(code=code)
        return flow.credentials
    except ValueError as e:
        if "Scope has changed" not in str(e):
            raise

        # Scope mismatch - extract tokens manually from session
        # This happens when Google grants different scopes than requested
        print("Google granted additional scopes (incremental authorization)")
        print("Proceeding with granted permissions...")
        print()

        token_data = flow.oauth2session.token

        # Calculate expiry
        expiry = None
        if "expires_in" in token_data:
            expiry = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        elif "expires_at" in token_data:
            expiry = datetime.utcfromtimestamp(token_data["expires_at"])

        # Parse scopes
        scope_data = token_data.get("scope", "")
        if isinstance(scope_data, str):
            scopes = scope_data.split()
        else:
            scopes = list(scope_data) if scope_data else []

        return Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=flow.client_config["client_id"],
            client_secret=flow.client_config["client_secret"],
            scopes=scopes,
            expiry=expiry,
        )


def _save_credentials(creds: Credentials, token_path: Path):
    """Save credentials to JSON file."""
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }
    token_path.write_text(json.dumps(token_data, indent=2))
