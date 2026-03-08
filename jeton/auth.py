"""
Google OAuth with three-mode support.

Modes:
1. Auto (default): localhost server, auto-opens browser
2. Manual (--manual): paste redirect URL
3. Non-interactive (--code URL): for scripting/Claude Code
"""

from __future__ import annotations

import json
import os
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow


def load_credentials(
    token_path: str | Path,
    credentials_path: str | Path | None = None,
    scopes: list[str] | None = None,
) -> Credentials | None:
    """Load existing credentials from token file.

    Automatically refreshes if the token is expired but has a refresh_token.

    Args:
        token_path: Path to token.json file
        credentials_path: Path to credentials.json (unused, kept for API compat)
        scopes: Expected scopes (unused, kept for API compat)

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
        scopes: List of full scope URLs
        manual_mode: If True, user pastes redirect URL instead of localhost server
        code: Pre-provided auth code or redirect URL (for non-interactive use)
        port: Port for localhost callback server (default 3000)
        post_auth: Optional dict for post-auth info screen. Keys:
            - copy_value: Value to display for copying
            - copy_label: Label for the copy value
            - message: Instructions to show the user
            - button_url: URL the button opens
            - button_label: Button text

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

    # Relax scope matching — Google sometimes grants different scopes
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


# ---------------------------------------------------------------------------
# Callback HTML — minimal, functional
# ---------------------------------------------------------------------------

_SUCCESS_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>OK</title></head><body style="font-family:system-ui;text-align:center;padding:60px">
<h1 style="color:#2e7d32">&#10003; Authorization Successful</h1>
<p>You can close this tab.</p></body></html>"""

_ERROR_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Error</title></head><body style="font-family:system-ui;text-align:center;padding:60px">
<h1 style="color:#c62828">&#10007; Authorization Failed</h1>
<p><code>{error}</code></p></body></html>"""

_POST_AUTH_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>OK</title></head><body style="font-family:system-ui;text-align:center;padding:60px">
<h1 style="color:#2e7d32">&#10003; Authorization Successful</h1>
<p style="margin:20px 0"><strong>{copy_label}:</strong>
<code style="background:#f5f5f5;padding:4px 8px;font-size:18px;user-select:all">{copy_value}</code></p>
<p>{message}</p>
<p style="margin-top:20px"><a href="{button_url}" target="_blank">{button_label}</a></p>
</body></html>"""


# ---------------------------------------------------------------------------
# Callback server
# ---------------------------------------------------------------------------

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path != "/oauth/callback":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        error = params.get("error", [None])[0]
        if error:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_ERROR_HTML.format(error=error).encode())
            self.server.auth_code = None
            self.server.auth_error = error
            return

        code = params.get("code", [None])[0]
        if not code:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_ERROR_HTML.format(error="No authorization code received").encode())
            self.server.auth_code = None
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        post_auth = getattr(self.server, "post_auth", None)
        if post_auth:
            import html
            self.wfile.write(_POST_AUTH_HTML.format(
                copy_value=html.escape(str(post_auth.get("copy_value", ""))),
                copy_label=html.escape(str(post_auth.get("copy_label", "Value"))),
                message=html.escape(str(post_auth.get("message", ""))),
                button_url=html.escape(str(post_auth.get("button_url", "#"))),
                button_label=html.escape(str(post_auth.get("button_label", "Continue"))),
            ).encode())
        else:
            self.wfile.write(_SUCCESS_HTML.encode())

        self.server.auth_code = code


# ---------------------------------------------------------------------------
# Auth flows
# ---------------------------------------------------------------------------

def _auto_flow(auth_url: str, port: int, post_auth: dict | None = None) -> str:
    """Auto server mode: localhost receives callback automatically."""
    print("Auto Server Mode (Local Development)")
    print("=" * 50)
    print()
    print("Authorization URL:")
    print(auth_url)
    print()

    try:
        webbrowser.open(auth_url)
        print("Browser opened automatically")
    except Exception:
        print("Could not auto-open browser — please copy URL manually")
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

    try:
        parsed = urlparse(input_str)
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if code:
            return code
    except Exception:
        pass

    return input_str


def _exchange_code(flow: Flow, code: str) -> Credentials:
    """Exchange authorization code for tokens.

    Handles the "Scope has changed" error from incremental authorization.
    """
    print()
    print("Exchanging authorization code for tokens...")

    try:
        flow.fetch_token(code=code)
        return flow.credentials
    except ValueError as e:
        if "Scope has changed" not in str(e):
            raise

        # Scope mismatch — extract tokens manually from session
        print("Google granted additional scopes (incremental authorization)")
        print("Proceeding with granted permissions...")
        print()

        token_data = flow.oauth2session.token

        expiry = None
        if "expires_in" in token_data:
            expiry = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        elif "expires_at" in token_data:
            expiry = datetime.utcfromtimestamp(token_data["expires_at"])

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
