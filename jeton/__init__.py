"""
Jeton — Google OAuth library for Batterie de Savoir.

Usage:
    from jeton import authenticate, load_credentials, TokenStatus

    # Load existing credentials (returns None if invalid/missing)
    creds = load_credentials("./token.json", "./credentials.json", scopes)

    # Run OAuth flow if needed
    if creds is None:
        creds = authenticate("./credentials.json", "./token.json", scopes)

    # Check token status without loading
    status = TokenStatus.check("./token.json")
"""

from jeton.auth import (
    authenticate,
    load_credentials,
    TokenStatus,
    expand_scopes,
    SCOPE_SHORTCUTS,
)

__all__ = [
    "authenticate",
    "load_credentials",
    "TokenStatus",
    "expand_scopes",
    "SCOPE_SHORTCUTS",
]

__version__ = "0.2.0"
