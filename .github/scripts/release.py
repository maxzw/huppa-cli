"""Calculate the next version, build it, and create a release tag without a commit."""

from __future__ import annotations

import argparse
import re
import subprocess


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, check=check, capture_output=True, text=True)
    return result.stdout.strip()


def bump(version: str, kind: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def latest_version() -> str:
    tags = run("git", "tag", "--list", "v[0-9]*").splitlines()
    versions = [tag.removeprefix("v") for tag in tags if re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag)]
    return max(versions, key=lambda value: tuple(int(part) for part in value.split(".")), default="0.0.0")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bump", choices=("patch", "minor", "major"), required=True)
    args = parser.parse_args()

    if run("git", "status", "--porcelain"):
        raise SystemExit("Working tree is not clean; commit or stash changes before creating a release.")

    next_version = bump(latest_version(), args.bump)
    tag = f"v{next_version}"
    if run("git", "tag", "--list", tag):
        raise SystemExit(f"Tag {tag} already exists.")

    subprocess.run(("git", "tag", tag), check=True)
    try:
        subprocess.run(("uv", "build"), check=True)
    except BaseException:
        subprocess.run(("git", "tag", "-d", tag), check=False)
        raise
    subprocess.run(("git", "push", "origin", tag), check=True)
    print(tag)


if __name__ == "__main__":
    main()
