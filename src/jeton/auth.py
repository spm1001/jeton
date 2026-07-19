"""
Google OAuth with automatic environment detection.

Modes:
1. Auto (default on desktop): localhost callback server + auto-opens browser
2. Headless (auto-detected): generates auth URL, saves PKCE state, raises HeadlessError
3. Code exchange: pass code= to complete the flow started by either mode
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
import webbrowser
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow


class HeadlessError(Exception):
    """Raised when authenticate() detects a headless environment.

    Contains the auth URL so the consumer can display it and instruct
    the user to re-run with --code URL.
    """

    def __init__(self, url: str):
        self.url = url
        super().__init__(
            f"No browser available. Open this URL, then re-run with --code:\n{url}"
        )


def _can_open_browser() -> bool:
    """Check if a graphical environment is available for OAuth callback."""
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


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


# ---------------------------------------------------------------------------
# PKCE state persistence
#
# .pkce_state.json (next to the token file) holds the code_verifier for every
# auth flow minted but not yet redeemed, KEYED BY THE OAUTH `state` PARAM.
# Keying matters: the old single top-level code_verifier meant two concurrent
# flows (e.g. two sessions re-authing at once) clobbered each other — the
# second mint overwrote the first's verifier, so the first redeem failed with
# "Invalid code verifier" AFTER the consent click was spent (mise-zikesa).
# Now each flow owns its entry; redeem looks up by the state carried in the
# redirect URL.
# ---------------------------------------------------------------------------

_PKCE_FLOW_TTL_S = 3600  # entries older than this are pruned at mint time


def _pkce_challenge(verifier: str) -> str:
    """Compute the S256 code challenge for a verifier (RFC 7636)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _pkce_read(path: Path) -> dict:
    """Read the PKCE state file tolerantly. Returns {} on missing/corrupt."""
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


