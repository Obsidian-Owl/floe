"""Unit test fixtures for floe-core package.

This module provides fixtures specific to unit tests, which:
- Run without external services (no K8s, no databases)
- Use mocks/fakes for all dependencies
- Execute quickly (< 1s per test)

For shared fixtures across all test tiers, see ../conftest.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def mock_entry_point() -> Callable[[str, str, str], MagicMock]:
    """Factory fixture to create mock entry points.

    Returns:
        A factory function that creates mock EntryPoint objects.

    Usage:
        def test_discovery(mock_entry_point: Callable) -> None:
            ep = mock_entry_point("my-plugin", "floe.computes", "my_package:MyPlugin")
            assert ep.name == "my-plugin"
    """

    def _create_entry_point(
        name: str,
        group: str,
        value: str,
    ) -> MagicMock:
        """Create a mock entry point.

        Args:
            name: Entry point name (plugin identifier)
            group: Entry point group (e.g., "floe.computes")
            value: Entry point value (e.g., "package:ClassName")

        Returns:
            Mock EntryPoint with name, group, value, and load() method.
        """
        ep = MagicMock(spec=["name", "group", "value", "load"])
        ep.name = name
        ep.group = group
        ep.value = value
        return ep

    return _create_entry_point


@pytest.fixture
def mock_entry_points(
    mock_entry_point: Callable[[str, str, str], MagicMock],
) -> Callable[[list[tuple[str, str, str]]], list[MagicMock]]:
    """Factory fixture to create multiple mock entry points.

    Args:
        mock_entry_point: The entry point factory fixture.

    Returns:
        A factory function that creates a list of mock entry points.

    Usage:
        def test_multi_discovery(mock_entry_points: Callable) -> None:
            eps = mock_entry_points([
                ("plugin-a", "floe.computes", "a:PluginA"),
                ("plugin-b", "floe.computes", "b:PluginB"),
            ])
            assert len(eps) == 2
    """

    def _create_entry_points(
        specs: list[tuple[str, str, str]],
    ) -> list[MagicMock]:
        """Create multiple mock entry points.

        Args:
            specs: List of (name, group, value) tuples.

        Returns:
            List of mock EntryPoint objects.
        """
        return [mock_entry_point(name, group, value) for name, group, value in specs]

    return _create_entry_points


@pytest.fixture
def mock_plugin_class() -> type[Any]:
    """Create a mock plugin class for testing.

    Returns:
        A mock class that can be used as a plugin implementation.

    Usage:
        def test_register(mock_plugin_class: type) -> None:
            # mock_plugin_class has name, version, floe_api_version
            ...
    """

    class MockPlugin:
        """Mock plugin for unit testing."""

        name = "mock-plugin"
        version = "1.0.0"
        floe_api_version = "1.0.0"
        description = "A mock plugin for testing"
        dependencies: list[str] = []

        @classmethod
        def get_config_schema(cls) -> None:
            """Return None (no config)."""
            return None

    return MockPlugin
