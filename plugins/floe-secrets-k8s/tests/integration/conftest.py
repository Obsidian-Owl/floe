"""Pytest configuration for floe-secrets-k8s integration tests.

This module provides fixtures specific to integration tests with real K8s cluster.
Inherits fixtures from the parent conftest.py.
"""

from __future__ import annotations

import subprocess
import uuid
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


def _kubectl_available() -> bool:
    """Check if kubectl is available and configured."""
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


@pytest.fixture
def kubectl_required() -> None:
    """Skip test if kubectl is not available.

    Use this fixture in integration tests that require kubectl.
    """
    if not _kubectl_available():
        pytest.fail("kubectl not available - start Kind cluster with: make kind-up")


@pytest.fixture
def test_namespace_name() -> Generator[str, None, None]:
    """Generate a unique test namespace name.

    Yields:
        Unique namespace name for test isolation.
    """
    ns = f"floe-test-{uuid.uuid4().hex[:8]}"
    yield ns


@pytest.fixture
def test_namespace(kubectl_required: None, test_namespace_name: str) -> Generator[str, None, None]:
    """Create and cleanup a unique K8s namespace for testing.

    Creates a namespace before the test and deletes it after.

    Args:
        kubectl_required: Ensures kubectl is available.
        test_namespace_name: Unique namespace name.

    Yields:
        Name of the created namespace.
    """
    ns = test_namespace_name

    # Create namespace
    subprocess.run(
        ["kubectl", "create", "namespace", ns],
        capture_output=True,
        check=False,
    )

    yield ns

    # Cleanup namespace
    subprocess.run(
        ["kubectl", "delete", "namespace", ns, "--ignore-not-found"],
        capture_output=True,
        check=False,
    )


@pytest.fixture
def live_k8s_plugin(kubectl_required: None, test_namespace: str) -> Any:
    """Create K8sSecretsPlugin connected to real K8s API.

    For integration tests that need real K8s connectivity.

    Args:
        kubectl_required: Ensures kubectl is available.
        test_namespace: The test namespace to use.

    Yields:
        Initialized K8sSecretsPlugin.
    """
    from floe_secrets_k8s.config import K8sSecretsConfig
    from floe_secrets_k8s.plugin import K8sSecretsPlugin

    config = K8sSecretsConfig(
        namespace=test_namespace,
        labels={"managed-by": "floe-integration-test"},
    )
    plugin = K8sSecretsPlugin(config)
    plugin.startup()

    yield plugin

    plugin.shutdown()
