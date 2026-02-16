# Jeton

Google OAuth token management for [Batterie de Savoir](https://github.com/spm1001/batterie-de-savoir) and any Python project that needs Google API access. Handles the full OAuth 2.0 flow — browser-based, manual (SSH/remote), or non-interactive (scripting/Claude Code) — and manages token refresh automatically.

## Installation

```bash
# From GitHub
uv pip install git+https://github.com/spm1001/jeton.git

# Or clone for development
git clone https://github.com/spm1001/jeton.git
cd jeton
uv sync
```

As a dependency in your `pyproject.toml`:

```toml
[project]
dependencies = ["jeton"]

[tool.uv.sources]
jeton = { git = "https://github.com/spm1001/jeton.git" }
```

## Prerequisites: Google Cloud Setup

Before using jeton, you need OAuth client credentials from a Google Cloud project.

1. **Create or select a GCP project** at [console.cloud.google.com](https://console.cloud.google.com)

2. **Enable the APIs** you need. Common ones:
   - Google Drive API
   - Gmail API
   - Google Docs API
   - Google Sheets API
   - Google Slides API
   - Google Calendar API

3. **Configure the OAuth consent screen** ([APIs & Services > OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)):
   - User type: External (or Internal if using Google Workspace)
   - Add the scopes your application needs
   - Add test users if the app is in "Testing" mode

4. **Create OAuth credentials** ([APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)):
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: **Web application**
   - Add `http://localhost:3000/oauth/callback` to "Authorized redirect URIs"
   - Download the JSON file and save it as `credentials.json`

## Usage

### Authenticate

```bash
# Auto mode — opens browser, handles callback automatically
jeton --credentials ./credentials.json --scopes drive.readonly gmail.readonly

# Manual mode — prints URL, you paste the redirect URL back
# Use this for SSH, remote servers, or Claude Code
jeton --manual --scopes drive.readonly

# Non-interactive — provide the auth code directly
jeton --manual --code "http://localhost:3000/oauth/callback?code=4/xxx" --scopes drive
```

### Check Token Status

```bash
jeton status
jeton status --token ./token.json
```

### Refresh Token

```bash
jeton refresh --token ./token.json
```

### List Available Scopes

```bash
jeton list-scopes
```

## Python API

```python
from jeton import authenticate, load_credentials, TokenStatus

# Load existing credentials (returns None if invalid/missing)
creds = load_credentials("./token.json", "./credentials.json")

# Run OAuth flow if needed
if creds is None:
    creds = authenticate(
        credentials_path="./credentials.json",
        token_path="./token.json",
        scopes=["drive.readonly", "gmail.readonly"],
    )

# Use with Google API client
from googleapiclient.discovery import build
service = build("drive", "v3", credentials=creds)

# Check token status without loading
status = TokenStatus.check("./token.json")
print(f"Valid: {status.valid}, Expires in: {status.expires_in}")
```

## Authentication Modes

| Mode | Flag | Use case |
|------|------|----------|
| **Auto** (default) | — | Local development. Starts localhost server, opens browser. |
| **Manual** | `--manual` | SSH, remote, headless. Prints URL, you paste the redirect back. |
| **Non-interactive** | `--manual --code URL` | Scripting, CI, Claude Code. Provide the code directly. |

## Scope Shortcuts

Instead of full Google OAuth URLs, use shortcuts:

| Shortcut | Full Scope |
|----------|------------|
| `drive` | `https://www.googleapis.com/auth/drive` |
| `drive.readonly` | `https://www.googleapis.com/auth/drive.readonly` |
| `gmail.readonly` | `https://www.googleapis.com/auth/gmail.readonly` |
| `sheets` | `https://www.googleapis.com/auth/spreadsheets` |
| `slides` | `https://www.googleapis.com/auth/presentations` |
| `docs` | `https://www.googleapis.com/auth/documents` |
| `calendar` | `https://www.googleapis.com/auth/calendar` |
| `contacts.readonly` | `https://www.googleapis.com/auth/contacts.readonly` |
| `script.projects` | `https://www.googleapis.com/auth/script.projects` |

Run `jeton list-scopes` for the full list.

## Node.js Usage

Node.js projects use jeton as a CLI tool to generate `token.json`, then read the token directly:

```bash
jeton --scopes drive script.projects
```

```javascript
const fs = require('fs');
const { google } = require('googleapis');

const credentials = JSON.parse(fs.readFileSync('./credentials.json'));
const token = JSON.parse(fs.readFileSync('./token.json'));

const auth = new google.auth.OAuth2(
  credentials.web.client_id,
  credentials.web.client_secret
);
auth.setCredentials(token);

// Auto-save refreshed tokens
auth.on('tokens', (newTokens) => {
  const updated = { ...token, ...newTokens };
  fs.writeFileSync('./token.json', JSON.stringify(updated, null, 2));
});
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `redirect_uri_mismatch` | Add `http://localhost:3000/oauth/callback` to your OAuth client's redirect URIs in GCP Console |
| `access_denied` | Check that your email is listed as a test user on the OAuth consent screen |
| `API not enabled` | Enable the required API in [APIs & Services > Library](https://console.cloud.google.com/apis/library) |
| Token expired, no refresh | Re-run `jeton --scopes ...` to get a new token with a refresh token |

## About the Name

In a professional kitchen, a *jeton* is a token exchanged between front-of-house and kitchen to track orders. Jeton manages the tokens exchanged between your application (front-of-house) and Google's APIs (the kitchen). It's part of [Batterie de Savoir](https://github.com/spm1001/batterie-de-savoir), a suite of knowledge-work tools that follow a culinary naming convention.

## License

[MIT](LICENSE)
