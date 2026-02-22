import os
from typing import Callable

import requests
from huppa_cli.credentials import load_credentials
from huppa_cli.schemas import AvailableClass, Booking, Membership
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api.huppa.app"


class HuppaError(Exception):
    pass


class HuppaAuthError(HuppaError):
    pass


class HuppaAPIError(HuppaError):
    pass


class HuppaClient:
    @classmethod
    def from_profile(cls, profile: str = "default") -> "HuppaClient":
        """Create a client by resolving credentials from env vars or keychain.

        Resolution order is environment variables first and then keychain profile.

        Args:
            profile: Credential profile name used for keychain lookup.

        Returns:
            An authenticated :class:`HuppaClient` instance.

        Raises:
            RuntimeError: If no complete credential set is available.
        """
        email = os.getenv("HUPPA_EMAIL")
        password = os.getenv("HUPPA_PASSWORD")
        subdomain = os.getenv("HUPPA_SUBDOMAIN")

        if not email or not password or not subdomain:
            creds = load_credentials(profile=profile)
            if creds:
                email = creds["email"]
                password = creds["password"]
                subdomain = creds["subdomain"]

        if not email or not password or not subdomain:
            raise RuntimeError(
                "Missing Huppa credentials. Run 'huppa auth setup' or set HUPPA_EMAIL, HUPPA_PASSWORD, and HUPPA_SUBDOMAIN."
            )

        return cls(email=email, password=password, subdomain=subdomain)

    def __init__(self, email: str, password: str, subdomain: str):
        """Initialize an authenticated Huppa API client.

        This constructor configures a persistent HTTP session, applies default headers,
        enables retry behavior for transient failures, and performs an initial login.

        Args:
            email: Huppa account email.
            password: Huppa account password.
            subdomain: Huppa gym subdomain (for example, ``mygym``).

        Raises:
            HuppaAuthError: If authentication fails.
            HuppaAPIError: If the login endpoint is unreachable or returns an error.
        """
        self._email = email
        self._subdomain = subdomain
        self._password_provider: Callable[[], str] = lambda: password
        self.session = requests.Session()
        self.timeout = (5, 20)
        origin = f"https://{subdomain}.huppa.app"
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Subdomain": subdomain,
                "Origin": origin,
                "Referer": f"{origin}/",
            }
        )
        retries = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST", "DELETE"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._login()

    def _login(self) -> None:
        """POST email/password; the session captures the set-cookie automatically."""
        password = self._password_provider()
        try:
            resp = self.session.post(
                f"{BASE_URL}/auth/login",
                json={"email": self._email, "password": password},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise HuppaAPIError(f"Could not reach Huppa login endpoint: {exc}") from exc

        if resp.status_code in {401, 403}:
            raise HuppaAuthError("Authentication failed. Check your Huppa email/password/subdomain.")
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise HuppaAPIError(f"Login failed with status {resp.status_code}.") from exc

        if not self.session.cookies.get("api-auth-token"):
            raise HuppaAuthError("Login succeeded but no session token was set.")

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make a request; re-login once on 401."""
        kwargs.setdefault("timeout", self.timeout)
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.Timeout as exc:
            raise HuppaAPIError("Request to Huppa timed out. Please try again.") from exc
        except requests.ConnectionError as exc:
            raise HuppaAPIError("Could not connect to Huppa. Check your internet connection.") from exc
        except requests.RequestException as exc:
            raise HuppaAPIError(f"Request to Huppa failed: {exc}") from exc

        if resp.status_code == 401:
            self._login()
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                raise HuppaAPIError(f"Request failed after re-authentication: {exc}") from exc

        if resp.status_code in {401, 403}:
            raise HuppaAuthError("Authentication failed. Re-run 'huppa auth setup' to refresh credentials.")

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            detail = resp.text.strip()[:300]
            raise HuppaAPIError(f"Huppa API error {resp.status_code}: {detail}") from exc
        return resp

    def _json_or_none(self, resp: requests.Response) -> dict | None:
        """Return a JSON object payload when present, otherwise ``None``.

        This handles empty response bodies and non-JSON payloads without raising.
        """
        if not resp.content or not resp.content.strip():
            return None
        try:
            payload = resp.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    def get_classes(self, date: str) -> list[AvailableClass]:
        """Return available class occurrences for a specific date.

        Args:
            date: Date in ``YYYY-MM-DD`` format.

        Returns:
            A list of parsed :class:`AvailableClass` objects.

        Raises:
            HuppaAuthError: If the request is unauthorized.
            HuppaAPIError: If the request fails or the API returns an error.
        """
        url = f"{BASE_URL}/users/me/occurrences"
        resp = self._request("GET", url, params={"date": date})
        return [AvailableClass.model_validate(c) for c in resp.json().get("data", [])]

    def get_my_bookings(self, filter: str = "upcoming", per_page: int = 50, page: int = 1) -> list[Booking]:
        """Return the user's bookings and waitlists.

        Args:
            filter: 'past' or 'upcoming'.
            per_page: Number of results per page.
            page: Page number.

        Returns:
            A flattened list of parsed :class:`Booking` objects.

        Raises:
            HuppaAuthError: If the request is unauthorized.
            HuppaAPIError: If the request fails or the API returns an error.
        """
        url = f"{BASE_URL}/users/me/bookings-and-waitlists"
        resp = self._request("GET", url, params={"filter": filter, "per_page": per_page, "page": page})
        results: list[Booking] = []
        for day in resp.json().get("data", []):
            for occ in day.get("occurrences", []):
                results.append(Booking.model_validate(occ))
        return results

    def book_class(self, organization_id: str, occurrence_id: str) -> dict | None:
        """Book a class occurrence.

        Args:
            organization_id: Organization identifier for the class.
            occurrence_id: Occurrence identifier for the class.

        Returns:
            Raw response payload from Huppa as a dictionary when present,
            otherwise ``None``.

        Raises:
            HuppaAuthError: If the request is unauthorized.
            HuppaAPIError: If the request fails or the API returns an error.
        """
        url = f"{BASE_URL}/organizations/{organization_id}/occurrences/{occurrence_id}/booking"
        resp = self._request("POST", url)
        return self._json_or_none(resp)

    def cancel_booking(self, organization_id: str, occurrence_id: str) -> dict | None:
        """Cancel an existing class booking.

        Args:
            organization_id: Organization identifier for the class.
            occurrence_id: Occurrence identifier for the class.

        Returns:
            Raw response payload from Huppa as a dictionary when present,
            otherwise ``None``.

        Raises:
            HuppaAuthError: If the request is unauthorized.
            HuppaAPIError: If the request fails or the API returns an error.
        """
        url = f"{BASE_URL}/organizations/{organization_id}/occurrences/{occurrence_id}/booking"
        resp = self._request("DELETE", url)
        return self._json_or_none(resp)

    def join_waitlist(self, organization_id: str, occurrence_id: str) -> dict | None:
        """Join the waitlist for a class occurrence.

        Args:
            organization_id: Organization identifier for the class.
            occurrence_id: Occurrence identifier for the class.

        Returns:
            Raw response payload from Huppa as a dictionary when present,
            otherwise ``None``.

        Raises:
            HuppaAuthError: If the request is unauthorized.
            HuppaAPIError: If the request fails or the API returns an error.
        """
        url = f"{BASE_URL}/organizations/{organization_id}/occurrences/{occurrence_id}/waitlist"
        resp = self._request("POST", url)
        return self._json_or_none(resp)

    def leave_waitlist(self, organization_id: str, occurrence_id: str) -> dict | None:
        """Leave the waitlist for a class occurrence.

        Args:
            organization_id: Organization identifier for the class.
            occurrence_id: Occurrence identifier for the class.

        Returns:
            Raw response payload from Huppa as a dictionary when present,
            otherwise ``None``.

        Raises:
            HuppaAuthError: If the request is unauthorized.
            HuppaAPIError: If the request fails or the API returns an error.
        """
        url = f"{BASE_URL}/organizations/{organization_id}/occurrences/{occurrence_id}/waitlist"
        resp = self._request("DELETE", url)
        return self._json_or_none(resp)

    def get_memberships(self) -> list[Membership]:
        """Return the user's memberships and booking products.

        Returns:
            A list of parsed :class:`Membership` objects.

        Raises:
            HuppaAuthError: If the request is unauthorized.
            HuppaAPIError: If the request fails or the API returns an error.
        """
        url = f"{BASE_URL}/users/me/booking-products"
        resp = self._request("GET", url)
        return [Membership.model_validate(m) for m in resp.json().get("data", [])]
