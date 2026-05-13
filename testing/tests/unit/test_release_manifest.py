from __future__ import annotations

from pathlib import Path

import pytest

from testing.release.manifest import (
    ReleaseManifestError,
    load_release_manifest,
    normalize_tag_to_python_version,
    validate_release_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "release" / "floe-release.yaml"

ALPHA_PUBLISH = {
    "floe-core",
    "floe-iceberg",
    "floe-orchestrator-dagster",
    "floe-catalog-polaris",
    "floe-storage-minio",
    "floe-compute-duckdb",
    "floe-dbt-core",
    "floe-ingestion-dlt",
    "floe-telemetry-jaeger",
    "floe-rbac-k8s",
    "floe-network-security-k8s",
    "floe-lineage-marquez",
    "floe-quality-gx",
    "floe-storage-aws-s3",
    "floe-catalog-glue",
}

ALPHA_EXCLUDED = {
    "floe-alert-slack",
    "floe-alert-email",
    "floe-alert-alertmanager",
    "floe-alert-webhook",
    "floe-identity-keycloak",
    "floe-secrets-infisical",
    "floe-secrets-k8s",
    "floe-semantic-cube",
    "floe-dbt-fusion",
    "floe-telemetry-console",
    "floe-quality-dbt",
}


def test_normalizes_alpha_git_tag_to_pep440() -> None:
    assert normalize_tag_to_python_version("v0.1.0-alpha.1") == "0.1.0a1"


def test_release_manifest_exists_and_matches_cutline() -> None:
    manifest = load_release_manifest(MANIFEST)

    publish_names = {pkg.name for pkg in manifest.python_packages.publish}
    excluded_names = {pkg.name for pkg in manifest.python_packages.exclude}

    assert publish_names == ALPHA_PUBLISH
    assert excluded_names == ALPHA_EXCLUDED
    assert publish_names.isdisjoint(excluded_names)


def test_release_manifest_detects_current_version_mismatch() -> None:
    manifest = load_release_manifest(MANIFEST)

    with pytest.raises(ReleaseManifestError, match="package version mismatch"):
        validate_release_manifest(manifest, repo_root=REPO_ROOT, tag="v0.1.0-alpha.1")


def test_release_manifest_rejects_secret_like_values(tmp_path: Path) -> None:
    manifest_path = tmp_path / "floe-release.yaml"
    manifest_path.write_text(
        """
release:
  train: alpha
  git_tag: v0.1.0-alpha.1
  python_version: 0.1.0a1
  helm_version: 0.1.0-alpha.1
python_packages:
  publish:
    - path: packages/floe-core
      name: floe-core
      evidence: current-main
  exclude: []
helm:
  alpha_policy: publish
  charts: []
validation:
  require_current_main_ci: true
  require_package_build_dry_run: true
  require_full_devpod_e2e: true
  require_aws_provider_live: true
  allow_accepted_historical_evidence: true
aws_secret_access_key: not-allowed
""",
        encoding="utf-8",
    )

    with pytest.raises(ReleaseManifestError, match="secret-like key"):
        load_release_manifest(manifest_path)
