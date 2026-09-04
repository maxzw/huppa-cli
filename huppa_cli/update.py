from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

import requests

from huppa_cli.version import get_version

REPOSITORY = "maxzw/huppa-cli"
PACKAGE_NAME = "huppa-cli"
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class UpdateError(RuntimeError):
    """Raised when a release cannot be checked or installed."""


def version_key(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise UpdateError(f"Unsupported release version: {value}")
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    return major, minor, patch


def _releases() -> list[dict]:
    try:
        response = requests.get(
            f"https://api.github.com/repos/{REPOSITORY}/releases",
            params={"per_page": 100},
            headers={"Accept": "application/vnd.github+json"},
            timeout=(5, 20),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise UpdateError(f"Could not check GitHub Releases: {exc}") from exc
    releases = response.json()
    return [release for release in releases if not release.get("draft") and not release.get("prerelease")]


def latest_release() -> dict:
    releases = _releases()
    if not releases:
        raise UpdateError("No suitable GitHub Release was found.")
    try:
        return max(releases, key=lambda release: version_key(release["tag_name"]))
    except (KeyError, UpdateError) as exc:
        raise UpdateError(f"GitHub returned an invalid release version: {exc}") from exc


def _wheel_asset(release: dict) -> dict:
    wheels = [asset for asset in release.get("assets", []) if asset.get("name", "").endswith(".whl")]
    if len(wheels) != 1:
        raise UpdateError(f"Release {release.get('tag_name', '<unknown>')} must contain exactly one wheel.")
    return wheels[0]


def _is_editable_install() -> bool:
    try:
        metadata = distribution(PACKAGE_NAME).read_text("direct_url.json")
    except (FileNotFoundError, PackageNotFoundError):
        return False
    if not metadata:
        return False
    try:
        return bool(json.loads(metadata).get("dir_info", {}).get("editable"))
    except json.JSONDecodeError:
        return False


def update(*, check_only: bool = False, force: bool = False, output=print) -> bool:
    """Check for and optionally install the newest GitHub Release.

    Returns ``True`` when an update was installed and ``False`` otherwise.
    """
    current = get_version()
    release = latest_release()
    tag = release["tag_name"]
    latest = version_key(tag)
    output(f"Installed: {current}")
    output(f"Latest: {tag}")

    try:
        current_key = version_key(current)
    except UpdateError:
        current_key = (0, 0, 0)
    if latest <= current_key and not force:
        output("Already up to date.")
        return False
    if check_only:
        output(f"Update available: {tag}")
        return False
    if _is_editable_install():
        raise UpdateError("This is an editable installation. Run 'make deploy' to update it from the checkout.")

    uv = shutil.which("uv")
    if not uv:
        raise UpdateError("uv is not on PATH; install the update manually or run 'make deploy' in a checkout.")
    asset = _wheel_asset(release)
    try:
        response = requests.get(
            asset["browser_download_url"],
            headers={"Accept": "application/octet-stream"},
            timeout=(5, 60),
        )
        response.raise_for_status()
    except (KeyError, requests.RequestException) as exc:
        raise UpdateError(f"Could not download release {tag}: {exc}") from exc

    with tempfile.TemporaryDirectory(prefix="huppa-update-") as directory:
        wheel = Path(directory) / asset["name"]
        wheel.write_bytes(response.content)
        result = subprocess.run([uv, "tool", "install", "--force", str(wheel)], check=False)
    if result.returncode:
        raise UpdateError(f"uv tool install failed with exit code {result.returncode}.")
    output(f"Updated to {tag}.")
    return True