@contextmanager
def _pkce_lock(path: Path):
    """Advisory lock for read-modify-write on the PKCE state file.

    Sidecar .lock file + flock (POSIX). Without fcntl (Windows) it degrades
    to a no-op: the atomic replace still prevents torn files, and keyed
    entries make the worst case a clear refusal at redeem, never a silent
    clobber.
    """
    try:
        import fcntl
    except ImportError:
        yield
        return
    lock_path = path.with_name(path.name + ".lock")
    with open(lock_path, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _pkce_write(path: Path, data: dict) -> None:
    """Atomic write (temp + replace) so a reader never sees a torn file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


def _pkce_persist(path: Path, state: str, verifier: str) -> None:
    """Add this flow's verifier under its state key — merge, never clobber.

    Prunes entries older than _PKCE_FLOW_TTL_S. A pre-upgrade top-level
    code_verifier is preserved so an in-flight legacy flow can still redeem
    after jeton upgrades mid-dance.
    """
    with _pkce_lock(path):
        data = _pkce_read(path)
        flows = data.get("flows")
        if not isinstance(flows, dict):
            flows = {}
        now = time.time()
        flows = {
            k: v
            for k, v in flows.items()
            if isinstance(v, dict)
            and now - v.get("created_at", 0) < _PKCE_FLOW_TTL_S
        }
        flows[state] = {"code_verifier": verifier, "created_at": now}
        payload: dict = {"flows": flows}
        if isinstance(data.get("code_verifier"), str):
            payload["code_verifier"] = data["code_verifier"]
        _pkce_write(path, payload)


def _pkce_verify_minted(path: Path, state: str, auth_url: str) -> None:
    """Mint-time self-check: the URL being handed out must match the verifier
    that actually landed on disk (re-read, not the in-memory copy).

    Catches silent write failures and same-instant clobbers. A doomed URL
    burns a human consent click, so abort loudly instead (mise-zikesa).
    """
    params = parse_qs(urlparse(auth_url).query)
    challenge = params.get("code_challenge", [None])[0]
    if challenge is None:
        return  # URL carries no PKCE — nothing to verify
    method = params.get("code_challenge_method", ["S256"])[0]
    entry = _pkce_read(path).get("flows", {}).get(state) or {}
    persisted = entry.get("code_verifier")
    expected = None
    if persisted:
        expected = _pkce_challenge(persisted) if method == "S256" else persisted
    if expected != challenge:
        raise RuntimeError(
            "PKCE self-check failed: the auth URL's code_challenge does not "
            "match the verifier persisted for its state. Handing out this URL "
            "would burn a consent click — the redeem could only fail. Likely "
            "causes: the state file write failed, or another process rewrote "
            "it in the same instant. Re-run authentication."
        )


def _pkce_lookup(path: Path, state: str | None) -> tuple[str, str | None]:
    """Find the verifier for a redeem. Returns (verifier, flow_key).

    flow_key is the state the entry lives under, or None for the legacy
    top-level verifier. With a state (full redirect URL pasted): exact keyed
    lookup, legacy fallback. Without one (bare code): only safe when a single
    flow is in flight — with several, refuse rather than guess, because a
    wrong verifier burns the single-use code at Google's token endpoint.

    Raises ValueError (before any Google call, so the code survives for a
    retry) when no verifier can be found.
    """
    data = _pkce_read(path)
    flows = data.get("flows") if isinstance(data.get("flows"), dict) else {}
    legacy = data.get("code_verifier")
    legacy = legacy if isinstance(legacy, str) else None

    if state is not None:
        entry = flows.get(state)
        if isinstance(entry, dict) and entry.get("code_verifier"):
            return entry["code_verifier"], state
        if legacy:
            return legacy, None
        raise ValueError(
            "No PKCE verifier found for this flow's state. Either the auth "
            "URL was minted on a different machine (mint and redeem must "
            "happen where the same token directory lives), or the state "
            "expired/was cleaned up. Re-run authentication to mint a fresh "
            "URL — this authorization code has NOT been spent."
        )

    live = {k: v for k, v in flows.items()
            if isinstance(v, dict) and v.get("code_verifier")}
    if len(live) == 1:
        key, entry = next(iter(live.items()))
        return entry["code_verifier"], key
    if len(live) > 1:
        raise ValueError(
            f"{len(live)} auth flows are in flight and a bare code doesn't "
            "say which one it belongs to. Paste the FULL redirect URL instead "
            "(it carries the state parameter) — this authorization code has "
            "NOT been spent."
        )
    if legacy:
        return legacy, None
    raise ValueError(
        "No PKCE state found on this machine — the auth URL wasn't minted "
        "here, or its state was cleaned up. Mint and redeem must happen on "
        "the same machine (same token directory). Re-run authentication — "
        "this authorization code has NOT been spent."
    )


def _pkce_consume(path: Path, flow_key: str | None) -> None:
    """Remove the redeemed flow's entry, leaving concurrent flows intact.

    flow_key None = the legacy top-level verifier. Deletes the file when
    nothing remains (matching the old unlink behaviour).
    """
    with _pkce_lock(path):
        data = _pkce_read(path)
        flows = data.get("flows") if isinstance(data.get("flows"), dict) else {}
        if flow_key is None:
            data.pop("code_verifier", None)
        else:
            flows.pop(flow_key, None)
        data["flows"] = flows
        if not flows and not data.get("code_verifier"):
            path.unlink(missing_ok=True)
            return
        _pkce_write(path, data)


def get_auth_url(
    credentials_path: str | Path,
    token_path: str | Path,
    scopes: list[str],
    port: int = 3000,
) -> str:
    """Generate OAuth URL and save PKCE state for later code exchange.

    Use this for remote/SSH flows where no browser is available locally.
    The caller should display the URL, then later call authenticate(code=...)
    to complete the exchange.

    Args:
        credentials_path: Path to credentials.json from GCP Console
        token_path: Where token will eventually be saved (PKCE state goes next to it)
        scopes: List of full scope URLs
        port: Port baked into the redirect URI (default 3000)

    Returns:
        Authorization URL string

    Raises:
        FileNotFoundError: If credentials.json doesn't exist
    """
    credentials_path = Path(credentials_path)
    token_path = Path(token_path)

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {credentials_path}\n"
            "Download OAuth client credentials from GCP Console:\n"
            "https://console.cloud.google.com/apis/credentials"
        )

    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

    redirect_uri = f"http://localhost:{port}/oauth/callback"
    pkce_state_path = token_path.parent / ".pkce_state.json"

    flow = Flow.from_client_secrets_file(
        str(credentials_path),
        scopes=scopes,
        redirect_uri=redirect_uri,
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    # Save PKCE verifier under this flow's state so authenticate(code=...)
    # can use it later — merged, so concurrent flows don't clobber each other.
    if hasattr(flow, "code_verifier") and flow.code_verifier:
        _pkce_persist(pkce_state_path, state, flow.code_verifier)
        _pkce_verify_minted(pkce_state_path, state, auth_url)

    return auth_url


def authenticate(
    credentials_path: str | Path,
    token_path: str | Path,
    scopes: list[str],
    code: str | None = None,
    port: int = 3000,
    post_auth: dict | None = None,
    state: str | None = None,
) -> Credentials:
    """Run OAuth flow and save resulting token.

    Two modes:
    - Auto (default): opens browser, starts localhost callback server
    - Code exchange: pass code= with auth code or redirect URL
      (pair with get_auth_url() for remote/SSH workflows)

    Args:
        credentials_path: Path to credentials.json from GCP Console
        token_path: Where to save the resulting token
        scopes: List of full scope URLs
        code: Auth code or redirect URL (for code exchange mode)
        port: Port for localhost callback server (default 3000)
        state: OAuth state param for the flow `code` belongs to. Only needed
            when `code` is a bare code (a full redirect URL carries state
            itself) AND several flows may be in flight — it selects the
            right PKCE verifier from the keyed state file.
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
        HeadlessError: If no browser available (url attribute has the auth URL)
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
    pkce_state_path = token_path.parent / ".pkce_state.json"

    flow = Flow.from_client_secrets_file(
        str(credentials_path),
        scopes=scopes,
        redirect_uri=redirect_uri,
    )

    pkce_used = False
    pkce_key: str | None = None

    if code:
        # Code exchange — look up the verifier for THIS flow (keyed by state
        # from the redirect URL, or the explicit state= arg for bare codes).
        auth_code, url_state = _parse_code_and_state(code)
        flow_state = url_state or state
        verifier, pkce_key = _pkce_lookup(pkce_state_path, flow_state)
        flow.code_verifier = verifier
        pkce_used = True

        print("OAuth Authentication")
        print("=" * 50)
        print()
    else:
        # Generate URL and PKCE state
        auth_url, mint_state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )

        # Save PKCE verifier so --code can work in a separate invocation —
        # keyed by state, merged so concurrent flows don't clobber each other.
        if hasattr(flow, "code_verifier") and flow.code_verifier:
            _pkce_persist(pkce_state_path, mint_state, flow.code_verifier)
            _pkce_verify_minted(pkce_state_path, mint_state, auth_url)
            pkce_used = True
            pkce_key = mint_state

        # Headless detection — raise before trying to open browser/bind port
        if not _can_open_browser():
            raise HeadlessError(auth_url)

        print("OAuth Authentication")
        print("=" * 50)
        print()

        auth_code = _auto_flow(auth_url, port, post_auth, expected_state=mint_state)

    # Exchange code for tokens (with scope mismatch handling)
    creds = _exchange_code(flow, auth_code)

    # Clean up THIS flow's PKCE entry — concurrent flows keep theirs
    if pkce_used:
        _pkce_consume(pkce_state_path, pkce_key)

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

        # Validate state parameter to prevent CSRF
        expected_state = getattr(self.server, "expected_state", None)
        if expected_state is not None:
            callback_state = params.get("state", [None])[0]
            if callback_state != expected_state:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    _ERROR_HTML.format(
                        error="State mismatch — possible CSRF attack. "
                        "Please restart authentication."
                    ).encode()
                )
                self.server.auth_code = None
                self.server.auth_error = "state_mismatch"
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

