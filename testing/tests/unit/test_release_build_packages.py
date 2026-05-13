from __future__ import annotations

from pathlib import Path

from testing.release.build_packages import artifact_counts, package_paths_from_manifest
from testing.release.manifest import load_release_manifest

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "release" / "floe-release.yaml"


def test_package_paths_from_manifest_returns_alpha_publish_set() -> None:
    paths = package_paths_from_manifest(load_release_manifest(MANIFEST))

    assert len(paths) == 15
    assert "plugins/floe-storage-aws-s3" in paths
    assert "plugins/floe-catalog-glue" in paths
    assert "plugins/floe-alert-slack" not in paths
    assert "plugins/floe-dbt-fusion" not in paths


def test_artifact_counts_counts_wheels_and_sdists(tmp_path: Path) -> None:
    (tmp_path / "floe_core-0.1.0a1-py3-none-any.whl").write_text("", encoding="utf-8")
    (tmp_path / "floe_core-0.1.0a1.tar.gz").write_text("", encoding="utf-8")
    (tmp_path / "floe_core-0.1.0a1.zip").write_text("", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "ignored-0.1.0a1-py3-none-any.whl").write_text("", encoding="utf-8")

    assert artifact_counts(tmp_path) == {"wheels": 1, "sdists": 1}
