"""Contract tests for demo manifest and test/demo chart catalog alignment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_MANIFEST = REPO_ROOT / "demo" / "manifest.yaml"
VALUES_DEMO = REPO_ROOT / "charts" / "floe-platform" / "values-demo.yaml"
VALUES_TEST = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text())
    assert isinstance(parsed, dict), f"{path} did not parse to a dict"
    return parsed


def _manifest_catalog_config() -> dict[str, Any]:
    return _load_yaml(DEMO_MANIFEST)["plugins"]["catalog"]["config"]


def _manifest_storage_config() -> dict[str, Any]:
    return _load_yaml(DEMO_MANIFEST)["plugins"]["storage"]["config"]


def _assert_bootstrap_alignment(values_path: Path) -> None:
    values = _load_yaml(values_path)
    bootstrap = values["polaris"]["bootstrap"]
    auth = values["polaris"]["auth"]["bootstrapCredentials"]
    manifest_catalog = _manifest_catalog_config()
    manifest_storage = _manifest_storage_config()

    expected_bucket_uri = f"s3://{manifest_storage['bucket']}"
    assert bootstrap["catalogName"] == manifest_catalog["warehouse"], (
        f"{values_path.name} polaris.bootstrap.catalogName must match "
        f"demo/manifest.yaml plugins.catalog.config.warehouse"
    )
    assert bootstrap["defaultBaseLocation"] == expected_bucket_uri, (
        f"{values_path.name} polaris.bootstrap.defaultBaseLocation must match "
        f"demo/manifest.yaml plugins.storage.config.bucket"
    )
    assert expected_bucket_uri in bootstrap["allowedLocations"], (
        f"{values_path.name} polaris.bootstrap.allowedLocations must include "
        f"the manifest storage bucket URI"
    )
    assert auth["clientId"] == manifest_catalog["oauth2"]["client_id"], (
        f"{values_path.name} Polaris bootstrap clientId must match the demo manifest"
    )
    assert auth["clientSecret"] == manifest_catalog["oauth2"]["client_secret"], (
        f"{values_path.name} Polaris bootstrap clientSecret must match the demo manifest"
    )


def test_values_demo_aligns_with_demo_manifest_catalog_contract() -> None:
    _assert_bootstrap_alignment(VALUES_DEMO)


def test_values_test_aligns_with_demo_manifest_catalog_contract() -> None:
    _assert_bootstrap_alignment(VALUES_TEST)
