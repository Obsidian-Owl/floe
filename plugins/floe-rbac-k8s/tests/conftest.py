"""Shared test fixtures for floe-rbac-k8s plugin tests."""

from __future__ import annotations

import pytest

from floe_rbac_k8s import K8sRBACPlugin


@pytest.fixture
def plugin() -> K8sRBACPlugin:
    """Create a K8sRBACPlugin instance for testing."""
    return K8sRBACPlugin()
