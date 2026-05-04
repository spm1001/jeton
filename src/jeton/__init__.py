"""
Jeton — Google OAuth for Python projects.

Three functions:
    authenticate()      Run the OAuth flow (auto, headless, or code exchange)
    get_auth_url()      Generate auth URL + save PKCE state (low-level)
    load_credentials()  Load token from disk, auto-refresh if expired

One exception:
    HeadlessError       Raised when no browser — .url has the auth URL
"""

from jeton.auth import HeadlessError, authenticate, get_auth_url, load_credentials

__all__ = ["HeadlessError", "authenticate", "get_auth_url", "load_credentials"]
__version__ = "1.3.0"
