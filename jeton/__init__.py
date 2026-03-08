"""
Jeton — Google OAuth for Python projects.

Two functions:
    authenticate()      Run the OAuth flow (auto, manual, or non-interactive)
    load_credentials()  Load token from disk, auto-refresh if expired
"""

from jeton.auth import authenticate, load_credentials

__all__ = ["authenticate", "load_credentials"]
__version__ = "1.0.0"
