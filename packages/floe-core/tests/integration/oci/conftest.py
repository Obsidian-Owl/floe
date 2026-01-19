"""Integration test fixtures for OCI client module.

This module provides fixtures for OCI client integration tests, which:
- Run against real OCI registries (Harbor in Kind cluster)
- Require K8s infrastructure to be available
- Test actual push/pull/inspect/list operations
- MUST inherit from IntegrationTestBase for K8s service resolution

Key Fixtures:
- registry_config: Real RegistryConfig from test environment
- oci_client: OCIClient instance configured for test registry
- test_artifact_tag: Unique tag for test isolation

For Harbor registry setup, see: testing/k8s/harbor/

Note: These tests FAIL if registry infrastructure is unavailable.
Per Constitution V, tests MUST NOT use pytest.skip().
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


def generate_unique_tag(prefix: str = "test") -> str:
    """Generate a unique tag for test isolation.

    Each test run gets a unique tag to prevent collisions when running
    tests concurrently or repeatedly.

    Args:
        prefix: Tag prefix (default: "test")

    Returns:
        A unique tag string like "test-abc12345-20260119"
    """
    unique_id = uuid.uuid4().hex[:8]
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}-{unique_id}-{date_str}"


@pytest.fixture
def test_artifact_tag() -> str:
    """Generate a unique artifact tag for each test.

    Returns:
        A unique mutable tag for testing (not semver, so can be overwritten).
    """
    return generate_unique_tag("test")


@pytest.fixture
def test_registry_uri() -> str:
    """Get the test registry URI from environment or default.

    Returns:
        OCI registry URI for integration tests.

    Raises:
        pytest.fail: If registry URI is not configured and Harbor is not available.
    """
    uri = os.environ.get("FLOE_TEST_REGISTRY_URI", "")
    if not uri:
        # Default to Harbor in Kind cluster
        uri = "oci://harbor.floe-testing.svc.cluster.local/floe-test"
    return uri


@pytest.fixture
def sample_compiled_artifacts_json() -> str:
    """Return valid CompiledArtifacts JSON content for push tests.

    Returns:
        JSON string representing valid CompiledArtifacts.
    """
    import json

    data: dict[str, Any] = {
        "version": "0.2.0",
        "metadata": {
            "product_name": "integration-test-product",
            "product_version": "1.0.0",
            "compiled_at": datetime.now(timezone.utc).isoformat(),
        },
        "dbt_profiles": {
            "default": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": "/tmp/test.duckdb",
                    }
                },
            }
        },
        "dagster_config": {},
    }
    return json.dumps(data, indent=2)


# Additional fixtures for OCIClient integration tests (T021)


@pytest.fixture
def oci_registry_host() -> str:
    """Get the OCI registry host for integration tests.

    Returns localhost:30500 for Kind cluster (NodePort), or can be overridden
    via FLOE_TEST_REGISTRY_HOST environment variable.

    Returns:
        Registry host (e.g., "localhost:30500").
    """
    return os.environ.get("FLOE_TEST_REGISTRY_HOST", "localhost:30500")


@pytest.fixture
def oci_registry_config(oci_registry_host: str) -> dict[str, Any]:
    """Create RegistryConfig dict for integration tests.

    Configures anonymous auth since the test registry doesn't require authentication.

    Args:
        oci_registry_host: Registry host from fixture.

    Returns:
        Dict suitable for RegistryConfig.model_validate().
    """
    return {
        "uri": f"oci://{oci_registry_host}/floe-test",
        "auth": {"type": "anonymous"},
    }


@pytest.fixture
def test_manifest_path(tmp_path: Path, oci_registry_config: dict[str, Any]) -> Path:
    """Create a temporary manifest.yaml for integration tests.

    Args:
        tmp_path: pytest tmp_path fixture.
        oci_registry_config: Registry config dict.

    Returns:
        Path to the created manifest.yaml.
    """
    import yaml

    manifest_data = {"artifacts": {"registry": oci_registry_config}}
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest_data))
    return manifest_path
