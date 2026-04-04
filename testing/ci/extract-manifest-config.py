"""Extract manifest configuration as shell-evaluable exports."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


def extract_config(manifest_path: Path) -> dict[str, str]:
    """Extract config values from manifest YAML as env var name-value pairs.

    Args:
        manifest_path: Path to the manifest YAML file.

    Returns:
        Dict mapping env var name to string value.

    Raises:
        SystemExit: If the file is missing, is a directory, or required
            sections are absent.
    """
    if manifest_path.is_dir():
        raise SystemExit(f"{manifest_path} is a directory, not a file")

    if not manifest_path.exists():
        print(f"Error: manifest file not found: {manifest_path}", file=sys.stderr)
        raise SystemExit(f"manifest file not found: {manifest_path}")

    with open(manifest_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    plugins: dict[str, Any] = raw.get("plugins") or {}

    if "storage" not in plugins:
        raise SystemExit("Missing required section: plugins.storage")

    if "catalog" not in plugins:
        raise SystemExit("Missing required section: plugins.catalog")

    storage_config: dict[str, Any] = plugins["storage"]["config"]
    catalog_config: dict[str, Any] = plugins["catalog"]["config"]
    oauth2: dict[str, Any] = catalog_config["oauth2"]

    path_style = str(storage_config["path_style_access"]).lower()

    return {
        "MANIFEST_BUCKET": str(storage_config["bucket"]),
        "MANIFEST_REGION": str(storage_config["region"]),
        "MANIFEST_PATH_STYLE_ACCESS": path_style,
        "MANIFEST_WAREHOUSE": str(catalog_config["warehouse"]),
        "MANIFEST_OAUTH_CLIENT_ID": str(oauth2["client_id"]),
        "MANIFEST_OAUTH_SCOPE": str(oauth2.get("scope", "PRINCIPAL_ROLE:ALL")),
    }


def _shell_quote(value: str) -> str:
    """Return a shell-safe quoted representation of value.

    Uses standard single-quoting ('value') when the value contains no
    single quotes.  When single quotes are present, uses bash $'...'
    ANSI-C quoting with \\x27 for single quotes so that no raw '; sequence
    can appear adjacent to shell metacharacters.

    Args:
        value: The string value to quote.

    Returns:
        A shell-safe quoted string (including surrounding quotes).
    """
    if "'" not in value:
        return f"'{value}'"
    # Use bash $'...' ANSI-C quoting: escape \ and encode ' as \x27
    escaped = value.replace("\\", "\\\\").replace("'", "\\x27")
    return f"$'{escaped}'"


def format_exports(config: dict[str, str]) -> str:
    """Format config dict as shell-evaluable export lines.

    Values without single quotes use plain single-quoting ('value').
    Values containing single quotes use bash $'...' ANSI-C quoting with
    \\x27 for the single-quote character.

    Args:
        config: Dict of env var name to value.

    Returns:
        String of newline-separated export statements.
    """
    lines: list[str] = []
    for key, value in config.items():
        lines.append(f"export {key}={_shell_quote(value)}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """CLI entry point: read manifest path from sys.argv, print exports."""
    if len(sys.argv) < 2:
        print(
            f"usage: {sys.argv[0]} <manifest.yaml>\nargument: manifest path is required",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest_path = Path(sys.argv[1])
    try:
        config = extract_config(manifest_path)
    except SystemExit as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(format_exports(config), end="")  # noqa: T201  # lgtm[py/clear-text-logging-sensitive-data]


if __name__ == "__main__":
    main()
