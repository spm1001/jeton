"""
Jeton — Google OAuth for Python projects.

Three functions:
    authenticate()      Run the OAuth flow (auto or code exchange)
    get_auth_url()      Generate auth URL + save PKCE state (for remote/SSH)
    load_credentials()  Load token from disk, auto-refresh if expired
"""

from jeton.auth import authenticate, get_auth_url, load_credentials

__all__ = ["authenticate", "get_auth_url", "load_credentials"]
__version__ = "1.1.0"
