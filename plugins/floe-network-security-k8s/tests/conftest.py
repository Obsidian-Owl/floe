"""Pytest configuration for floe-network-security-k8s tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_network_security_k8s import K8sNetworkSecurityPlugin


@pytest.fixture
def plugin() -> "K8sNetworkSecurityPlugin":
    """Create a K8sNetworkSecurityPlugin instance for testing."""
    from floe_network_security_k8s import K8sNetworkSecurityPlugin

    return K8sNetworkSecurityPlugin()
