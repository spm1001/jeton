# Jeton

Google OAuth for Python projects. Two functions, three auth modes, auto-refresh.

**Why this exists:** `google-auth-oauthlib` provides `InstalledAppFlow.run_local_server()` for browser-based OAuth, but has no support for SSH/remote sessions or non-interactive scripting. Jeton adds manual mode (paste the redirect URL) and code mode (pass the auth code directly) — the two flows you need when Claude Code, CI, or an SSH session is doing the authenticating.

## Install

```toml
# pyproject.toml
[project]
dependencies = ["jeton"]

[tool.uv.sources]
jeton = { git = "https://github.com/spm1001/jeton.git" }
```

> **⚠️ The git pin is mandatory, not stylistic.** The `jeton` name on PyPI
> belongs to someone else's empty placeholder (0.1.0, Nov 2025, unrelated).
> A bare `pip install jeton`, `uv add jeton`, or `uvx --from jeton` resolves
> to that package and fails later with `cannot import name 'authenticate'`.
> Always install from the git URL:
> `uvx --from 'jeton @ git+https://github.com/spm1001/jeton.git' …`

## Usage

```python
from jeton import authenticate, load_credentials

# Load existing token (auto-refreshes if expired)
creds = load_credentials("./token.json")

# If no token exists, run the OAuth flow
if creds is None:
    creds = authenticate(
        credentials_path="./credentials.json",
        token_path="./token.json",
        scopes=["https://www.googleapis.com/auth/drive"],
    )

# Use with Google API client
from googleapiclient.discovery import build
service = build("drive", "v3", credentials=creds)
```

## Auth Modes

| Mode | When | How |
|------|------|-----|
| **Auto** (default) | Local machine with browser | Opens browser, localhost server receives callback |
| **Manual** | SSH, remote, headless | Prints URL, user pastes redirect URL back |
| **Non-interactive** | Claude Code, CI, scripting | Pass `code=` argument directly |

```python
# Auto — opens browser
authenticate(creds_path, token_path, scopes)

# Manual — paste URL
authenticate(creds_path, token_path, scopes, manual_mode=True)

# Non-interactive — provide code
authenticate(creds_path, token_path, scopes, code="4/0Abc...")
```

## Post-Auth Screen

For flows that need a follow-up action (e.g., copy a project number), pass `post_auth`:

```python
authenticate(
    creds_path, token_path, scopes,
    post_auth={
        "copy_value": "123456789",
        "copy_label": "GCP Project Number",
        "message": "Paste this in Apps Script settings",
        "button_url": "https://script.google.com/...",
        "button_label": "Open Settings",
    },
)
```

In auto mode, this renders on the callback page. In manual mode, it prints to the terminal.

## About the Name

In a professional kitchen, a *jeton* is a token exchanged between front-of-house and kitchen to track orders. Part of [Batterie de Savoir](https://github.com/spm1001/batterie-de-savoir).

## License

[MIT](LICENSE)
