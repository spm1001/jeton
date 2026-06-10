# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Purpose

Jeton is the Google OAuth library for [Batterie de Savoir](https://github.com/spm1001/batterie-de-savoir). Two functions, three auth modes, auto-refresh. Exists because `InstalledAppFlow.run_local_server()` has no SSH/remote or non-interactive mode.

Consumers: mise-en-space, itv-appscript-deploy.

**Gotcha:** `jeton` on PyPI is an unrelated placeholder package — any install
must pin the git URL (see README install block). A bare `jeton` dependency
resolves to the wrong package and fails with `cannot import name 'authenticate'`.

## Architecture

```
src/jeton/
├── __init__.py     # Public API: authenticate, load_credentials
└── auth.py         # Everything: flows, callback server, token I/O
```

That's it. ~430 lines total.

## Key Design Decisions

### Two Functions, Full URLs

Public API is `authenticate()` and `load_credentials()`. Consumers pass full scope URLs — no shortcut expansion.

### Three Auth Modes

1. **Auto** (default): localhost callback server + `webbrowser.open()`
2. **Manual**: print URL, user pastes redirect URL (for SSH/remote)
3. **Non-interactive**: pass `code=` argument (for Claude Code/scripts)

### post_auth Screen

`authenticate(..., post_auth={...})` shows a follow-up action on the callback page (auto mode) or in the terminal (manual mode). Used by itv-appscript-deploy to display the GCP project number for copy-paste.

### Scope Mismatch Handling

Google sometimes grants different scopes than requested. `_exchange_code()` catches `ValueError: Scope has changed` and extracts tokens from the OAuth session manually instead of crashing.

### Explicit Paths

Each consumer provides its own `credentials.json`, `token.json`, and scopes. No magic defaults.

## Commands

```bash
uv sync              # Install dependencies
uv run pytest        # Run tests (8 tests)
```

## Integration Pattern

```python
from jeton import authenticate, load_credentials

creds = load_credentials("./token.json")
if creds is None:
    creds = authenticate(
        "./credentials.json", "./token.json",
        ["https://www.googleapis.com/auth/drive"],
    )
```

## Security

**Never commit** `token.json` — it contains access/refresh tokens. `credentials.json` (OAuth client config) is safe to commit — it identifies the app, not the user.
