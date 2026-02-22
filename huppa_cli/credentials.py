import getpass

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "huppa-cli"


def _username(profile: str, field: str) -> str:
    return f"{profile}:{field}"


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
    try:
        keyring.set_password(SERVICE_NAME, _username(profile, "email"), email)
        keyring.set_password(SERVICE_NAME, _username(profile, "password"), password)
        keyring.set_password(SERVICE_NAME, _username(profile, "subdomain"), subdomain)
    except KeyringError as exc:
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
    except KeyringError as exc:
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
    try:
        for field in ("email", "password", "subdomain"):
            keyring.delete_password(SERVICE_NAME, _username(profile, field))
    except keyring.errors.PasswordDeleteError:
        pass
    except KeyringError as exc:
        raise RuntimeError(f"Failed to clear credentials from keychain: {exc}") from exc


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
