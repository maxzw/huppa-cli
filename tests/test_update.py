from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from huppa_cli import update


def test_version_key_orders_releases():
    assert update.version_key("v1.0.0") > update.version_key("v0.99.99")


def test_latest_release_ignores_prereleases(monkeypatch):
    releases = [
        {"tag_name": "v1.0.0", "prerelease": False, "draft": False},
        {"tag_name": "v1.1.0rc1", "prerelease": True, "draft": False},
        {"tag_name": "v0.9.0", "prerelease": False, "draft": True},
    ]
    monkeypatch.setattr(update, "_releases", lambda: [r for r in releases if not r["prerelease"]])

    assert update.latest_release()["tag_name"] == "v1.0.0"


def test_update_check_does_not_download(monkeypatch):
    monkeypatch.setattr(update, "get_version", lambda: "1.0.0")
    monkeypatch.setattr(update, "latest_release", lambda: {"tag_name": "v1.1.0", "assets": []})
    download = Mock(side_effect=AssertionError("check must not download"))
    monkeypatch.setattr(update.requests, "get", download)
    output = []

    installed = update.update(check_only=True, output=output.append)

    assert installed is False
    assert output == ["Installed: 1.0.0", "Latest: v1.1.0", "Update available: v1.1.0"]
    download.assert_not_called()


def test_update_installs_downloaded_wheel(monkeypatch):
    monkeypatch.setattr(update, "get_version", lambda: "1.0.0")
    monkeypatch.setattr(
        update,
        "latest_release",
        lambda: {
            "tag_name": "v1.1.0",
            "assets": [
                {"name": "huppa_cli-1.1.0-py3-none-any.whl", "browser_download_url": "https://example.test/huppa.whl"}
            ],
        },
    )
    response = SimpleNamespace(content=b"wheel", raise_for_status=Mock())
    monkeypatch.setattr(update.requests, "get", Mock(return_value=response))
    monkeypatch.setattr(update, "shutil", SimpleNamespace(which=lambda name: "/usr/local/bin/uv"))
    install = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(update.subprocess, "run", install)
    monkeypatch.setattr(update, "_is_editable_install", lambda: False)
    output = []

    installed = update.update(output=output.append)

    assert installed is True
    assert output[-1] == "Updated to v1.1.0."
    install.assert_called_once()
    command = install.call_args.args[0]
    assert command[:3] == ["/usr/local/bin/uv", "tool", "install"]
    assert command[3] == "--force"
    response.raise_for_status.assert_called_once()


def test_update_rejects_editable_install(monkeypatch):
    monkeypatch.setattr(update, "get_version", lambda: "1.0.0")
    monkeypatch.setattr(update, "latest_release", lambda: {"tag_name": "v1.1.0", "assets": []})
    monkeypatch.setattr(update, "_is_editable_install", lambda: True)

    with pytest.raises(update.UpdateError, match="editable"):
        update.update()


def test_update_reports_install_failure(monkeypatch):
    monkeypatch.setattr(update, "get_version", lambda: "1.0.0")
    monkeypatch.setattr(
        update,
        "latest_release",
        lambda: {
            "tag_name": "v1.1.0",
            "assets": [{"name": "huppa.whl", "browser_download_url": "https://example.test/huppa.whl"}],
        },
    )
    response = SimpleNamespace(content=b"wheel", raise_for_status=Mock())
    monkeypatch.setattr(update.requests, "get", Mock(return_value=response))
    monkeypatch.setattr(update, "shutil", SimpleNamespace(which=lambda name: "/usr/local/bin/uv"))
    monkeypatch.setattr(update.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=2)))
    monkeypatch.setattr(update, "_is_editable_install", lambda: False)

    with pytest.raises(update.UpdateError, match="exit code 2"):
        update.update()
