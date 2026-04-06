"""Integration tests for the runtime loader with real demo artifacts.

Verifies that load_product_definitions() works with the real
compiled_artifacts.json and target/manifest.json from the customer-360
demo product. No K8s services required — this tests the wiring layer
between floe-core schemas and the Dagster orchestrator loader.

Requirements Covered:
- AC-1: Returns valid Definitions with expected resources and assets
- AC-2: No module-load-time connections (resources are deferred)

Test Type Rationale:
    Integration test — crosses package boundary between floe_core (schemas)
    and floe_orchestrator_dagster (loader) using real compiled artifacts.
    No mocks for artifact parsing; real file I/O.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dagster import Definitions

from floe_orchestrator_dagster.loader import load_product_definitions

# Path to the customer-360 demo project with real artifacts
DEMO_DIR = Path(__file__).resolve().parents[4] / "demo" / "customer-360"
PRODUCT_NAME = "customer-360"


@pytest.fixture
def demo_definitions() -> Definitions:
    """Load Definitions from the real customer-360 demo directory.

    Returns:
        Dagster Definitions loaded from demo/customer-360/.

    Raises:
        pytest.fail: If compiled_artifacts.json or manifest.json are missing.
    """
    artifacts_path = DEMO_DIR / "compiled_artifacts.json"
    manifest_path = DEMO_DIR / "target" / "manifest.json"
    if not artifacts_path.exists():
        pytest.fail(
            f"compiled_artifacts.json not found at {artifacts_path}. "
            "Run 'floe compile' to generate demo artifacts."
        )
    if not manifest_path.exists():
        pytest.fail(
            f"manifest.json not found at {manifest_path}. "
            "Run 'dbt parse' in the demo directory to generate manifest."
        )
    return load_product_definitions(PRODUCT_NAME, DEMO_DIR)


@pytest.mark.requirement("AC-1")
def test_returns_definitions_from_real_artifacts(
    demo_definitions: Definitions,
) -> None:
    """load_product_definitions returns Definitions from real demo artifacts."""
    assert isinstance(demo_definitions, Definitions)


@pytest.mark.requirement("AC-1")
def test_has_dbt_resource(demo_definitions: Definitions) -> None:
    """Definitions from real artifacts contains a 'dbt' resource."""
    resources = demo_definitions.resources or {}
    assert "dbt" in resources, f"'dbt' resource missing. Present keys: {list(resources.keys())}"


@pytest.mark.requirement("AC-1")
def test_has_lineage_resource(demo_definitions: Definitions) -> None:
    """Definitions from real artifacts contains a 'lineage' resource."""
    resources = demo_definitions.resources or {}
    assert "lineage" in resources, (
        f"'lineage' resource missing. Present keys: {list(resources.keys())}"
    )


@pytest.mark.requirement("AC-1")
def test_has_at_least_one_asset(demo_definitions: Definitions) -> None:
    """Definitions from real artifacts contains at least one asset."""
    assets = list(demo_definitions.assets or [])
    assert len(assets) >= 1, "Definitions must include at least one @dbt_assets asset"


@pytest.mark.requirement("AC-2")
def test_resources_are_deferred(demo_definitions: Definitions) -> None:
    """Resources loaded from real artifacts must be deferred (not eager connections).

    This verifies AC-2: no ConnectionError or TimeoutError during import,
    even if Polaris/MinIO are unreachable.
    """
    resources = demo_definitions.resources or {}
    forbidden_types = ("Catalog", "Client", "Connection", "Session")
    for key, resource in resources.items():
        assert resource is not None, f"Resource '{key}' is None"
        type_name = type(resource).__name__
        assert not any(t in type_name for t in forbidden_types), (
            f"Resource '{key}' appears to be an eagerly resolved connection "
            f"({type_name}), not a deferred ResourceDefinition"
        )


@pytest.mark.requirement("AC-2")
def test_no_exception_during_load() -> None:
    """Loading definitions must not raise ConnectionError or TimeoutError.

    The loader should complete without attempting network connections,
    even when external services are unreachable.
    """
    artifacts_path = DEMO_DIR / "compiled_artifacts.json"
    if not artifacts_path.exists():
        pytest.fail("compiled_artifacts.json not found — run 'floe compile'")

    # This should succeed without any network calls
    result = load_product_definitions(PRODUCT_NAME, DEMO_DIR)
    assert isinstance(result, Definitions)
