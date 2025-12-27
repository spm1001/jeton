"""CLI for itv-google-auth."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from itv_google_auth.auth import (
    SCOPE_SHORTCUTS,
    TokenStatus,
    authenticate,
    expand_scopes,
    load_credentials,
)


@click.group(invoke_without_command=True)
@click.option(
    "--credentials", "-c",
    type=click.Path(exists=False),
    default="./credentials.json",
    help="Path to credentials.json from GCP Console",
)
@click.option(
    "--token", "-t",
    type=click.Path(),
    default="./token.json",
    help="Path to save/load token.json",
)
@click.option(
    "--scopes", "-s",
    multiple=True,
    help="OAuth scopes (can use shortcuts like 'drive.readonly')",
)
@click.option(
    "--manual", "-m",
    is_flag=True,
    help="Manual mode: paste redirect URL instead of localhost server",
)
@click.option(
    "--code",
    type=str,
    default=None,
    help="Pre-provided auth code or redirect URL (for non-interactive use)",
)
@click.option(
    "--port", "-p",
    type=int,
    default=3000,
    help="Port for localhost callback server (default: 3000)",
)
@click.pass_context
def main(ctx, credentials, token, scopes, manual, code, port):
    """Google OAuth authentication for ITV tooling.

    Run without subcommand to authenticate:

        itv-auth --credentials ./credentials.json --scopes drive.readonly

    Or check token status:

        itv-auth status --token ./token.json

    \b
    Available scope shortcuts:
        drive, drive.readonly, drive.file
        gmail, gmail.readonly, gmail.send
        sheets, sheets.readonly
        slides, slides.readonly
        docs, docs.readonly
        calendar, calendar.readonly
        contacts.readonly, directory.readonly
        script.projects, script.deployments
        logging.read
    """
    # If no subcommand, run auth flow
    if ctx.invoked_subcommand is None:
        # Require scopes for auth
        if not scopes:
            click.echo("Error: --scopes required for authentication", err=True)
            click.echo("Example: itv-auth --scopes drive.readonly gmail.readonly", err=True)
            click.echo("\nUse 'itv-auth --help' for available scope shortcuts", err=True)
            sys.exit(1)

        try:
            authenticate(
                credentials_path=credentials,
                token_path=token,
                scopes=list(scopes),
                manual_mode=manual or bool(code),
                code=code,
                port=port,
            )
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except (ValueError, TimeoutError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except KeyboardInterrupt:
            click.echo("\nAuthentication cancelled", err=True)
            sys.exit(1)


@main.command()
@click.option(
    "--token", "-t",
    type=click.Path(),
    default="./token.json",
    help="Path to token.json",
)
@click.option(
    "--credentials", "-c",
    type=click.Path(exists=False),
    default="./credentials.json",
    help="Path to credentials.json (for refresh check)",
)
def status(token, credentials):
    """Check the status of an existing token."""
    token_status = TokenStatus.check(token)

    if not token_status.exists:
        click.echo(f"Token: {token}")
        click.echo("Status: NOT FOUND")
        click.echo("\nRun 'itv-auth --scopes ...' to authenticate")
        sys.exit(1)

    click.echo(f"Token: {token}")

    if token_status.valid:
        click.echo("Status: VALID")
    elif token_status.expired and token_status.can_refresh:
        click.echo("Status: EXPIRED (can refresh)")
    else:
        click.echo("Status: INVALID")

    if token_status.expires_at:
        click.echo(f"Expires: {token_status.expires_at.isoformat()}")
        if token_status.expires_in:
            hours = token_status.expires_in.total_seconds() / 3600
            if hours > 24:
                click.echo(f"Expires in: {hours / 24:.1f} days")
            else:
                click.echo(f"Expires in: {hours:.1f} hours")

    click.echo(f"Can refresh: {'Yes' if token_status.can_refresh else 'No'}")

    if token_status.scopes:
        click.echo(f"Scopes ({len(token_status.scopes)}):")
        for scope in sorted(token_status.scopes):
            # Show shortcut if available
            shortcut = next(
                (k for k, v in SCOPE_SHORTCUTS.items() if v == scope),
                None
            )
            if shortcut:
                click.echo(f"  - {shortcut} ({scope})")
            else:
                click.echo(f"  - {scope}")

    if token_status.error:
        click.echo(f"Error: {token_status.error}")
        sys.exit(1)


@main.command()
@click.option(
    "--token", "-t",
    type=click.Path(),
    default="./token.json",
    help="Path to token.json",
)
@click.option(
    "--credentials", "-c",
    type=click.Path(exists=False),
    default="./credentials.json",
    help="Path to credentials.json",
)
def refresh(token, credentials):
    """Force refresh an existing token."""
    token_path = Path(token)
    credentials_path = Path(credentials)

    if not token_path.exists():
        click.echo(f"Error: Token file not found: {token}", err=True)
        sys.exit(1)

    # Load and refresh
    creds = load_credentials(token_path, credentials_path)

    if creds is None:
        click.echo("Error: Could not load or refresh token", err=True)
        click.echo("Run 'itv-auth --scopes ...' to re-authenticate", err=True)
        sys.exit(1)

    click.echo(f"Token refreshed: {token}")
    if creds.expiry:
        click.echo(f"New expiry: {creds.expiry.isoformat()}")


@main.command("list-scopes")
def list_scopes():
    """List all available scope shortcuts."""
    click.echo("Available scope shortcuts:")
    click.echo()

    # Group by category
    categories = {
        "Drive": ["drive", "drive.readonly", "drive.file"],
        "Gmail": ["gmail", "gmail.readonly", "gmail.send"],
        "Sheets": ["sheets", "sheets.readonly"],
        "Slides": ["slides", "slides.readonly"],
        "Docs": ["docs", "docs.readonly"],
        "Calendar": ["calendar", "calendar.readonly"],
        "Contacts": ["contacts.readonly", "directory.readonly", "admin.directory.user.readonly"],
        "Apps Script": ["script.projects", "script.deployments"],
        "Logging": ["logging.read"],
    }

    for category, shortcuts in categories.items():
        click.echo(f"{category}:")
        for shortcut in shortcuts:
            if shortcut in SCOPE_SHORTCUTS:
                click.echo(f"  {shortcut:30} {SCOPE_SHORTCUTS[shortcut]}")
        click.echo()


if __name__ == "__main__":
    main()
