"""Integration test: pipeline FAILS when configured Iceberg is unreachable (AC-5).

Verifies that load_product_definitions() produces Definitions whose
iceberg resource initialization raises an error when Polaris is
unreachable. The pipeline MUST NOT report success with zero data.

Test Type Rationale:
    Integration test — uses real compiled_artifacts.json from demo product
    with mocked Polaris connection to verify end-to-end failure propagation
    through the resource factory chain.

Requirements:
    AC-5: Pipeline FAILS (not succeeds) when configured Iceberg is unreachable
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dagster import Definitions, ResourceDefinition

from floe_orchestrator_dagster.loader import load_product_definitions


def _find_project_root() -> Path:
    """Walk up from this file to find the repo root via .git directory."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    msg = "Could not find project root (no .git directory found)"
    raise FileNotFoundError(msg)


# Path to the customer-360 demo project with real artifacts
DEMO_DIR = _find_project_root() / "demo" / "customer-360"
PRODUCT_NAME = "customer-360"


def _create_artifacts_with_catalog(tmp_path: Path) -> Path:
    """Create a temporary project dir with compiled_artifacts.json that has catalog configured.

    Args:
        tmp_path: Temporary directory for the project.

    Returns:
        Path to the project directory with artifacts and manifest.
    """
    # Read real artifacts to get structure, then ensure catalog is configured
    real_artifacts_path = DEMO_DIR / "compiled_artifacts.json"
    if not real_artifacts_path.exists():
        pytest.fail(
            f"compiled_artifacts.json not found at {real_artifacts_path}. "
            "Run 'floe compile' to generate demo artifacts."
        )

    artifacts_data = json.loads(real_artifacts_path.read_text())

    # Ensure catalog and storage are configured
    if "plugins" not in artifacts_data:
        artifacts_data["plugins"] = {}
    artifacts_data["plugins"]["catalog"] = {
        "type": "polaris",
        "version": "0.1.0",
        "config": {"uri": "http://unreachable-polaris:8181/api/catalog"},
    }
    artifacts_data["plugins"]["storage"] = {
        "type": "s3",
        "version": "1.0.0",
        "config": {"endpoint": "http://unreachable-minio:9000"},
    }

    # Write artifacts
    project_dir = tmp_path / "test-product"
    project_dir.mkdir()
    (project_dir / "compiled_artifacts.json").write_text(json.dumps(artifacts_data))

    # Copy manifest from demo
    manifest_path = DEMO_DIR / "target" / "manifest.json"
    if not manifest_path.exists():
        pytest.fail(
            f"manifest.json not found at {manifest_path}. Run 'dbt parse' in the demo directory."
        )
    target_dir = project_dir / "target"
    target_dir.mkdir()
    (target_dir / "manifest.json").write_text(manifest_path.read_text())

    return project_dir


@pytest.mark.requirement("AC-5")
def test_iceberg_resource_raises_when_polaris_unreachable(tmp_path: Path) -> None:
    """Pipeline FAILS when configured Iceberg is unreachable.

    Creates Definitions via load_product_definitions() with Iceberg configured
    but Polaris unreachable. The iceberg resource initialization MUST raise
    an exception — not silently return None or empty.
    """
    project_dir = _create_artifacts_with_catalog(tmp_path)

    # Load definitions — this should succeed (deferred resources)
    defs = load_product_definitions("test-product", project_dir)
    assert isinstance(defs, Definitions)

    # The iceberg resource should exist (catalog is configured)
    resources = defs.resources or {}
    assert "iceberg" in resources, (
        f"'iceberg' resource missing when catalog is configured. Keys: {list(resources.keys())}"
    )

    # Initializing the iceberg resource should FAIL because Polaris is unreachable.
    # The resource_fn calls try_create_iceberg_resources which now re-raises.
    iceberg_resource = resources["iceberg"]
    assert isinstance(iceberg_resource, ResourceDefinition)

    # Invoke the resource_fn — it should raise because the catalog plugin
    # will try to connect to unreachable Polaris
    mock_init_context = MagicMock()
    with pytest.raises(Exception, match=r"(?i)unreachable|connection|catalog|polaris|iceberg"):
        iceberg_resource.resource_fn(mock_init_context)


@pytest.mark.requirement("AC-5")
def test_definitions_load_succeeds_without_iceberg(tmp_path: Path) -> None:
    """Definitions load fine when catalog is NOT configured (no Iceberg).

    This is the counterpart to test_iceberg_resource_raises — verifying
    that loading works when Iceberg is simply not configured (graceful
    degradation, not loud failure).
    """
    real_artifacts_path = DEMO_DIR / "compiled_artifacts.json"
    if not real_artifacts_path.exists():
        pytest.fail("compiled_artifacts.json not found — run 'floe compile'")

    artifacts_data = json.loads(real_artifacts_path.read_text())

    # Ensure catalog is NOT configured
    if "plugins" in artifacts_data:
        artifacts_data["plugins"]["catalog"] = None
        artifacts_data["plugins"]["storage"] = None

    project_dir = tmp_path / "no-iceberg-product"
    project_dir.mkdir()
    (project_dir / "compiled_artifacts.json").write_text(json.dumps(artifacts_data))

    manifest_path = DEMO_DIR / "target" / "manifest.json"
    if not manifest_path.exists():
        pytest.fail("manifest.json not found — run 'dbt parse'")
    target_dir = project_dir / "target"
    target_dir.mkdir()
    (target_dir / "manifest.json").write_text(manifest_path.read_text())

    defs = load_product_definitions("no-iceberg-product", project_dir)
    assert isinstance(defs, Definitions)

    # No iceberg resource should be present
    resources = defs.resources or {}
    assert "iceberg" not in resources, (
        "iceberg resource should not exist when catalog is not configured"
    )
