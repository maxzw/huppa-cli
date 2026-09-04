import functools
import json
import os
from datetime import datetime

import click
from dotenv import load_dotenv
from huppa_cli.client import HuppaClient, HuppaError
from huppa_cli.credentials import (
    clear_credentials,
    keyring_backend_name,
    load_credentials,
    mask_secret,
    prompt_for_credentials,
    save_credentials,
)
from huppa_cli.version import get_version

load_dotenv()


def _get_client() -> HuppaClient:
    profile = os.getenv("HUPPA_PROFILE", "default")
    return HuppaClient.from_profile(profile=profile)


def _json_output(data) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


def _validate_date(date: str) -> None:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise click.BadParameter(f"Invalid date format '{date}'. Use YYYY-MM-DD.") from exc


def _handle_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HuppaError as exc:
            raise click.ClickException(str(exc))

    return wrapper


@click.group()
def cli():
    """Huppa CLI — browse, book, and manage gym classes."""


@cli.command()
def version():
    """Show the installed Huppa CLI version."""
    click.echo(f"huppa {get_version()}")


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Print status as JSON.")
@_handle_errors
def status(as_json):
    """Show credential, keyring, and API connection status."""
    profile = os.getenv("HUPPA_PROFILE", "default")
    env_values = {
        "email": os.getenv("HUPPA_EMAIL"),
        "password": os.getenv("HUPPA_PASSWORD"),
        "subdomain": os.getenv("HUPPA_SUBDOMAIN"),
    }
    use_environment = all(env_values.values())
    try:
        credentials = None if use_environment else load_credentials(profile=profile)
    except RuntimeError as exc:
        credentials = None
        keyring_error = str(exc)
    else:
        keyring_error = None
    use_keyring = not use_environment and credentials is not None
    values = env_values if use_environment else (credentials or env_values)
    source = "environment" if use_environment else "keyring" if use_keyring else "partial/missing"
    result = {
        "version": get_version(),
        "profile": profile,
        "email": values.get("email") or None,
        "subdomain": values.get("subdomain") or None,
        "password": mask_secret(values.get("password")),
        "password_configured": bool(values.get("password")),
        "credential_source": source,
        "keyring_backend": keyring_error or keyring_backend_name(),
        "config_path": str(click.get_app_dir("huppa")),
        "api": "not checked",
    }
    if values.get("email") and values.get("password") and values.get("subdomain"):
        try:
            _get_client()
        except (HuppaError, RuntimeError) as exc:
            result["api"] = f"error: {exc}"
        else:
            result["api"] = "reachable"
    if as_json:
        _json_output(result)
        return
    for key, value in result.items():
        click.echo(f"{key}: {value}")


# --- auth subgroup ---


@cli.group()
def auth():
    """Manage Huppa authentication credentials."""


@auth.command()
def setup():
    """Interactive credential setup (stores in OS keychain)."""
    profile = os.getenv("HUPPA_PROFILE", "default")
    creds = prompt_for_credentials()
    try:
        HuppaClient(creds["email"], creds["password"], creds["subdomain"])
    except HuppaError as exc:
        raise click.ClickException(f"Login failed: {exc}")
    save_credentials(
        email=creds["email"],
        password=creds["password"],
        subdomain=creds["subdomain"],
        profile=profile,
    )
    click.echo(f"Saved credentials to keychain profile '{profile}'.")


@auth.command()
def logout():
    """Clear stored credentials."""
    profile = os.getenv("HUPPA_PROFILE", "default")
    clear_credentials(profile=profile)
    click.echo(f"Cleared credentials for profile '{profile}'.")


@auth.command()
def whoami():
    """Show current profile and email."""
    profile = os.getenv("HUPPA_PROFILE", "default")
    creds = load_credentials(profile=profile)
    if not creds:
        click.echo(f"No saved credentials found for profile '{profile}'.")
        raise SystemExit(1)
    click.echo(f"Profile: {profile}")
    click.echo(f"Email: {creds['email']}")
    click.echo(f"Subdomain: {creds['subdomain']}")


# --- business commands ---


@cli.command()
@click.argument("dates", nargs=-1, required=True)
@_handle_errors
def classes(dates):
    """List available gym classes for one or more dates (YYYY-MM-DD)."""
    for d in dates:
        _validate_date(d)
    client = _get_client()
    if len(dates) == 1:
        result = [c.model_dump() for c in client.get_classes(dates[0])]
    else:
        result = {}
        for d in dates:
            result[d] = [c.model_dump() for c in client.get_classes(d)]
    _json_output(result)


@cli.command()
@click.option("--filter", "booking_filter", type=click.Choice(["upcoming", "past"]), default="upcoming")
@click.option("--per-page", default=50, type=int)
@click.option("--page", default=1, type=int)
@_handle_errors
def bookings(booking_filter, per_page, page):
    """List your bookings and waitlists."""
    client = _get_client()
    result = [b.model_dump() for b in client.get_my_bookings(filter=booking_filter, per_page=per_page, page=page)]
    _json_output(result)


@cli.command()
@_handle_errors
def memberships():
    """Show memberships, credit balances, and payment dates."""
    client = _get_client()
    result = [m.model_dump() for m in client.get_memberships()]
    _json_output(result)


@cli.command()
@click.argument("organization_id")
@click.argument("occurrence_id")
@_handle_errors
def book(organization_id, occurrence_id):
    """Book a gym class occurrence."""
    client = _get_client()
    result = client.book_class(organization_id, occurrence_id)
    _json_output(result)


@cli.command()
@click.argument("organization_id")
@click.argument("occurrence_id")
@_handle_errors
def cancel(organization_id, occurrence_id):
    """Cancel an existing gym class booking."""
    client = _get_client()
    result = client.cancel_booking(organization_id, occurrence_id)
    _json_output(result)


# --- waitlist subgroup ---


@cli.group()
def waitlist():
    """Manage class waitlists."""


@waitlist.command("join")
@click.argument("organization_id")
@click.argument("occurrence_id")
@_handle_errors
def waitlist_join(organization_id, occurrence_id):
    """Join the waitlist for a class."""
    client = _get_client()
    result = client.join_waitlist(organization_id, occurrence_id)
    _json_output(result)


@waitlist.command("leave")
@click.argument("organization_id")
@click.argument("occurrence_id")
@_handle_errors
def waitlist_leave(organization_id, occurrence_id):
    """Leave the waitlist for a class."""
    client = _get_client()
    result = client.leave_waitlist(organization_id, occurrence_id)
    _json_output(result)


# --- mcp subcommand ---


@cli.command()
def mcp():
    """Start the MCP server (stdio transport)."""
    from huppa_cli.server import run_mcp

    run_mcp()


def main():
    cli()
