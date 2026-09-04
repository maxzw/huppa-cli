import functools
import json
import os
import sys
from datetime import datetime

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from huppa_cli.client import HuppaClient, HuppaError
from huppa_cli.credentials import (
    clear_credentials,
    keyring_backend_name,
    load_credentials,
    mask_secret,
    prompt_for_credentials,
    save_credentials,
)
from huppa_cli.update import UpdateError, update as update_package
from huppa_cli.version import get_version

load_dotenv()


def _get_client() -> HuppaClient:
    profile = os.getenv("HUPPA_PROFILE", "default")
    return HuppaClient.from_profile(profile=profile)


def _json_output(data) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


def _rich_print(renderable) -> None:
    Console(file=sys.stdout).print(renderable)


def _status_table(result: dict) -> Table:
    table = Table(title="Huppa status", show_lines=False, header_style="bold cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value")
    for key, value in result.items():
        style = "green" if key == "api" and value == "reachable" else "red" if key == "api" else None
        table.add_row(key, str(value), style=style)
    return table


def _class_table(classes, title: str) -> Table:
    table = Table(title=title, show_lines=False, header_style="bold cyan")
    table.add_column("Time", style="bold", no_wrap=True)
    table.add_column("Class", style="white")
    table.add_column("Category", style="magenta")
    table.add_column("Spaces", justify="right", style="green")
    table.add_column("Status", style="yellow")
    for item in classes:
        status = "Booked" if item["is_booked"] else "Waitlist" if item["is_on_waitlist"] else "Open"
        table.add_row(
            item["starts_at"].split(" ", 1)[-1],
            item["name"],
            item["category"],
            str(item["available_slots"]),
            status,
        )
    return table


def _booking_table(bookings) -> Table:
    table = Table(title="Bookings", show_lines=False, header_style="bold cyan")
    table.add_column("Date", style="bold", no_wrap=True)
    table.add_column("Class")
    table.add_column("Category", style="magenta")
    table.add_column("Status", style="yellow")
    for item in bookings:
        table.add_row(item["starts_at"], item["name"], item["category"], item["booking_status"] or "Waitlist")
    return table


def _membership_table(memberships) -> Table:
    table = Table(title="Memberships", show_lines=False, header_style="bold cyan")
    table.add_column("Membership", style="bold")
    table.add_column("Status", style="green")
    table.add_column("Credits", justify="right")
    for item in memberships:
        table.add_row(item["name"], item["status"], f"{item['credits']}/{item['total_credits']}")
    return table


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
    _rich_print(f"[bold cyan]huppa[/bold cyan] {get_version()}")


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
    _rich_print(_status_table(result))


@cli.command("update")
@click.option("--check", "check_only", is_flag=True, help="Only check for an update; do not install it.")
@click.option("--force", is_flag=True, help="Reinstall the latest release even when already current.")
def update_command(check_only, force):
    """Check for and install the latest Huppa CLI release."""
    try:
        update_package(
            check_only=check_only,
            force=force,
            output=click.echo,
        )
    except UpdateError as exc:
        raise click.ClickException(str(exc)) from exc


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
    _rich_print(f"[green]Saved credentials to keychain profile '{profile}'.[/green]")


@auth.command()
def logout():
    """Clear stored credentials."""
    profile = os.getenv("HUPPA_PROFILE", "default")
    clear_credentials(profile=profile)
    _rich_print(f"[yellow]Cleared credentials for profile '{profile}'.[/yellow]")


@auth.command()
def whoami():
    """Show current profile and email."""
    profile = os.getenv("HUPPA_PROFILE", "default")
    creds = load_credentials(profile=profile)
    if not creds:
        _rich_print(f"[yellow]No saved credentials found for profile '{profile}'.[/yellow]")
        raise SystemExit(1)
    table = Table(title=f"Profile · {profile}", show_lines=False, header_style="bold cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value")
    table.add_row("Email", creds["email"])
    table.add_row("Subdomain", creds["subdomain"])
    _rich_print(table)


# --- business commands ---


@cli.command()
@click.argument("dates", nargs=-1, required=True)
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON instead of a table.")
@_handle_errors
def classes(dates, as_json):
    """List available gym classes for one or more dates (YYYY-MM-DD)."""
    for d in dates:
        _validate_date(d)
    client = _get_client()
    if len(dates) == 1:
        result = [c.model_dump() for c in client.get_classes(dates[0])]
        if not as_json:
            _rich_print(_class_table(result, f"Classes · {dates[0]}"))
            return
    else:
        result = {}
        for d in dates:
            result[d] = [c.model_dump() for c in client.get_classes(d)]
        if not as_json:
            for d, items in result.items():
                _rich_print(_class_table(items, f"Classes · {d}"))
            return
    _json_output(result)


@cli.command()
@click.option("--filter", "booking_filter", type=click.Choice(["upcoming", "past"]), default="upcoming")
@click.option("--per-page", default=50, type=int)
@click.option("--page", default=1, type=int)
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON instead of a table.")
@_handle_errors
def bookings(booking_filter, per_page, page, as_json):
    """List your bookings and waitlists."""
    client = _get_client()
    result = [b.model_dump() for b in client.get_my_bookings(filter=booking_filter, per_page=per_page, page=page)]
    _json_output(result) if as_json else _rich_print(_booking_table(result))


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Print structured JSON instead of a table.")
@_handle_errors
def memberships(as_json):
    """Show memberships, credit balances, and payment dates."""
    client = _get_client()
    result = [m.model_dump() for m in client.get_memberships()]
    _json_output(result) if as_json else _rich_print(_membership_table(result))


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
