import getpass

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "huppa-cli"
KEYRING_ERRORS = (KeyringError, OSError)


def _username(profile: str, field: str) -> str:
    return f"{profile}:{field}"


def keyring_backend_name() -> str:
    """Return the configured keyring backend name without exposing credentials."""
    try:
        backend = keyring.get_keyring()
    except (*KEYRING_ERRORS, RuntimeError) as exc:
        return f"unavailable ({exc})"
    return f"{backend.__class__.__module__}.{backend.__class__.__name__}"


def mask_secret(value: str | None) -> str:
    """Return a fixed safe representation of a configured secret."""
    return "********" if value else "<not set>"


def save_credentials(email: str, password: str, subdomain: str, profile: str = "default") -> None:
    """Save Huppa credentials to the OS keychain.

    Args:
        email: Huppa account email.
        password: Huppa account password.
        subdomain: Huppa gym subdomain.
        profile: Credential profile name.

    Raises:
        RuntimeError: If keychain storage fails.
    """
    values = {"email": email, "password": password, "subdomain": subdomain}
    if not all(values.values()):
        raise RuntimeError("Email, password, and subdomain are all required")

    previous: dict[str, str | None] = {}
    attempted: list[str] = []
    try:
        for field in values:
            previous[field] = keyring.get_password(SERVICE_NAME, _username(profile, field))
        for field, value in values.items():
            attempted.append(field)
            keyring.set_password(SERVICE_NAME, _username(profile, field), value)
    except KEYRING_ERRORS as exc:
        for field in attempted:
            username = _username(profile, field)
            try:
                old_value = previous[field]
                if old_value is None:
                    keyring.delete_password(SERVICE_NAME, username)
                else:
                    keyring.set_password(SERVICE_NAME, username, old_value)
            except KEYRING_ERRORS:
                pass
        raise RuntimeError(f"Failed to save credentials to keychain: {exc}") from exc


def load_credentials(profile: str = "default") -> dict[str, str] | None:
    """Load Huppa credentials from the OS keychain.

    Args:
        profile: Credential profile name.

    Returns:
        A credential dictionary when all required values exist, otherwise ``None``.

    Raises:
        RuntimeError: If keychain retrieval fails.
    """
    try:
        email = keyring.get_password(SERVICE_NAME, _username(profile, "email"))
        password = keyring.get_password(SERVICE_NAME, _username(profile, "password"))
        subdomain = keyring.get_password(SERVICE_NAME, _username(profile, "subdomain"))
    except KEYRING_ERRORS as exc:
        raise RuntimeError(f"Failed to read credentials from keychain: {exc}") from exc

    if email and password and subdomain:
        return {"email": email, "password": password, "subdomain": subdomain}
    return None


def clear_credentials(profile: str = "default") -> None:
    """Delete stored Huppa credentials for a profile.

    Args:
        profile: Credential profile name.

    Raises:
        RuntimeError: If keychain deletion fails unexpectedly.
    """
    errors = []
    for field in ("email", "password", "subdomain"):
        try:
            keyring.delete_password(SERVICE_NAME, _username(profile, field))
        except keyring.errors.PasswordDeleteError:
            pass
        except KEYRING_ERRORS as exc:
            errors.append(exc)
    if errors:
        raise RuntimeError(f"Failed to clear credentials from keychain: {errors[0]}") from errors[0]


def prompt_for_credentials() -> dict[str, str]:
    """Prompt interactively for email, password, and subdomain.

    Returns:
        A dictionary with ``email``, ``password``, and ``subdomain``.

    Raises:
        RuntimeError: If any required value is missing.
    """
    email = input("Huppa email: ").strip()
    password = getpass.getpass("Huppa password: ").strip()
    subdomain = input("Huppa subdomain (e.g. mygym): ").strip()

    if not email or not password or not subdomain:
        raise RuntimeError("Email, password, and subdomain are all required")

    return {"email": email, "password": password, "subdomain": subdomain}
