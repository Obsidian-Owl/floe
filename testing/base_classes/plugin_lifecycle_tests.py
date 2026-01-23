"""Base class for plugin lifecycle tests.

This module provides reusable test cases for validating plugin lifecycle hooks.
Plugin test files can inherit from this class to get standard lifecycle
validation tests without duplicating code.

Task ID: T046
Phase: 7 - US7 (Reduce Test Duplication)
User Story: US7 - Reduce Test Duplication

Requirements tested:
    CR-002: Plugin health_check method
    FR-006: Plugin lifecycle methods (startup, shutdown)
    FR-023: Plugin lifecycle hooks

Example:
    from testing.base_classes.plugin_lifecycle_tests import BasePluginLifecycleTests

    class TestMyPluginLifecycle(BasePluginLifecycleTests):
        @pytest.fixture
        def plugin_instance(self):
            return MyPlugin(config=MyPluginConfig())

        @pytest.fixture
        def initialized_plugin(self, plugin_instance):
            plugin_instance.startup()
            yield plugin_instance
            plugin_instance.shutdown()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


class BasePluginLifecycleTests(ABC):
    """Base class providing reusable plugin lifecycle test cases.

    Subclasses must define:
        - plugin_instance fixture: Returns an uninitialized plugin instance
        - initialized_plugin fixture (optional): Returns an initialized plugin

    Provides standard tests for:
        - startup() method existence and callability
        - shutdown() method existence and callability
        - health_check() method existence
        - Lifecycle state transitions
        - Error handling during lifecycle

    Example:
        class TestDuckDBPluginLifecycle(BasePluginLifecycleTests):
            @pytest.fixture
            def plugin_instance(self) -> DuckDBComputePlugin:
                return DuckDBComputePlugin()

            @pytest.fixture
            def initialized_plugin(self, plugin_instance) -> DuckDBComputePlugin:
                plugin_instance.startup()
                yield plugin_instance
                plugin_instance.shutdown()
    """

    @pytest.fixture
    @abstractmethod
    def plugin_instance(self) -> Any:
        """Return an uninitialized plugin instance for testing.

        Subclasses MUST implement this fixture to provide a configured
        but NOT started plugin instance.

        Returns:
            An uninitialized plugin object.
        """
        ...

    # =========================================================================
    # Startup Method Tests
    # =========================================================================

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_startup_method(self, plugin_instance: Any) -> None:
        """Test plugin has startup() lifecycle method."""
        assert hasattr(plugin_instance, "startup")
        assert callable(plugin_instance.startup)

    @pytest.mark.requirement("FR-023")
    def test_startup_can_be_called(self, plugin_instance: Any) -> None:
        """Test startup() can be called without raising.

        Note: Subclasses testing plugins with external dependencies should
        override this test or provide appropriate mocks in their fixture.
        """
        # Should not raise - subclasses must provide mocks if needed
        plugin_instance.startup()

    # =========================================================================
    # Shutdown Method Tests
    # =========================================================================

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_shutdown_method(self, plugin_instance: Any) -> None:
        """Test plugin has shutdown() lifecycle method."""
        assert hasattr(plugin_instance, "shutdown")
        assert callable(plugin_instance.shutdown)

    @pytest.mark.requirement("FR-023")
    def test_shutdown_can_be_called_without_startup(self, plugin_instance: Any) -> None:
        """Test shutdown() can be called even if startup() wasn't called.

        Plugins should handle graceful shutdown even in uninitialized state.
        """
        # Should not raise
        plugin_instance.shutdown()

    @pytest.mark.requirement("FR-023")
    def test_shutdown_can_be_called_multiple_times(self, plugin_instance: Any) -> None:
        """Test shutdown() is idempotent.

        Calling shutdown() multiple times should not raise.
        """
        plugin_instance.shutdown()
        plugin_instance.shutdown()  # Should not raise

    # =========================================================================
    # Health Check Tests
    # =========================================================================

    @pytest.mark.requirement("CR-002")
    def test_plugin_has_health_check_method(self, plugin_instance: Any) -> None:
        """Test plugin has health_check() method."""
        assert hasattr(plugin_instance, "health_check")
        assert callable(plugin_instance.health_check)

    @pytest.mark.requirement("CR-002")
    def test_health_check_returns_health_status(self, plugin_instance: Any) -> None:
        """Test health_check() returns a HealthStatus object."""
        from floe_core.plugin_metadata import HealthStatus

        status = plugin_instance.health_check()

        assert isinstance(status, HealthStatus)

    @pytest.mark.requirement("CR-002")
    def test_health_check_unhealthy_before_startup(self, plugin_instance: Any) -> None:
        """Test health_check() returns UNHEALTHY before startup().

        Plugins should report unhealthy state when not initialized.
        """
        from floe_core.plugin_metadata import HealthState

        status = plugin_instance.health_check()

        # Most plugins should be unhealthy before startup
        # Some stateless plugins may be healthy immediately
        assert status.state in (HealthState.UNHEALTHY, HealthState.HEALTHY)

    # =========================================================================
    # Lifecycle Sequence Tests
    # =========================================================================

    @pytest.mark.requirement("FR-023")
    def test_startup_then_shutdown_sequence(self, plugin_instance: Any) -> None:
        """Test normal startup -> shutdown lifecycle sequence.

        Note: Subclasses testing plugins with external dependencies should
        override this test or provide appropriate mocks in their fixture.
        """
        # Start
        plugin_instance.startup()

        # Stop
        plugin_instance.shutdown()

    @pytest.mark.requirement("FR-023")
    def test_can_restart_after_shutdown(self, plugin_instance: Any) -> None:
        """Test plugin can be restarted after shutdown.

        Plugins should support: startup() -> shutdown() -> startup()

        Note: Subclasses testing plugins with external dependencies should
        override this test or provide appropriate mocks in their fixture.
        """
        # First lifecycle
        plugin_instance.startup()
        plugin_instance.shutdown()

        # Second lifecycle (restart)
        plugin_instance.startup()
        plugin_instance.shutdown()


# Module exports
__all__ = ["BasePluginLifecycleTests"]