def _auto_flow(
    auth_url: str,
    port: int,
    post_auth: dict | None = None,
    expected_state: str | None = None,
) -> str:
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
    server.expected_state = expected_state

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


def _parse_code_from_input(input_str: str) -> str:
    """Extract authorization code from URL or raw code."""
    code, _ = _parse_code_and_state(input_str)
    return code


def _parse_code_and_state(input_str: str) -> tuple[str, str | None]:
    """Extract authorization code and state from URL or raw code.

    Returns:
        (code, state) — state is None when input is a raw code (not a URL).
    """
    input_str = input_str.strip()

    try:
        parsed = urlparse(input_str)
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if code:
            state = params.get("state", [None])[0]
            return code, state
    except Exception:
        pass

    return input_str, None


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


_CANONICAL_TOKEN_FIELDS = {
    "token",
    "refresh_token",
    "token_uri",
    "client_id",
    "client_secret",
    "scopes",
    "expiry",
}


def _save_credentials(creds: Credentials, token_path: Path):
    """Save credentials to JSON file, preserving any non-canonical top-level keys.

    Downstream consumers may stash extra metadata (e.g. an ``_identity`` cue, an
    audit label) alongside the OAuth fields. Merging on write keeps that data
    alive across the hourly refresh cycle.
    """
    token_data: dict = {}
    if token_path.exists():
        try:
            existing = json.loads(token_path.read_text())
            if isinstance(existing, dict):
                token_data = existing
        except (json.JSONDecodeError, OSError):
            pass

    token_data.update({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    })
    token_path.write_text(json.dumps(token_data, indent=2))
