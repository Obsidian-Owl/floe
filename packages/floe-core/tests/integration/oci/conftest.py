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


# ============================================================================
# Authenticated Registry Fixtures (T060 - Basic Auth Testing)
# ============================================================================


class MockSecretsPlugin:
    """Mock SecretsPlugin for integration testing.

    Provides test credentials for basic auth tests without requiring
    a real secrets backend.
    """

    def __init__(self, credentials: dict[str, str]) -> None:
        """Initialize with test credentials.

        Args:
            credentials: Dict with 'username' and 'password' keys.
        """
        self._credentials = credentials

    @property
    def name(self) -> str:
        """Return plugin name."""
        return "mock-secrets"

    @property
    def version(self) -> str:
        """Return plugin version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Return floe API version."""
        return "1.0"

    def get_secret(self, key: str) -> str | None:
        """Retrieve secret by key."""
        if key.endswith("/username"):
            return self._credentials.get("username")
        if key.endswith("/password"):
            return self._credentials.get("password")
        return self._credentials.get(key)

    def set_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        """Store secret (not implemented for mock)."""
        raise NotImplementedError("Mock does not support writing secrets")

    def list_secrets(self, prefix: str = "") -> list[str]:
        """List secrets."""
        return ["test-creds/username", "test-creds/password"]

    def get_multi_key_secret(self, name: str) -> dict[str, str]:
        """Retrieve multi-key secret."""
        if name == "test-creds":
            return self._credentials
        raise KeyError(f"Secret not found: {name}")


@pytest.fixture
def auth_registry_host() -> str:
    """Get the authenticated registry host for basic auth integration tests.

    Returns localhost:30501 for Kind cluster (NodePort), or can be overridden
    via FLOE_TEST_AUTH_REGISTRY_HOST environment variable.

    Returns:
        Registry host with basic auth (e.g., "localhost:30501").
    """
    return os.environ.get("FLOE_TEST_AUTH_REGISTRY_HOST", "localhost:30501")


@pytest.fixture
def auth_registry_credentials() -> dict[str, str]:
    """Get the test credentials for the authenticated registry.

    These credentials match those configured in registry-auth.yaml htpasswd.

    Returns:
        Dict with 'username' and 'password' keys.
    """
    return {
        "username": os.environ.get("FLOE_TEST_AUTH_REGISTRY_USER", "testuser"),
        "password": os.environ.get("FLOE_TEST_AUTH_REGISTRY_PASS", "testpass123"),
    }


@pytest.fixture
def mock_secrets_plugin(auth_registry_credentials: dict[str, str]) -> MockSecretsPlugin:
    """Create a MockSecretsPlugin with test credentials.

    Args:
        auth_registry_credentials: Test credentials.

    Returns:
        MockSecretsPlugin instance.
    """
    return MockSecretsPlugin(auth_registry_credentials)


@pytest.fixture
def auth_registry_config(auth_registry_host: str) -> dict[str, Any]:
    """Create RegistryConfig dict for authenticated registry tests.

    Configures basic auth with test credentials reference.

    Args:
        auth_registry_host: Registry host from fixture.

    Returns:
        Dict suitable for RegistryConfig.model_validate().
    """
    return {
        "uri": f"oci://{auth_registry_host}/floe-auth-test",
        "auth": {
            "type": "basic",
            "credentials_ref": {
                "name": "test-creds",
            },
        },
    }


@pytest.fixture
def auth_manifest_path(
    tmp_path: Path,
    auth_registry_host: str,
) -> Path:
    """Create a temporary manifest.yaml for authenticated registry tests.

    Note: This creates a manifest with credentials reference.
    The actual credential resolution happens via the MockSecretsPlugin fixture.

    Args:
        tmp_path: pytest tmp_path fixture.
        auth_registry_host: Authenticated registry host.

    Returns:
        Path to the created manifest.yaml.
    """
    import yaml

    manifest_data = {
        "artifacts": {
            "registry": {
                "uri": f"oci://{auth_registry_host}/floe-auth-test",
                "auth": {
                    "type": "basic",
                    "credentials_ref": {
                        "name": "test-creds",
                    },
                },
            }
        }
    }
    manifest_path = tmp_path / "manifest-auth.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest_data))
    return manifest_path


@pytest.fixture
def invalid_credentials() -> dict[str, str]:
    """Get invalid credentials for negative testing.

    Returns:
        Dict with 'username' and 'password' keys that should fail auth.
    """
    return {
        "username": "wronguser",
        "password": "wrongpass",
    }


@pytest.fixture
def invalid_secrets_plugin(invalid_credentials: dict[str, str]) -> MockSecretsPlugin:
    """Create a MockSecretsPlugin with invalid credentials.

    Args:
        invalid_credentials: Invalid test credentials.

    Returns:
        MockSecretsPlugin instance with wrong credentials.
    """
    return MockSecretsPlugin(invalid_credentials)
