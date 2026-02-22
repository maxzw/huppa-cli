import os
from datetime import datetime

from dotenv import load_dotenv
from huppa_cli.client import HuppaAPIError, HuppaAuthError, HuppaClient, HuppaError
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Huppa")

_client: HuppaClient | None = None


def get_client() -> HuppaClient:
    """Return a cached, authenticated Huppa client instance.

    Credentials are resolved by ``HuppaClient.from_profile``.

    Raises:
        RuntimeError: If no complete credential set is available.
    """
    global _client
    if _client is None:
        profile = os.getenv("HUPPA_PROFILE", "default")
        _client = HuppaClient.from_profile(profile=profile)
    return _client


def _validate_date(date: str) -> None:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.") from exc


def _validate_filter(value: str) -> None:
    if value not in {"past", "upcoming"}:
        raise ValueError("Invalid filter. Use 'past' or 'upcoming'.")


def _run_with_normalized_errors(func):
    try:
        return func()
    except HuppaAuthError as exc:
        raise RuntimeError(f"Authentication error: {exc}") from exc
    except HuppaAPIError as exc:
        raise RuntimeError(f"Huppa API error: {exc}") from exc
    except HuppaError as exc:
        raise RuntimeError(f"Huppa client error: {exc}") from exc


@mcp.tool()
def get_classes(date: str) -> list[dict]:
    """Get available gym classes for a given date.

    Args:
        date: Date in ``YYYY-MM-DD`` format.

    Returns:
        A list of class payloads.
    """
    _validate_date(date)

    def _execute() -> list[dict]:
        client = get_client()
        classes = client.get_classes(date)
        return [c.model_dump() for c in classes]

    return _run_with_normalized_errors(_execute)


@mcp.tool()
def get_classes_multiple_dates(list_of_dates: list[str]) -> dict[str, list[dict]]:
    """Get mapping of dates to available gym classes for multiple dates.

    Args:
        list_of_dates: A list of dates in ``YYYY-MM-DD`` format.

    Returns:
        A mapping of date strings to lists of class payloads.
    """
    for date in list_of_dates:
        _validate_date(date)

    def _execute() -> dict[str, list[dict]]:
        client = get_client()
        result = {}
        for date in list_of_dates:
            classes = client.get_classes(date)
            result[date] = [c.model_dump() for c in classes]
        return result

    return _run_with_normalized_errors(_execute)


@mcp.tool()
def book_class(organization_id: str, occurrence_id: str) -> dict | None:
    """Book a gym class occurrence.

    Args:
        organization_id: Organization identifier from ``get_classes``.
        occurrence_id: Class occurrence identifier from ``get_classes``.

    Returns:
        Booking response payload when present, otherwise ``None``.
    """
    return _run_with_normalized_errors(lambda: get_client().book_class(organization_id, occurrence_id))


@mcp.tool()
def cancel_booking(organization_id: str, occurrence_id: str) -> dict | None:
    """Cancel an existing gym class booking.

    Args:
        organization_id: Organization identifier for the booking.
        occurrence_id: Class occurrence identifier for the booking.

    Returns:
        Cancellation response payload when present, otherwise ``None``.
    """
    return _run_with_normalized_errors(lambda: get_client().cancel_booking(organization_id, occurrence_id))


@mcp.tool()
def join_waitlist(organization_id: str, occurrence_id: str) -> dict | None:
    """Join the waitlist for a class occurrence.

    Args:
        organization_id: Organization identifier for the class.
        occurrence_id: Class occurrence identifier.

    Returns:
        Waitlist join response payload when present, otherwise ``None``.
    """
    return _run_with_normalized_errors(lambda: get_client().join_waitlist(organization_id, occurrence_id))


@mcp.tool()
def leave_waitlist(organization_id: str, occurrence_id: str) -> dict | None:
    """Leave the waitlist for a class occurrence.

    Args:
        organization_id: Organization identifier for the class.
        occurrence_id: Class occurrence identifier.

    Returns:
        Waitlist leave response payload when present, otherwise ``None``.
    """
    return _run_with_normalized_errors(lambda: get_client().leave_waitlist(organization_id, occurrence_id))


@mcp.tool()
def get_my_bookings(filter: str = "upcoming", per_page: int = 50, page: int = 1) -> list[dict]:
    """Get the user's past or upcoming bookings and waitlists.

    Args:
        filter: 'past' or 'upcoming' (default: 'upcoming').
        per_page: Number of results per page (default: 50).
        page: Page number (default: 1).

    Returns:
        A list of booking payloads.
    """
    _validate_filter(filter)

    def _execute() -> list[dict]:
        client = get_client()
        bookings = client.get_my_bookings(filter=filter, per_page=per_page, page=page)
        return [b.model_dump() for b in bookings]

    return _run_with_normalized_errors(_execute)


@mcp.tool()
def get_memberships() -> list[dict]:
    """Get memberships, including credit balances and payment dates.

    Returns:
        A list of membership payloads.
    """

    def _execute() -> list[dict]:
        client = get_client()
        memberships = client.get_memberships()
        return [m.model_dump() for m in memberships]

    return _run_with_normalized_errors(_execute)


def run_mcp() -> None:
    """Start the MCP server."""
    mcp.run()
