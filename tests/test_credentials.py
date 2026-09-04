from unittest.mock import Mock

import keyring
import pytest

from huppa_cli import credentials


def test_save_credentials_writes_all_fields(monkeypatch):
    store = {}
    monkeypatch.setattr(credentials.keyring, "get_password", lambda service, username: store.get(username))
    monkeypatch.setattr(
        credentials.keyring,
        "set_password",
        lambda service, username, value: store.__setitem__(username, value),
    )

    credentials.save_credentials("user@example.com", "secret", "mygym", profile="work")

    assert store == {
        "work:email": "user@example.com",
        "work:password": "secret",
        "work:subdomain": "mygym",
    }


def test_save_credentials_rolls_back_partial_write(monkeypatch):
    store = {"default:email": "old@example.com", "default:password": "old-secret", "default:subdomain": "oldgym"}
    failed = False

    def set_password(service, username, value):
        nonlocal failed
        if username == "default:password" and not failed:
            failed = True
            raise keyring.errors.KeyringError("locked")
        store[username] = value

    monkeypatch.setattr(credentials.keyring, "get_password", lambda service, username: store.get(username))
    monkeypatch.setattr(credentials.keyring, "set_password", set_password)

    with pytest.raises(RuntimeError, match="Failed to save credentials"):
        credentials.save_credentials("new@example.com", "new-secret", "newgym")

    assert store == {
        "default:email": "old@example.com",
        "default:password": "old-secret",
        "default:subdomain": "oldgym",
    }


def test_save_credentials_validates_before_keyring_access(monkeypatch):
    get_password = Mock(side_effect=AssertionError("keyring should not be accessed"))
    monkeypatch.setattr(credentials.keyring, "get_password", get_password)

    with pytest.raises(RuntimeError, match="all required"):
        credentials.save_credentials("", "secret", "mygym")

    get_password.assert_not_called()


def test_clear_credentials_continues_after_backend_failure(monkeypatch):
    deleted = []

    def delete_password(service, username):
        if username == "default:email":
            raise keyring.errors.KeyringError("locked")
        deleted.append(username)

    monkeypatch.setattr(credentials.keyring, "delete_password", delete_password)

    with pytest.raises(RuntimeError, match="Failed to clear credentials"):
        credentials.clear_credentials()

    assert deleted == ["default:password", "default:subdomain"]


def test_keyring_backend_name_handles_backend_failure(monkeypatch):
    monkeypatch.setattr(credentials.keyring, "get_keyring", Mock(side_effect=RuntimeError("unavailable")))

    assert credentials.keyring_backend_name() == "unavailable (unavailable)"


def test_mask_secret_never_returns_secret():
    assert credentials.mask_secret("secret") == "********"
    assert credentials.mask_secret(None) == "<not set>"
