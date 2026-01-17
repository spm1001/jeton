# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Purpose

Shared Google OAuth library for ITV tooling. Provides consistent authentication across:
- Python projects (direct API use, e.g., mcp-google-workspace)
- Node.js/Apps Script projects (via CLI → token.json, e.g., itv-slides-formatter)

## Architecture

```
itv_google_auth/
├── __init__.py     # Public API exports
├── auth.py         # Core: authenticate(), load_credentials(), TokenStatus
├── callback.py     # HTML templates for OAuth callback pages
└── cli.py          # Click CLI: itv-auth command
```

## Key Design Decisions

### Explicit Paths Over Defaults

Each project provides its own:
- `credentials.json` (from its own GCP project)
- `token.json` (output location)
- Scopes (only what that project needs)

No magic defaults like `~/.config/itv-tools/`. Keeps projects independent.

### Scope Shortcuts

Full URLs are verbose. Shortcuts like `drive.readonly` expand to full URLs:
```python
SCOPE_SHORTCUTS = {
    "drive.readonly": "https://www.googleapis.com/auth/drive.readonly",
    ...
}
```

### Dual-Mode Authentication

1. **Auto mode**: Localhost server at port 3000, auto-opens browser
2. **Manual mode**: Print URL, user pastes redirect URL back (for SSH)
3. **Non-interactive**: `--code` flag for scripting/Claude Code

### Scope Mismatch Handling

Google sometimes grants different scopes than requested (incremental auth). The `_exchange_code()` function catches `ValueError: Scope has changed` and extracts tokens manually from the OAuth session.

## Commands

```bash
# Development
uv sync                          # Install dependencies
uv run pytest                    # Run tests
uv run itv-auth --help           # Test CLI

# Install globally
pipx install .                   # From repo root
pipx install ~/Repos/itv-google-auth  # From anywhere
```

## Testing

Manual testing (requires credentials.json):
```bash
# Test auto mode
uv run itv-auth --scopes drive.readonly

# Test manual mode
uv run itv-auth --manual --scopes drive.readonly

# Test status
uv run itv-auth status --token ./token.json
```

## Integration with Other Projects

### Python Projects

```python
from itv_google_auth import authenticate, load_credentials

creds = load_credentials("./token.json", "./credentials.json")
if creds is None:
    creds = authenticate("./credentials.json", "./token.json", ["drive.readonly"])
```

### Node.js Projects

1. Add to `package.json`:
   ```json
   {
     "scripts": {
       "auth": "itv-auth --scopes drive script.projects"
     }
   }
   ```

2. Read token in code:
   ```javascript
   const token = JSON.parse(fs.readFileSync('./token.json'));
   auth.setCredentials(token);
   ```

## Related Projects

- **mcp-google-workspace**: Primary Python consumer (MCP tools for Claude)
- **itv-appscript-deploy**: Apps Script deployment CLI (uses this library directly)
- **itv-slides-formatter**: Apps Script project (uses itv-appscript-deploy for auth/deploy)

## Security

**Never commit:**
- `credentials.json` - OAuth client secrets
- `token.json` - Access/refresh tokens
- `.env` - Any environment secrets

Required `.gitignore`:
```
credentials.json
token.json
*.env*
```
