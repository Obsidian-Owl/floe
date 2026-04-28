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


def validate_artifacts(manifest_path: Path, demo_dir: Path) -> None:
    """Fail if generated demo artifacts do not preserve manifest plugin selections."""
    manifest = _load_yaml(manifest_path)
    plugins = manifest.get("plugins")
    if not isinstance(plugins, dict):
        raise SystemExit(f"{manifest_path} must define a plugins mapping")

    expected_lineage_backend = plugins.get("lineage_backend")
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("demo/manifest.yaml"))
    parser.add_argument("--demo-dir", type=Path, default=Path("demo"))
    args = parser.parse_args()

    validate_artifacts(args.manifest, args.demo_dir)


if __name__ == "__main__":
    main()
