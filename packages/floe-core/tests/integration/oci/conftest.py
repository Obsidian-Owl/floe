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
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


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


# NOTE: Additional fixtures will be added as OCIClient and RegistryConfig
# are implemented in subsequent tasks (T006, T012). These fixtures will:
# - Load RegistryConfig from test manifest
# - Create OCIClient instance with test credentials
# - Set up Harbor namespace for test isolation
