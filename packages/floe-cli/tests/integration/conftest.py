"""Integration test configuration for floe-cli.

This module provides fixtures for integration testing with Kubernetes.
Tests require a running Kind cluster with floe resources deployed.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "requirement(id): mark test as validating a specific requirement (FR-XXX)",
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as requiring K8s cluster",
    )
