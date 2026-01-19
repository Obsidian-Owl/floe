"""Integration test fixtures for floe-rbac-k8s plugin.

Integration tests require a Kind cluster for K8s-native testing.
"""

from __future__ import annotations

import pytest

# Integration tests use fixtures from parent conftest.py
# Add integration-specific fixtures here as needed
# Note: Kind cluster setup is handled by testing infrastructure


@pytest.fixture
def requires_kind_cluster() -> None:
    """Marker fixture indicating test requires Kind cluster.

    Tests using this fixture will fail if Kind cluster is not available.
    """
    # Actual cluster validation handled by testing.base_classes.IntegrationTestBase
    pass
