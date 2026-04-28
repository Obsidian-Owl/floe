#!/usr/bin/env python3
"""Resolve workspace packages required by the demo image.

The demo image installs local workspace packages with ``pip install --no-deps``
after third-party dependencies have been exported from ``uv.lock``. This script
therefore resolves both manifest-selected plugin packages and their local
workspace dependency closure before the list is passed to Docker.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from floe_core.schemas.manifest import PlatformManifest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib


ENTRY_POINT_GROUPS = {
    "compute": "floe.computes",
    "orchestrator": "floe.orchestrators",
    "catalog": "floe.catalogs",
    "storage": "floe.storage",
    "semantic_layer": "floe.semantic_layers",
    "ingestion": "floe.ingestion",
    "secrets": "floe.secrets",  # pragma: allowlist secret
    "telemetry_backend": "floe.telemetry_backends",
    "lineage_backend": "floe.lineage_backends",
    "identity": "floe.identity",
    "dbt": "floe.dbt",
    "quality": "floe.quality",
}

PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+")


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def _normalize_package_name(name: str) -> str:
    return name.lower().replace("_", "-")


def _workspace_sources(repo_root: Path) -> dict[str, Path]:
    pyproject = _load_toml(repo_root / "pyproject.toml")
    sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})
    workspace: dict[str, Path] = {}

    for name, source in sources.items():
        if not isinstance(source, dict) or "path" not in source:
            continue
        path = repo_root / str(source["path"])
        if (path / "pyproject.toml").exists():
            workspace[_normalize_package_name(name)] = path

    return workspace


def _workspace_metadata(workspace: dict[str, Path]) -> dict[str, dict[str, Any]]:
    return {name: _load_toml(path / "pyproject.toml") for name, path in workspace.items()}


def _entry_point_index(metadata: dict[str, dict[str, Any]]) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}

    for package_name, pyproject in metadata.items():
        entry_points = pyproject.get("project", {}).get("entry-points", {})
        for group, entries in entry_points.items():
            if not isinstance(entries, dict):
                continue
            for plugin_name in entries:
                index[(str(group), str(plugin_name))] = package_name

    return index


def _local_dependencies(package_name: str, metadata: dict[str, dict[str, Any]]) -> set[str]:
    dependencies = metadata[package_name].get("project", {}).get("dependencies", [])
    local: set[str] = set()

    for dependency in dependencies:
        match = PACKAGE_NAME_RE.match(str(dependency))
        if match:
            local.add(_normalize_package_name(match.group(0)))

    return local.intersection(metadata.keys())


def _selected_plugin_name(category: str, selection: object) -> str | None:
    """Return the configured plugin name for a manifest plugin selection."""
    if category == "quality":
        plugin_name = getattr(selection, "provider", None)
    else:
        plugin_name = getattr(selection, "type", None)

    if plugin_name is None:
        return None
    return str(plugin_name)


def _selected_plugin_packages(
    manifest: PlatformManifest,
    entry_points: dict[tuple[str, str], str],
) -> set[str]:
    selected: set[str] = set()

    for category, group in ENTRY_POINT_GROUPS.items():
        selection = getattr(manifest.plugins, category, None)
        if selection is None:
            continue
        plugin_name = _selected_plugin_name(category, selection)
        if plugin_name is None:
            continue

        package_name = entry_points.get((group, plugin_name))
        if package_name is None:
            raise SystemExit(
                f"No workspace package found for manifest plugin {category}.{plugin_name} "
                f"in entry point group {group}."
            )
        selected.add(package_name)

    return selected


def resolve_demo_plugins(repo_root: Path, manifest_path: Path) -> list[str]:
    """Resolve manifest-selected demo packages plus local dependencies."""
    manifest_data = yaml.safe_load(manifest_path.read_text())
    manifest = PlatformManifest.model_validate(manifest_data)
    workspace = _workspace_sources(repo_root)
    metadata = _workspace_metadata(workspace)
    entry_points = _entry_point_index(metadata)

    selected = _selected_plugin_packages(manifest, entry_points)
    resolved = set(selected)
    pending = list(selected)

    while pending:
        package_name = pending.pop()
        for dependency_name in _local_dependencies(package_name, metadata):
            if dependency_name not in resolved:
                resolved.add(dependency_name)
                pending.append(dependency_name)

    return sorted(resolved)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("demo/manifest.yaml"),
        help="Path to the platform manifest used by the demo image.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root containing pyproject.toml.",
    )
    args = parser.parse_args()

    packages = resolve_demo_plugins(args.repo_root.resolve(), args.manifest.resolve())
    print(" ".join(packages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
