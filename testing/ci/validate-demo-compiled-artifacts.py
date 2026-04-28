#!/usr/bin/env python3
"""Validate generated demo runtime artifacts against the platform manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a YAML mapping")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def _demo_product_dirs(demo_dir: Path) -> list[Path]:
    return sorted(path for path in demo_dir.iterdir() if (path / "floe.yaml").is_file())


def _has_plugin(plugins: dict[str, Any], name: str) -> bool:
    plugin = plugins.get(name)
    return isinstance(plugin, dict) and bool(plugin.get("type"))


def _validate_file_backed_duckdb_profile(
    artifact_path: Path,
    artifact: dict[str, Any],
) -> None:
    profiles = artifact.get("dbt_profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise SystemExit(
            f"{artifact_path} enables Iceberg export but does not contain dbt_profiles"
        )

    for profile_name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        target = profile.get("target")
        outputs = profile.get("outputs")
        if not isinstance(target, str) or not isinstance(outputs, dict):
            continue
        output = outputs.get(target)
        if not isinstance(output, dict) or output.get("type") != "duckdb":
            continue
        duckdb_path = output.get("path")
        if not isinstance(duckdb_path, str) or not duckdb_path or duckdb_path == ":memory:":
            raise SystemExit(
                f"{artifact_path} profile {profile_name!r} target {target!r} must use "
                "a file-backed DuckDB path when catalog+storage Iceberg export is enabled"
            )


def validate_artifacts(manifest_path: Path, demo_dir: Path) -> None:
    """Fail if generated demo artifacts do not preserve manifest plugin selections."""
    manifest = _load_yaml(manifest_path)
    plugins = manifest.get("plugins")
    if not isinstance(plugins, dict):
        raise SystemExit(f"{manifest_path} must define a plugins mapping")

    expected_lineage_backend = plugins.get("lineage_backend")
    manifest_enables_iceberg_export = _has_plugin(plugins, "catalog") and _has_plugin(
        plugins,
        "storage",
    )
    product_dirs = _demo_product_dirs(demo_dir)
    if not product_dirs:
        raise SystemExit(f"No demo product directories with floe.yaml found in {demo_dir}")

    for product_dir in product_dirs:
        artifact_path = product_dir / "compiled_artifacts.json"
        if not artifact_path.is_file():
            raise SystemExit(
                f"{artifact_path} is missing; run `make compile-demo` before building "
                "the demo image"
            )

        artifact = _load_json(artifact_path)
        artifact_plugins = artifact.get("plugins")
        if not isinstance(artifact_plugins, dict):
            raise SystemExit(f"{artifact_path} must define a plugins object")

        actual_lineage_backend = artifact_plugins.get("lineage_backend")
        if actual_lineage_backend != expected_lineage_backend:
            raise SystemExit(
                f"{artifact_path} has lineage_backend {actual_lineage_backend!r}; "
                f"expected {expected_lineage_backend!r} from {manifest_path}. "
                "Regenerate with `make compile-demo`."
            )

        artifact_enables_iceberg_export = _has_plugin(artifact_plugins, "catalog") and _has_plugin(
            artifact_plugins,
            "storage",
        )
        if manifest_enables_iceberg_export and artifact_enables_iceberg_export:
            _validate_file_backed_duckdb_profile(artifact_path, artifact)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("demo/manifest.yaml"))
    parser.add_argument("--demo-dir", type=Path, default=Path("demo"))
    args = parser.parse_args()

    validate_artifacts(args.manifest, args.demo_dir)


if __name__ == "__main__":
    main()
