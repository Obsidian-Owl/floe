"""Shared pytest fixtures for floe-core package tests.

This module provides fixtures used across all test tiers (unit, integration, contract).
For unit-specific fixtures, see unit/conftest.py.

NOTE: Do NOT add __init__.py to test directories - pytest uses importlib mode
which can cause namespace collisions with __init__.py files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def reset_registry() -> Generator[None, None, None]:
    """Reset the plugin registry before and after each test.

    Ensures test isolation by clearing any registered plugins.
    Yields control to the test, then cleans up afterward.

    Usage:
        def test_something(reset_registry: None) -> None:
            # Registry is empty at start
            ...
            # Registry will be reset after test completes
    """
    # Import here to avoid circular imports during collection
    # Will be available after T014-T015 implement the registry
    try:
        from floe_core.plugin_registry import _reset_registry

        _reset_registry()
        yield
        _reset_registry()
    except ImportError:
        # Registry not yet implemented - just yield
        yield


@pytest.fixture
def sample_plugin_name() -> str:
    """Provide a standard plugin name for tests.

    Returns:
        A consistent plugin name for test assertions.
    """
    return "test-plugin"


@pytest.fixture
def sample_plugin_version() -> str:
    """Provide a standard plugin version for tests.

    Returns:
        A valid semver version string.
    """
    return "1.0.0"


@pytest.fixture
def sample_api_version() -> str:
    """Provide a standard floe API version for tests.

    Returns:
        A valid API version string matching FLOE_PLUGIN_API_VERSION.
    """
    return "1.0.0"
