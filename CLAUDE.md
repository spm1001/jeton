# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Purpose

Jeton is the Google OAuth library for [Batterie de Savoir](https://github.com/spm1001/batterie-de-savoir) — a kitchen-metaphor toolkit for knowledge work. Jeton handles the tokens exchanged between front-of-house (the user) and kitchen (Google APIs).

Provides consistent authentication across:
- Python projects (direct API use, e.g., mise-en-space)
- Node.js/Apps Script projects (via CLI → token.json)

## Architecture

```
jeton/
├── __init__.py     # Public API exports
├── auth.py         # Core: authenticate(), load_credentials(), TokenStatus
├── callback.py     # HTML templates for OAuth callback pages
└── cli.py          # Click CLI: jeton command
```

## Key Design Decisions

### Explicit Paths Over Defaults

Each project provides its own:
- `credentials.json` (from its own GCP project)
- `token.json` (output location)
- Scopes (only what that project needs)

No magic defaults like `~/.config/jeton/`. Keeps projects independent.

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
uv run jeton --help              # Test CLI

# Install globally
uv tool install .                # From repo root
uv tool install ~/Repos/jeton   # From anywhere
```

## Testing

Manual testing (requires credentials.json):
```bash
# Test auto mode
uv run jeton --scopes drive.readonly

# Test manual mode
uv run jeton --manual --scopes drive.readonly

# Test status
uv run jeton status --token ./token.json
```

## Integration with Other Projects

### Python Projects

```python
from jeton import authenticate, load_credentials

creds = load_credentials("./token.json", "./credentials.json")
if creds is None:
    creds = authenticate("./credentials.json", "./token.json", ["drive.readonly"])
```

### Node.js Projects

1. Add to `package.json`:
   ```json
   {
     "scripts": {
       "auth": "jeton --scopes drive script.projects"
     }
   }
   ```

2. Read token in code:
   ```javascript
   const token = JSON.parse(fs.readFileSync('./token.json'));
   auth.setCredentials(token);
   ```

## Related Projects

- **mise-en-space**: Primary Python consumer (Google Workspace MCP for Claude)
- Other Batterie de Savoir tools that need Google API access

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
