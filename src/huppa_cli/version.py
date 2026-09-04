from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
import tomllib

PACKAGE_NAME = "huppa-cli"


def get_version() -> str:
    """Return the installed package version, with a source-checkout fallback."""
    try:
        return package_version(PACKAGE_NAME)
    except PackageNotFoundError:
        pyproject = Path(__file__).parents[1] / "pyproject.toml"
        try:
            project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
        except (OSError, tomllib.TOMLDecodeError):
            return "0.0.0+unknown"
        return str(project.get("version", "0.0.0+unknown"))
