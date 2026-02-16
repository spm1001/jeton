# Jeton

Google OAuth library for [Batterie de Savoir](https://github.com/spm1001/batterie-de-savoir). Provides a consistent authentication pattern across Python and Node.js projects.

## Installation

```bash
# Install globally with pipx
pipx install ~/Repos/jeton

# Or for development
cd ~/Repos/jeton
uv sync
```

## CLI Usage

### Authenticate

```bash
# Basic auth with scopes
jeton --scopes drive.readonly gmail.readonly

# With explicit paths
jeton --credentials ./credentials.json --token ./token.json --scopes drive sheets

# Manual mode (for SSH/remote)
jeton --manual --scopes drive.readonly

# Non-interactive (for scripting/Claude Code)
jeton --manual --code "http://localhost:3000/oauth/callback?code=4/xxx" --scopes drive
```

### Check Status

```bash
jeton status
jeton status --token ./token.json
```

### Refresh Token

```bash
jeton refresh --token ./token.json
```

### List Scope Shortcuts

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

## Scope Shortcuts

Instead of full URLs, use shortcuts:

| Shortcut | Full Scope |
|----------|------------|
| `drive` | `https://www.googleapis.com/auth/drive` |
| `drive.readonly` | `https://www.googleapis.com/auth/drive.readonly` |
| `gmail.readonly` | `https://www.googleapis.com/auth/gmail.readonly` |
| `sheets` | `https://www.googleapis.com/auth/spreadsheets` |
| `slides` | `https://www.googleapis.com/auth/presentations` |
| `docs` | `https://www.googleapis.com/auth/documents` |
| `calendar` | `https://www.googleapis.com/auth/calendar` |
| `script.projects` | `https://www.googleapis.com/auth/script.projects` |

Run `jeton list-scopes` for the full list.

## Node.js Usage

Node.js projects don't use the library directly. Instead:

1. Run `jeton` to create `token.json`
2. Read the token in your Node.js code:

```javascript
const fs = require('fs');
const { google } = require('googleapis');

function getAuth() {
  const tokenPath = './token.json';
  const credsPath = './credentials.json';

  if (!fs.existsSync(tokenPath)) {
    console.error('No token.json - run: jeton --scopes drive script.projects');
    process.exit(1);
  }

  const credentials = JSON.parse(fs.readFileSync(credsPath));
  const { client_id, client_secret } = credentials.web;
  const token = JSON.parse(fs.readFileSync(tokenPath));

  const auth = new google.auth.OAuth2(client_id, client_secret);
  auth.setCredentials(token);

  // Auto-save refreshed tokens
  auth.on('tokens', (newTokens) => {
    const updated = { ...token, ...newTokens };
    fs.writeFileSync(tokenPath, JSON.stringify(updated, null, 2));
  });

  return auth;
}
```

## Authentication Modes

### Auto Mode (Default)

Starts a localhost server, opens browser automatically. Best for local development.

```bash
jeton --scopes drive
```

### Manual Mode

Prints URL, you paste the redirect URL back. For SSH/remote environments.

```bash
jeton --manual --scopes drive
```

### Non-Interactive Mode

For scripting and Claude Code integration. The `--code` flag accepts either the full redirect URL or just the authorization code.

```bash
# Get the auth URL first
jeton --manual --scopes drive
# (copy URL, authorize in browser, copy failed redirect URL)

# Then complete with code
jeton --manual --code "http://localhost:3000/oauth/callback?code=4/xxx" --scopes drive
```

## Setup

1. Create OAuth credentials in GCP Console:
   - Go to https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID (Web Application type)
   - Add `http://localhost:3000/oauth/callback` to authorized redirect URIs
   - Download as `credentials.json`

2. Enable required APIs in your GCP project

3. Run authentication:
   ```bash
   jeton --credentials ./credentials.json --scopes drive
   ```

## License

MIT License.
