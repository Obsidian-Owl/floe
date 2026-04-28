"""Tests for demo compiled artifact validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

MODULE_PATH = Path(__file__).resolve().parents[1] / "validate-demo-compiled-artifacts.py"
spec = importlib.util.spec_from_file_location("validate_demo_compiled_artifacts", MODULE_PATH)
assert spec is not None and spec.loader is not None
validate_demo_compiled_artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_demo_compiled_artifacts)


def _write_manifest(path: Path) -> dict[str, object]:
    lineage_backend = {
        "type": "marquez",
        "version": "0.1.0",
        "config": {
            "url": "http://floe-platform-marquez:5000",
            "allow_insecure_http": True,
        },
    }
    path.write_text(
        yaml.safe_dump({"plugins": {"lineage_backend": lineage_backend}}),
        encoding="utf-8",
    )
    return lineage_backend


def _write_product(demo_dir: Path, name: str, lineage_backend: object) -> None:
    product_dir = demo_dir / name
    product_dir.mkdir()
    (product_dir / "floe.yaml").write_text("kind: DataProduct\n", encoding="utf-8")
    (product_dir / "compiled_artifacts.json").write_text(
        json.dumps({"plugins": {"lineage_backend": lineage_backend}}),
        encoding="utf-8",
    )


def test_validate_artifacts_accepts_manifest_lineage_backend_for_all_products(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    lineage_backend = _write_manifest(manifest_path)
    _write_product(demo_dir, "customer-360", lineage_backend)
    _write_product(demo_dir, "iot-telemetry", lineage_backend)

    validate_demo_compiled_artifacts.validate_artifacts(manifest_path, demo_dir)


def test_validate_artifacts_rejects_stale_null_lineage_backend(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    _write_manifest(manifest_path)
    _write_product(demo_dir, "customer-360", None)

    with pytest.raises(SystemExit, match="lineage_backend None"):
        validate_demo_compiled_artifacts.validate_artifacts(manifest_path, demo_dir)


def test_validate_artifacts_rejects_missing_compiled_artifact(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    demo_dir = tmp_path / "demo"
    product_dir = demo_dir / "customer-360"
    product_dir.mkdir(parents=True)
    (product_dir / "floe.yaml").write_text("kind: DataProduct\n", encoding="utf-8")
    _write_manifest(manifest_path)

    with pytest.raises(SystemExit, match="compiled_artifacts.json is missing"):
        validate_demo_compiled_artifacts.validate_artifacts(manifest_path, demo_dir)


def test_compile_demo_runs_artifact_validator_after_generation() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")
    compile_demo = makefile.split("compile-demo:", 1)[1].split(".PHONY: check-manifests", 1)[0]

    generation_index = compile_demo.index("--generate-definitions")
    validation_index = compile_demo.index("testing/ci/validate-demo-compiled-artifacts.py")
    assert generation_index < validation_index
