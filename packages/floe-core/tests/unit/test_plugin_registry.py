"""Unit tests for plugin_registry module.

Tests discovery, singleton behavior, and error handling.
All tests use mocks - no external services required.

T016: Tests for discovery functionality
T017: Tests for graceful error handling
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugin_registry import (
    PluginRegistry,
    _reset_registry,
    get_registry,
)
from floe_core.plugin_types import PluginType

if TYPE_CHECKING:
    from collections.abc import Callable


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_plugin() -> PluginMetadata:
    """Create a mock plugin that properly implements PluginMetadata.

    Returns:
        A PluginMetadata instance for testing.
    """

    class TestPlugin(PluginMetadata):
        """Test plugin implementation."""

        @property
        def name(self) -> str:
            return "test-plugin"

        @property
        def version(self) -> str:
            return "1.0.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"  # Current platform API version

    return TestPlugin()


# =============================================================================
# T016: Unit tests for discovery
# =============================================================================


class TestPluginRegistryDiscovery:
    """Tests for PluginRegistry.discover_all() and _discover_group()."""

    @pytest.mark.requirement("FR-001")
    def test_discover_all_scans_all_plugin_types(
        self,
        reset_registry: None,
    ) -> None:
        """Test discover_all() scans all 11 plugin type groups."""
        registry = PluginRegistry()

        with patch("floe_core.plugins.discovery.entry_points") as mock_entry_points:
            mock_entry_points.return_value = []
            registry.discover_all()

            # Should have called entry_points for each PluginType
            assert mock_entry_points.call_count == len(PluginType)

            # Verify all groups were scanned
            expected_groups = {pt.entry_point_group for pt in PluginType}
            # Check via kwargs since entry_points is called with group=
            actual_groups = {call.kwargs["group"] for call in mock_entry_points.call_args_list}
            assert actual_groups == expected_groups

    @pytest.mark.requirement("FR-001")
    def test_discover_all_is_idempotent(
        self,
        reset_registry: None,
    ) -> None:
        """Test discover_all() only runs once (idempotent)."""
        registry = PluginRegistry()

        with patch("floe_core.plugins.discovery.entry_points") as mock_entry_points:
            mock_entry_points.return_value = []

            # First call should scan
            registry.discover_all()
            first_call_count = mock_entry_points.call_count

            # Second call should skip
            registry.discover_all()
            assert mock_entry_points.call_count == first_call_count

    @pytest.mark.requirement("FR-001")
    def test_discover_all_stores_entry_points(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test discover_all() stores discovered entry points."""
        registry = PluginRegistry()

        # Create mock entry points for compute plugins
        ep1 = mock_entry_point("duckdb", "floe.computes", "floe_duckdb:DuckDBPlugin")
        ep2 = mock_entry_point("spark", "floe.computes", "floe_spark:SparkPlugin")

        def mock_eps(group: str) -> list[MagicMock]:
            if group == "floe.computes":
                return [ep1, ep2]
            return []

        with patch("floe_core.plugins.discovery.entry_points", side_effect=mock_eps):
            registry.discover_all()

            # Verify entry points were stored
            key1 = (PluginType.COMPUTE, "duckdb")
            key2 = (PluginType.COMPUTE, "spark")
            assert key1 in registry._discovered
            assert key2 in registry._discovered
            assert registry._discovered[key1] == ep1
            assert registry._discovered[key2] == ep2

    @pytest.mark.requirement("FR-010")
    def test_discover_detects_duplicate_plugins(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test discovery logs warning for duplicate plugin names."""
        registry = PluginRegistry()

        # Create two entry points with same name
        ep1 = mock_entry_point("duckdb", "floe.computes", "pkg1:Plugin1")
        ep2 = mock_entry_point("duckdb", "floe.computes", "pkg2:Plugin2")

        def mock_eps(group: str) -> list[MagicMock]:
            if group == "floe.computes":
                return [ep1, ep2]
            return []

        with (
            patch("floe_core.plugins.discovery.entry_points", side_effect=mock_eps),
            patch("floe_core.plugins.discovery.logger") as mock_logger,
        ):
            registry.discover_all()

            # Only first entry point should be stored
            key = (PluginType.COMPUTE, "duckdb")
            assert registry._discovered[key] == ep1

            # Verify warning was logged for duplicate
            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args_list
            assert any("discover_group.duplicate" in str(call) for call in call_args), (
                "Expected warning log for duplicate plugin"
            )

    @pytest.mark.requirement("FR-001")
    def test_discover_multiple_plugin_types(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test discovery across multiple plugin types."""
        registry = PluginRegistry()

        compute_ep = mock_entry_point("duckdb", "floe.computes", "pkg:DuckDB")
        orchestrator_ep = mock_entry_point("dagster", "floe.orchestrators", "pkg:Dagster")
        catalog_ep = mock_entry_point("polaris", "floe.catalogs", "pkg:Polaris")

        def mock_eps(group: str) -> list[MagicMock]:
            mapping = {
                "floe.computes": [compute_ep],
                "floe.orchestrators": [orchestrator_ep],
                "floe.catalogs": [catalog_ep],
            }
            return mapping.get(group, [])

        with patch("floe_core.plugins.discovery.entry_points", side_effect=mock_eps):
            registry.discover_all()

            assert (PluginType.COMPUTE, "duckdb") in registry._discovered
            assert (PluginType.ORCHESTRATOR, "dagster") in registry._discovered
            assert (PluginType.CATALOG, "polaris") in registry._discovered


class TestGetRegistrySingleton:
    """Tests for get_registry() singleton function."""

    @pytest.mark.requirement("SC-001")
    def test_get_registry_returns_plugin_registry(
        self,
        reset_registry: None,
    ) -> None:
        """Test get_registry() returns a PluginRegistry instance."""
        registry = get_registry()
        assert isinstance(registry, PluginRegistry)

    @pytest.mark.requirement("SC-001")
    def test_get_registry_returns_same_instance(
        self,
        reset_registry: None,
    ) -> None:
        """Test get_registry() returns singleton (same instance)."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    @pytest.mark.requirement("SC-001")
    def test_get_registry_calls_discover_all(
        self,
        reset_registry: None,
    ) -> None:
        """Test get_registry() automatically calls discover_all()."""
        with patch("floe_core.plugins.discovery.entry_points") as mock_entry_points:
            mock_entry_points.return_value = []

            registry = get_registry()

            # discover_all was called (entry_points was invoked)
            assert mock_entry_points.call_count == len(PluginType)
            assert registry._discovered_all is True

    @pytest.mark.requirement("SC-001")
    def test_reset_registry_clears_singleton(
        self,
        reset_registry: None,
    ) -> None:
        """Test _reset_registry() clears the singleton."""
        registry1 = get_registry()
        _reset_registry()
        registry2 = get_registry()

        # Should be different instances
        assert registry1 is not registry2


# =============================================================================
# T017: Unit tests for graceful error handling
# =============================================================================


class TestPluginRegistryErrorHandling:
    """Tests for graceful error handling in discovery."""

    @pytest.mark.requirement("FR-011")
    def test_discover_continues_on_group_error(
        self,
        reset_registry: None,
    ) -> None:
        """Test discovery continues when entry_points() raises exception."""
        registry = PluginRegistry()

        call_count = 0

        def mock_eps_with_error(group: str) -> list[Any]:
            nonlocal call_count
            call_count += 1
            if group == "floe.computes":
                raise RuntimeError("Simulated entry point error")
            return []

        with patch(
            "floe_core.plugins.discovery.entry_points",
            side_effect=mock_eps_with_error,
        ):
            # Should not raise - graceful degradation
            registry.discover_all()

            # Should have continued to other groups
            assert call_count == len(PluginType)
            assert registry._discovered_all is True

    @pytest.mark.requirement("FR-011")
    def test_discover_continues_after_processing_error(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test discovery continues after an entry point processing error."""
        registry = PluginRegistry()

        # Create a bad entry point that raises when accessing its value
        # (name must work so the error handler can log it)
        bad_ep = MagicMock()
        bad_ep.name = "bad-plugin"
        # Make value property raise an exception when accessed
        type(bad_ep).value = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("Bad entry point"))
        )

        # Create a good entry point that should still be discovered
        good_ep = mock_entry_point("good", "floe.computes", "pkg:Good")

        def mock_eps(group: str) -> list[MagicMock]:
            if group == "floe.computes":
                # Bad EP first, then good EP - tests that processing continues
                return [bad_ep, good_ep]
            return []

        with patch("floe_core.plugins.discovery.entry_points", side_effect=mock_eps):
            registry.discover_all()

            # Good entry point should still be discovered despite bad one
            assert (PluginType.COMPUTE, "good") in registry._discovered
            # Bad entry point IS stored because the error happens during logging
            # (after the entry point is added to _discovered at line 174)
            # This tests graceful degradation - we continue processing

    @pytest.mark.requirement("FR-011")
    def test_discover_logs_errors(
        self,
        reset_registry: None,
    ) -> None:
        """Test discovery logs errors via structlog."""
        registry = PluginRegistry()

        def mock_eps_error(group: str) -> list[Any]:
            if group == "floe.computes":
                raise RuntimeError("Test error")
            return []

        with (
            patch(
                "floe_core.plugins.discovery.entry_points",
                side_effect=mock_eps_error,
            ),
            patch("floe_core.plugins.discovery.logger") as mock_logger,
        ):
            registry.discover_all()

            # Verify error was logged
            mock_logger.error.assert_called()
            # Check it was called with expected event name
            call_args = mock_logger.error.call_args_list
            assert any("discover_group.failed" in str(call) for call in call_args)

    @pytest.mark.requirement("FR-011")
    def test_empty_discovery_succeeds(
        self,
        reset_registry: None,
    ) -> None:
        """Test discovery succeeds when no plugins are found."""
        registry = PluginRegistry()

        with patch("floe_core.plugins.discovery.entry_points", return_value=[]):
            registry.discover_all()

            assert registry._discovered_all is True
            assert len(registry._discovered) == 0

    @pytest.mark.requirement("SC-005")
    def test_discovery_is_thread_safe(
        self,
        reset_registry: None,
    ) -> None:
        """Test get_registry() is thread-safe under concurrent access."""
        import threading

        results: list[PluginRegistry] = []
        errors: list[Exception] = []

        def get_registry_thread() -> None:
            try:
                reg = get_registry()
                results.append(reg)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = [threading.Thread(target=get_registry_thread) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0

        # All threads got the same instance
        assert len(results) == 10
        assert all(r is results[0] for r in results)


# =============================================================================
# T024: Unit tests for register/get/list
# =============================================================================


class TestPluginRegistryRegister:
    """Tests for PluginRegistry.register() method."""

    @pytest.mark.requirement("FR-002")
    def test_register_adds_plugin_to_loaded(
        self,
        reset_registry: None,
        mock_plugin: PluginMetadata,
    ) -> None:
        """Test register() adds plugin to _loaded dict."""
        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, mock_plugin)

        key = (PluginType.COMPUTE, mock_plugin.name)
        assert key in registry._loaded
        assert registry._loaded[key] is mock_plugin

    @pytest.mark.requirement("FR-002")
    def test_register_checks_version_compatibility(
        self,
        reset_registry: None,
    ) -> None:
        """Test register() checks API version compatibility."""
        from floe_core.plugin_errors import PluginIncompatibleError

        # Create incompatible plugin (major version mismatch)
        class IncompatiblePlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "incompatible"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "99.0"  # Way higher than platform version

        registry = PluginRegistry()
        plugin = IncompatiblePlugin()

        with pytest.raises(PluginIncompatibleError) as exc_info:
            registry.register(PluginType.COMPUTE, plugin)

        assert "incompatible" in str(exc_info.value)


class TestPluginRegistryGet:
    """Tests for PluginRegistry.get() method."""

    @pytest.mark.requirement("FR-009")
    def test_get_returns_registered_plugin(
        self,
        reset_registry: None,
        mock_plugin: PluginMetadata,
    ) -> None:
        """Test get() returns a previously registered plugin."""
        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, mock_plugin)

        result = registry.get(PluginType.COMPUTE, mock_plugin.name)
        assert result is mock_plugin

    @pytest.mark.requirement("FR-009")
    def test_get_lazy_loads_discovered_plugin(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test get() lazy loads from discovered entry points."""
        registry = PluginRegistry()

        # Create mock entry point that returns a plugin class
        class LazyPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "lazy"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        ep = mock_entry_point("lazy", "floe.computes", "pkg:LazyPlugin")
        ep.load.return_value = LazyPlugin

        # Manually add to discovered (simulating discover_all)
        registry._discovered[(PluginType.COMPUTE, "lazy")] = ep

        # get() should load and cache the plugin
        result = registry.get(PluginType.COMPUTE, "lazy")
        assert result.name == "lazy"
        assert (PluginType.COMPUTE, "lazy") in registry._loaded
        ep.load.assert_called_once()

    @pytest.mark.requirement("FR-011")
    def test_get_raises_not_found_error(
        self,
        reset_registry: None,
    ) -> None:
        """Test get() raises PluginNotFoundError for unknown plugin."""
        from floe_core.plugin_errors import PluginNotFoundError

        registry = PluginRegistry()

        with pytest.raises(PluginNotFoundError) as exc_info:
            registry.get(PluginType.COMPUTE, "nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.plugin_type == PluginType.COMPUTE
        assert exc_info.value.name == "nonexistent"

    @pytest.mark.requirement("SC-002")
    def test_get_caches_loaded_plugin(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test get() caches plugin and returns same instance."""
        registry = PluginRegistry()

        class CachedPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "cached"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        ep = mock_entry_point("cached", "floe.computes", "pkg:CachedPlugin")
        ep.load.return_value = CachedPlugin
        registry._discovered[(PluginType.COMPUTE, "cached")] = ep

        # First call loads
        result1 = registry.get(PluginType.COMPUTE, "cached")
        # Second call should return cached instance
        result2 = registry.get(PluginType.COMPUTE, "cached")

        assert result1 is result2
        # load() should only be called once
        ep.load.assert_called_once()


class TestPluginRegistryList:
    """Tests for PluginRegistry.list() and list_all() methods."""

    @pytest.mark.requirement("FR-002")
    def test_list_returns_plugins_of_type(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test list() returns all plugins of specified type."""
        registry = PluginRegistry()

        # Create two compute plugins
        class Plugin1(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin1"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        class Plugin2(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin2"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        ep1 = mock_entry_point("plugin1", "floe.computes", "pkg:Plugin1")
        ep1.load.return_value = Plugin1
        ep2 = mock_entry_point("plugin2", "floe.computes", "pkg:Plugin2")
        ep2.load.return_value = Plugin2

        registry._discovered[(PluginType.COMPUTE, "plugin1")] = ep1
        registry._discovered[(PluginType.COMPUTE, "plugin2")] = ep2

        result = registry.list(PluginType.COMPUTE)

        assert len(result) == 2
        names = [p.name for p in result]
        assert "plugin1" in names
        assert "plugin2" in names

    @pytest.mark.requirement("FR-002")
    def test_list_returns_empty_for_no_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test list() returns empty list when no plugins of type exist."""
        registry = PluginRegistry()

        result = registry.list(PluginType.COMPUTE)

        assert result == []

    @pytest.mark.requirement("FR-007")
    def test_list_with_limit_parameter(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test list() with limit parameter returns at most limit plugins.

        T015: Added limit parameter to plugin_registry.list() for performance.
        """
        registry = PluginRegistry()

        # Create three compute plugins
        class Plugin1(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin1"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        class Plugin2(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin2"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        class Plugin3(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin3"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        # Setup entry points (order: name, group, value)
        ep1 = mock_entry_point("plugin1", "floe.computes", "test:Plugin1")
        ep1.load.return_value = Plugin1

        ep2 = mock_entry_point("plugin2", "floe.computes", "test:Plugin2")
        ep2.load.return_value = Plugin2

        ep3 = mock_entry_point("plugin3", "floe.computes", "test:Plugin3")
        ep3.load.return_value = Plugin3

        # Directly populate _discovered to avoid discovery complexity
        registry._discovered[(PluginType.COMPUTE, "plugin1")] = ep1
        registry._discovered[(PluginType.COMPUTE, "plugin2")] = ep2
        registry._discovered[(PluginType.COMPUTE, "plugin3")] = ep3

        # No limit - should return all 3
        result_all = registry.list(PluginType.COMPUTE)
        assert len(result_all) == 3

        # Limit 1 - should return only 1
        result_one = registry.list(PluginType.COMPUTE, limit=1)
        assert len(result_one) == 1

        # Limit 2 - should return 2
        result_two = registry.list(PluginType.COMPUTE, limit=2)
        assert len(result_two) == 2

        # Limit higher than available - should return all
        result_high = registry.list(PluginType.COMPUTE, limit=100)
        assert len(result_high) == 3

    @pytest.mark.requirement("FR-002")
    def test_list_all_returns_all_plugin_names(
        self,
        reset_registry: None,
    ) -> None:
        """Test list_all() returns plugin names grouped by type."""
        registry = PluginRegistry()

        # Add some discovered plugins
        ep1 = MagicMock()
        ep2 = MagicMock()
        ep3 = MagicMock()

        registry._discovered[(PluginType.COMPUTE, "duckdb")] = ep1
        registry._discovered[(PluginType.COMPUTE, "spark")] = ep2
        registry._discovered[(PluginType.ORCHESTRATOR, "dagster")] = ep3

        result = registry.list_all()

        # Should have all plugin types as keys
        assert len(result) == len(PluginType)

        # Check specific entries
        assert "duckdb" in result[PluginType.COMPUTE]
        assert "spark" in result[PluginType.COMPUTE]
        assert "dagster" in result[PluginType.ORCHESTRATOR]

        # Other types should have empty lists
        assert result[PluginType.CATALOG] == []

    @pytest.mark.requirement("FR-002")
    def test_list_all_sorts_names(
        self,
        reset_registry: None,
    ) -> None:
        """Test list_all() returns sorted plugin names."""
        registry = PluginRegistry()

        # Add plugins in unsorted order
        registry._discovered[(PluginType.COMPUTE, "zebra")] = MagicMock()
        registry._discovered[(PluginType.COMPUTE, "alpha")] = MagicMock()
        registry._discovered[(PluginType.COMPUTE, "middle")] = MagicMock()

        result = registry.list_all()

        assert result[PluginType.COMPUTE] == ["alpha", "middle", "zebra"]


# =============================================================================
# T025: Unit tests for duplicate registration
# =============================================================================


# =============================================================================
# T031: Unit tests for incompatible plugin rejection
# =============================================================================


class TestPluginRegistryVersionCompatibility:
    """Tests for version compatibility checking in plugin registry."""

    @pytest.mark.requirement("FR-003")
    def test_register_rejects_incompatible_major_version(
        self,
        reset_registry: None,
    ) -> None:
        """Test register() rejects plugin with incompatible major version."""
        from floe_core.plugin_errors import PluginIncompatibleError
        from floe_core.version_compat import FLOE_PLUGIN_API_VERSION

        class IncompatibleMajorPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "incompatible-major"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "99.0"  # Major version mismatch

        registry = PluginRegistry()
        plugin = IncompatibleMajorPlugin()

        with pytest.raises(PluginIncompatibleError) as exc_info:
            registry.register(PluginType.COMPUTE, plugin)

        assert exc_info.value.name == "incompatible-major"
        assert exc_info.value.required_version == "99.0"
        assert exc_info.value.platform_version == FLOE_PLUGIN_API_VERSION

    @pytest.mark.requirement("FR-004")
    def test_register_rejects_incompatible_minor_version(
        self,
        reset_registry: None,
    ) -> None:
        """Test register() rejects plugin requiring newer minor version."""
        from floe_core.plugin_errors import PluginIncompatibleError

        # Plugin needs 0.99 but platform is 0.1
        class IncompatibleMinorPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "incompatible-minor"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "0.99"  # Minor too high for platform 0.1

        registry = PluginRegistry()
        plugin = IncompatibleMinorPlugin()

        with pytest.raises(PluginIncompatibleError) as exc_info:
            registry.register(PluginType.COMPUTE, plugin)

        assert "incompatible-minor" in str(exc_info.value)

    @pytest.mark.requirement("FR-004")
    def test_register_accepts_compatible_plugin(
        self,
        reset_registry: None,
    ) -> None:
        """Test register() accepts plugin with compatible version."""
        from floe_core.version_compat import FLOE_PLUGIN_API_VERSION

        class CompatiblePlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "compatible"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return FLOE_PLUGIN_API_VERSION  # Exact match

        registry = PluginRegistry()
        plugin = CompatiblePlugin()

        # Should not raise
        registry.register(PluginType.COMPUTE, plugin)

        # Plugin should be registered
        assert registry.get(PluginType.COMPUTE, "compatible") is plugin

    @pytest.mark.requirement("FR-005")
    def test_get_rejects_incompatible_lazy_loaded_plugin(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test get() rejects incompatible plugin during lazy loading."""
        from floe_core.plugin_errors import PluginIncompatibleError

        class IncompatibleLazyPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "lazy-incompatible"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "99.0"  # Major version mismatch

        registry = PluginRegistry()

        # Set up discovered entry point
        ep = mock_entry_point("lazy-incompatible", "floe.computes", "pkg:IncompatibleLazyPlugin")
        ep.load.return_value = IncompatibleLazyPlugin
        registry._discovered[(PluginType.COMPUTE, "lazy-incompatible")] = ep

        # get() should fail during lazy load
        with pytest.raises(PluginIncompatibleError) as exc_info:
            registry.get(PluginType.COMPUTE, "lazy-incompatible")

        assert exc_info.value.name == "lazy-incompatible"
        ep.load.assert_called_once()

    @pytest.mark.requirement("FR-005")
    def test_incompatible_plugin_not_cached(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test that incompatible plugins are not added to _loaded cache."""
        from floe_core.plugin_errors import PluginIncompatibleError

        class BadPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "bad-plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "99.0"

        registry = PluginRegistry()

        ep = mock_entry_point("bad-plugin", "floe.computes", "pkg:BadPlugin")
        ep.load.return_value = BadPlugin
        registry._discovered[(PluginType.COMPUTE, "bad-plugin")] = ep

        with pytest.raises(PluginIncompatibleError):
            registry.get(PluginType.COMPUTE, "bad-plugin")

        # Plugin should NOT be in _loaded
        assert (PluginType.COMPUTE, "bad-plugin") not in registry._loaded

    @pytest.mark.requirement("SC-004")
    def test_list_skips_incompatible_plugins(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test list() skips incompatible plugins gracefully."""

        class GoodPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "good-plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"  # Compatible

        class BadPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "bad-plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "99.0"  # Incompatible

        registry = PluginRegistry()

        good_ep = mock_entry_point("good-plugin", "floe.computes", "pkg:GoodPlugin")
        good_ep.load.return_value = GoodPlugin

        bad_ep = mock_entry_point("bad-plugin", "floe.computes", "pkg:BadPlugin")
        bad_ep.load.return_value = BadPlugin

        registry._discovered[(PluginType.COMPUTE, "good-plugin")] = good_ep
        registry._discovered[(PluginType.COMPUTE, "bad-plugin")] = bad_ep

        # list() should return only compatible plugins
        plugins = registry.list(PluginType.COMPUTE)

        names = [p.name for p in plugins]
        assert "good-plugin" in names
        assert "bad-plugin" not in names
        assert len(plugins) == 1

    @pytest.mark.requirement("FR-003")
    def test_plugin_incompatible_error_message(
        self,
        reset_registry: None,
    ) -> None:
        """Test PluginIncompatibleError has informative message."""
        from floe_core.plugin_errors import PluginIncompatibleError

        class TestPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "test-error-msg"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "99.0"

        registry = PluginRegistry()

        with pytest.raises(PluginIncompatibleError) as exc_info:
            registry.register(PluginType.COMPUTE, TestPlugin())

        error_msg = str(exc_info.value)
        assert "test-error-msg" in error_msg
        assert "99.0" in error_msg
        assert "1.0" in error_msg  # Platform version


class TestPluginRegistryDuplicateHandling:
    """Tests for duplicate plugin registration handling."""

    @pytest.mark.requirement("FR-010")
    def test_register_raises_on_duplicate(
        self,
        reset_registry: None,
        mock_plugin: PluginMetadata,
    ) -> None:
        """Test register() raises DuplicatePluginError for duplicate registration."""
        from floe_core.plugin_errors import DuplicatePluginError

        registry = PluginRegistry()

        # First registration succeeds
        registry.register(PluginType.COMPUTE, mock_plugin)

        # Second registration should fail
        with pytest.raises(DuplicatePluginError) as exc_info:
            registry.register(PluginType.COMPUTE, mock_plugin)

        assert exc_info.value.plugin_type == PluginType.COMPUTE
        assert exc_info.value.name == mock_plugin.name

    @pytest.mark.requirement("FR-010")
    def test_same_name_different_type_allowed(
        self,
        reset_registry: None,
    ) -> None:
        """Test plugins with same name but different types are allowed."""

        class Plugin1(PluginMetadata):
            @property
            def name(self) -> str:
                return "samename"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        class Plugin2(PluginMetadata):
            @property
            def name(self) -> str:
                return "samename"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        registry = PluginRegistry()

        # Register same name under different types
        registry.register(PluginType.COMPUTE, Plugin1())
        registry.register(PluginType.ORCHESTRATOR, Plugin2())

        # Both should be accessible
        assert registry.get(PluginType.COMPUTE, "samename").name == "samename"
        assert registry.get(PluginType.ORCHESTRATOR, "samename").name == "samename"


# =============================================================================
# T037: Unit tests for config validation
# =============================================================================


class TestPluginRegistryConfiguration:
    """Tests for PluginRegistry.configure() and get_config() methods."""

    @pytest.mark.requirement("FR-006")
    def test_configure_with_valid_config(
        self,
        reset_registry: None,
    ) -> None:
        """Test configure() validates and stores valid configuration."""
        from pydantic import BaseModel

        class TestConfig(BaseModel):
            host: str
            port: int = 5432

        class ConfigurablePlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "configurable"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return TestConfig

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, ConfigurablePlugin())

        config = registry.configure(
            PluginType.COMPUTE,
            "configurable",
            {"host": "localhost", "port": 5433},
        )

        assert config is not None
        assert config.host == "localhost"
        assert config.port == 5433

    @pytest.mark.requirement("FR-008")
    def test_configure_applies_defaults(
        self,
        reset_registry: None,
    ) -> None:
        """Test configure() applies default values from schema."""
        from pydantic import BaseModel

        class ConfigWithDefaults(BaseModel):
            host: str
            port: int = 5432
            timeout: float = 30.0

        class DefaultPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "default-plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return ConfigWithDefaults

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, DefaultPlugin())

        # Only provide required field
        config = registry.configure(
            PluginType.COMPUTE,
            "default-plugin",
            {"host": "localhost"},
        )

        assert config is not None
        assert config.host == "localhost"
        assert config.port == 5432  # Default
        assert config.timeout == pytest.approx(30.0)  # Default

    @pytest.mark.requirement("FR-006")
    def test_configure_with_no_schema(
        self,
        reset_registry: None,
        mock_plugin: PluginMetadata,
    ) -> None:
        """Test configure() returns None for plugins without config schema."""
        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, mock_plugin)

        config = registry.configure(
            PluginType.COMPUTE,
            mock_plugin.name,
            {},
        )

        assert config is None

    @pytest.mark.requirement("FR-006")
    def test_configure_stores_config(
        self,
        reset_registry: None,
    ) -> None:
        """Test configure() stores validated config for retrieval."""
        from pydantic import BaseModel

        class StoredConfig(BaseModel):
            value: str

        class StoringPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "storing"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return StoredConfig

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, StoringPlugin())

        registry.configure(PluginType.COMPUTE, "storing", {"value": "test"})

        # Should be retrievable via get_config
        retrieved = registry.get_config(PluginType.COMPUTE, "storing")
        assert retrieved is not None
        assert retrieved.value == "test"

    @pytest.mark.requirement("FR-006")
    def test_get_config_returns_none_if_not_configured(
        self,
        reset_registry: None,
        mock_plugin: PluginMetadata,
    ) -> None:
        """Test get_config() returns None for unconfigured plugins."""
        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, mock_plugin)

        config = registry.get_config(PluginType.COMPUTE, mock_plugin.name)
        assert config is None

    @pytest.mark.requirement("FR-006")
    def test_configure_raises_plugin_not_found(
        self,
        reset_registry: None,
    ) -> None:
        """Test configure() raises PluginNotFoundError for unknown plugin."""
        from floe_core.plugin_errors import PluginNotFoundError

        registry = PluginRegistry()

        with pytest.raises(PluginNotFoundError):
            registry.configure(PluginType.COMPUTE, "nonexistent", {})


# =============================================================================
# T038: Unit tests for validation error messages
# =============================================================================


class TestPluginRegistryValidationErrors:
    """Tests for validation error handling in configure()."""

    @pytest.mark.requirement("FR-007")
    def test_configure_raises_on_invalid_config(
        self,
        reset_registry: None,
    ) -> None:
        """Test configure() raises PluginConfigurationError on invalid config."""
        from pydantic import BaseModel

        from floe_core.plugin_errors import PluginConfigurationError

        class StrictConfig(BaseModel):
            required_field: str

        class StrictPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "strict"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return StrictConfig

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, StrictPlugin())

        with pytest.raises(PluginConfigurationError) as exc_info:
            registry.configure(PluginType.COMPUTE, "strict", {})

        assert exc_info.value.name == "strict"
        assert len(exc_info.value.errors) > 0

    @pytest.mark.requirement("FR-007")
    def test_validation_error_includes_field_path(
        self,
        reset_registry: None,
    ) -> None:
        """Test validation errors include field path."""
        from pydantic import BaseModel, Field

        from floe_core.plugin_errors import PluginConfigurationError

        class TypedConfig(BaseModel):
            port: int = Field(..., ge=1, le=65535)

        class TypedPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "typed"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return TypedConfig

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, TypedPlugin())

        with pytest.raises(PluginConfigurationError) as exc_info:
            registry.configure(PluginType.COMPUTE, "typed", {"port": "not-an-int"})

        errors = exc_info.value.errors
        assert any(err["field"] == "port" for err in errors)

    @pytest.mark.requirement("FR-007")
    def test_validation_error_includes_message(
        self,
        reset_registry: None,
    ) -> None:
        """Test validation errors include error message."""
        from pydantic import BaseModel, Field

        from floe_core.plugin_errors import PluginConfigurationError

        class BoundedConfig(BaseModel):
            threads: int = Field(..., ge=1, le=128)

        class BoundedPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "bounded"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return BoundedConfig

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, BoundedPlugin())

        with pytest.raises(PluginConfigurationError) as exc_info:
            registry.configure(PluginType.COMPUTE, "bounded", {"threads": 0})

        errors = exc_info.value.errors
        assert len(errors) > 0
        assert "message" in errors[0]
        assert errors[0]["message"]  # Non-empty message

    @pytest.mark.requirement("FR-007")
    def test_validation_error_nested_field_path(
        self,
        reset_registry: None,
    ) -> None:
        """Test validation errors include nested field paths (dot notation)."""
        from pydantic import BaseModel

        from floe_core.plugin_errors import PluginConfigurationError

        class ConnectionConfig(BaseModel):
            host: str
            port: int

        class NestedConfig(BaseModel):
            connection: ConnectionConfig
            timeout: float = 30.0

        class NestedPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "nested"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return NestedConfig

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, NestedPlugin())

        with pytest.raises(PluginConfigurationError) as exc_info:
            registry.configure(
                PluginType.COMPUTE,
                "nested",
                {"connection": {"host": "localhost", "port": "invalid"}},
            )

        errors = exc_info.value.errors
        # Should have nested path like "connection.port"
        assert any("connection" in err["field"] for err in errors)

    @pytest.mark.requirement("FR-007")
    def test_validation_error_multiple_fields(
        self,
        reset_registry: None,
    ) -> None:
        """Test validation errors capture all invalid fields."""
        from pydantic import BaseModel

        from floe_core.plugin_errors import PluginConfigurationError

        class MultiFieldConfig(BaseModel):
            host: str
            port: int
            timeout: float

        class MultiFieldPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "multifield"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return MultiFieldConfig

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, MultiFieldPlugin())

        with pytest.raises(PluginConfigurationError) as exc_info:
            # All fields invalid/missing
            registry.configure(PluginType.COMPUTE, "multifield", {})

        errors = exc_info.value.errors
        # Should have errors for all three required fields
        assert len(errors) >= 3
        field_names = [err["field"] for err in errors]
        assert "host" in field_names
        assert "port" in field_names
        assert "timeout" in field_names

    @pytest.mark.requirement("FR-007")
    def test_validation_error_includes_type(
        self,
        reset_registry: None,
    ) -> None:
        """Test validation errors include error type."""
        from pydantic import BaseModel

        from floe_core.plugin_errors import PluginConfigurationError

        class RequiredConfig(BaseModel):
            required: str

        class RequiredPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "required"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_config_schema(self) -> type[BaseModel]:
                return RequiredConfig

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, RequiredPlugin())

        with pytest.raises(PluginConfigurationError) as exc_info:
            registry.configure(PluginType.COMPUTE, "required", {})

        errors = exc_info.value.errors
        assert len(errors) > 0
        assert "type" in errors[0]
        assert errors[0]["type"]  # Non-empty type


# =============================================================================
# T045: Unit tests for lifecycle hooks
# =============================================================================


class TestPluginRegistryLifecycleHooks:
    """Tests for activate_plugin() and shutdown_all() methods (T045)."""

    @pytest.mark.requirement("FR-013")
    def test_activate_plugin_calls_startup_hook(
        self,
        reset_registry: None,
    ) -> None:
        """Test activate_plugin() calls plugin's startup() method."""
        startup_called = False

        class StartupPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "startup-test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                nonlocal startup_called
                startup_called = True

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, StartupPlugin())

        assert not startup_called
        registry.activate_plugin(PluginType.COMPUTE, "startup-test")
        assert startup_called

    @pytest.mark.requirement("FR-013")
    def test_activate_plugin_is_idempotent(
        self,
        reset_registry: None,
    ) -> None:
        """Test activate_plugin() skips if already activated."""
        startup_count = 0

        class CountingPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "counting"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                nonlocal startup_count
                startup_count += 1

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, CountingPlugin())

        registry.activate_plugin(PluginType.COMPUTE, "counting")
        registry.activate_plugin(PluginType.COMPUTE, "counting")
        registry.activate_plugin(PluginType.COMPUTE, "counting")

        # Should only be called once despite multiple activate calls
        assert startup_count == 1

    @pytest.mark.requirement("FR-013")
    def test_activate_plugin_raises_on_startup_failure(
        self,
        reset_registry: None,
    ) -> None:
        """Test activate_plugin() raises PluginStartupError on failure."""
        from floe_core.plugin_errors import PluginStartupError

        class FailingPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "failing"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                raise ValueError("Startup failed!")

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, FailingPlugin())

        with pytest.raises(PluginStartupError) as exc_info:
            registry.activate_plugin(PluginType.COMPUTE, "failing")

        assert exc_info.value.plugin_type == PluginType.COMPUTE
        assert exc_info.value.name == "failing"
        assert isinstance(exc_info.value.cause, ValueError)

    @pytest.mark.requirement("SC-006")
    def test_activate_plugin_raises_on_timeout(
        self,
        reset_registry: None,
    ) -> None:
        """Test activate_plugin() raises PluginStartupError on timeout."""
        import time

        from floe_core.plugin_errors import PluginStartupError

        class SlowPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "slow"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                time.sleep(2)  # Sleep longer than timeout

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, SlowPlugin())

        with pytest.raises(PluginStartupError) as exc_info:
            # Use short timeout for test
            registry.activate_plugin(PluginType.COMPUTE, "slow", timeout=0.1)

        assert exc_info.value.name == "slow"
        assert isinstance(exc_info.value.cause, TimeoutError)

    @pytest.mark.requirement("FR-013")
    def test_activate_plugin_raises_plugin_not_found(
        self,
        reset_registry: None,
    ) -> None:
        """Test activate_plugin() raises PluginNotFoundError for unknown plugin."""
        from floe_core.plugin_errors import PluginNotFoundError

        registry = PluginRegistry()

        with pytest.raises(PluginNotFoundError):
            registry.activate_plugin(PluginType.COMPUTE, "nonexistent")

    @pytest.mark.requirement("FR-013")
    def test_shutdown_all_calls_shutdown_hooks(
        self,
        reset_registry: None,
    ) -> None:
        """Test shutdown_all() calls shutdown() on all activated plugins."""
        shutdown_order: list[str] = []

        class ShutdownPlugin(PluginMetadata):
            def __init__(self, plugin_name: str) -> None:
                self._name = plugin_name

            @property
            def name(self) -> str:
                return self._name

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                pass

            def shutdown(self) -> None:
                shutdown_order.append(self._name)

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, ShutdownPlugin("plugin-a"))
        registry.register(PluginType.CATALOG, ShutdownPlugin("plugin-b"))

        # Activate in order
        registry.activate_plugin(PluginType.COMPUTE, "plugin-a")
        registry.activate_plugin(PluginType.CATALOG, "plugin-b")

        results = registry.shutdown_all()

        # Both should have been called
        assert "plugin-a" in shutdown_order
        assert "plugin-b" in shutdown_order
        # Both should succeed (no exceptions)
        assert all(v is None for v in results.values())

    @pytest.mark.requirement("FR-013")
    def test_shutdown_all_continues_on_error(
        self,
        reset_registry: None,
    ) -> None:
        """Test shutdown_all() continues after plugin shutdown fails."""

        class FailingShutdownPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "failing-shutdown"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                pass

            def shutdown(self) -> None:
                raise RuntimeError("Shutdown failed!")

        class GoodPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "good-plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                pass

            def shutdown(self) -> None:
                pass  # Success

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, FailingShutdownPlugin())
        registry.register(PluginType.CATALOG, GoodPlugin())

        registry.activate_plugin(PluginType.COMPUTE, "failing-shutdown")
        registry.activate_plugin(PluginType.CATALOG, "good-plugin")

        results = registry.shutdown_all()

        # Should have results for both plugins
        assert len(results) == 2
        # One failed, one succeeded
        failed_count = sum(1 for v in results.values() if v is not None)
        assert failed_count == 1

    @pytest.mark.requirement("FR-013")
    def test_shutdown_all_clears_activated_set(
        self,
        reset_registry: None,
    ) -> None:
        """Test shutdown_all() clears the activated plugins set."""

        class SimplePlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "simple"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                pass

            def shutdown(self) -> None:
                pass

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, SimplePlugin())
        registry.activate_plugin(PluginType.COMPUTE, "simple")

        # Verify plugin is activated
        assert (PluginType.COMPUTE, "simple") in registry._activated

        registry.shutdown_all()

        # Should be cleared
        assert len(registry._activated) == 0

    @pytest.mark.requirement("SC-006")
    def test_shutdown_all_handles_timeout(
        self,
        reset_registry: None,
    ) -> None:
        """Test shutdown_all() handles slow shutdown with timeout."""
        import time

        class SlowShutdownPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "slow-shutdown"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                pass

            def shutdown(self) -> None:
                time.sleep(2)  # Slow shutdown

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, SlowShutdownPlugin())
        registry.activate_plugin(PluginType.COMPUTE, "slow-shutdown")

        results = registry.shutdown_all(timeout=0.1)

        # Should have timeout error
        assert "COMPUTE:slow-shutdown" in results
        assert isinstance(results["COMPUTE:slow-shutdown"], TimeoutError)


# =============================================================================
# T050: Unit tests for health checks
# =============================================================================


class TestPluginRegistryHealthChecks:
    """Tests for health_check_all() method (T050)."""

    @pytest.mark.requirement("FR-014")
    def test_health_check_all_returns_healthy_for_healthy_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test health_check_all() returns HEALTHY for healthy plugins."""
        from floe_core.plugin_metadata import HealthState, HealthStatus

        class HealthyPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "healthy"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def health_check(self) -> HealthStatus:
                return HealthStatus(state=HealthState.HEALTHY)

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, HealthyPlugin())

        results = registry.health_check_all()

        assert "COMPUTE:healthy" in results
        assert results["COMPUTE:healthy"].state == HealthState.HEALTHY

    @pytest.mark.requirement("FR-014")
    def test_health_check_all_returns_degraded_status(
        self,
        reset_registry: None,
    ) -> None:
        """Test health_check_all() propagates DEGRADED status."""
        from floe_core.plugin_metadata import HealthState, HealthStatus

        class DegradedPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "degraded"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def health_check(self) -> HealthStatus:
                return HealthStatus(
                    state=HealthState.DEGRADED,
                    message="Connection pool low",
                )

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, DegradedPlugin())

        results = registry.health_check_all()

        assert results["COMPUTE:degraded"].state == HealthState.DEGRADED
        assert "Connection pool low" in results["COMPUTE:degraded"].message

    @pytest.mark.requirement("FR-014")
    def test_health_check_all_returns_unhealthy_on_exception(
        self,
        reset_registry: None,
    ) -> None:
        """Test health_check_all() returns UNHEALTHY when health_check raises."""
        from floe_core.plugin_metadata import HealthState, HealthStatus

        class FailingHealthPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "failing-health"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def health_check(self) -> HealthStatus:
                raise RuntimeError("Health check failed!")

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, FailingHealthPlugin())

        results = registry.health_check_all()

        assert results["COMPUTE:failing-health"].state == HealthState.UNHEALTHY
        assert "RuntimeError" in results["COMPUTE:failing-health"].details.get("exception_type", "")

    @pytest.mark.requirement("SC-007")
    def test_health_check_all_returns_unhealthy_on_timeout(
        self,
        reset_registry: None,
    ) -> None:
        """Test health_check_all() returns UNHEALTHY on timeout."""
        import time

        from floe_core.plugin_metadata import HealthState, HealthStatus

        class SlowHealthPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "slow-health"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def health_check(self) -> HealthStatus:
                time.sleep(2)  # Slow health check
                return HealthStatus(state=HealthState.HEALTHY)

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, SlowHealthPlugin())

        results = registry.health_check_all(timeout=0.1)

        assert results["COMPUTE:slow-health"].state == HealthState.UNHEALTHY
        assert "timed out" in results["COMPUTE:slow-health"].message

    @pytest.mark.requirement("FR-014")
    def test_health_check_all_checks_multiple_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test health_check_all() checks all loaded plugins."""
        from floe_core.plugin_metadata import HealthState, HealthStatus

        class PluginA(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-a"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def health_check(self) -> HealthStatus:
                return HealthStatus(state=HealthState.HEALTHY)

        class PluginB(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-b"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def health_check(self) -> HealthStatus:
                return HealthStatus(state=HealthState.DEGRADED)

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, PluginA())
        registry.register(PluginType.CATALOG, PluginB())

        results = registry.health_check_all()

        assert len(results) == 2
        assert "COMPUTE:plugin-a" in results
        assert "CATALOG:plugin-b" in results

    @pytest.mark.requirement("FR-014")
    def test_health_check_all_returns_empty_for_no_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test health_check_all() returns empty dict when no plugins loaded."""
        registry = PluginRegistry()

        results = registry.health_check_all()

        assert results == {}

    @pytest.mark.requirement("FR-014")
    def test_health_check_all_only_checks_loaded_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test health_check_all() only checks loaded (not discovered) plugins."""
        from floe_core.plugin_metadata import HealthState, HealthStatus

        class LoadedPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "loaded"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def health_check(self) -> HealthStatus:
                return HealthStatus(state=HealthState.HEALTHY)

        registry = PluginRegistry()
        # Register (loads immediately)
        registry.register(PluginType.COMPUTE, LoadedPlugin())
        # Add discovered but not loaded entry
        from unittest.mock import MagicMock

        mock_ep = MagicMock()
        mock_ep.name = "discovered-only"
        registry._discovered[(PluginType.CATALOG, "discovered-only")] = mock_ep

        results = registry.health_check_all()

        # Should only have the loaded plugin
        assert len(results) == 1
        assert "COMPUTE:loaded" in results
        assert "CATALOG:discovered-only" not in results


# =============================================================================
# T056: Unit tests for dependency resolution
# =============================================================================


class TestPluginRegistryDependencyResolution:
    """Tests for resolve_dependencies() and activate_all() methods (T056).

    Tests Kahn's algorithm implementation for topological sorting of
    plugins based on their declared dependencies.
    """

    @pytest.mark.requirement("FR-015")
    def test_resolve_dependencies_empty_list(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() returns empty list for empty input."""
        registry = PluginRegistry()

        result = registry.resolve_dependencies([])

        assert result == []

    @pytest.mark.requirement("FR-015")
    def test_resolve_dependencies_single_plugin_no_deps(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() handles single plugin with no dependencies."""

        class SinglePlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "single"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        registry = PluginRegistry()
        plugin = SinglePlugin()

        result = registry.resolve_dependencies([plugin])

        assert len(result) == 1
        assert result[0] is plugin

    @pytest.mark.requirement("FR-015")
    def test_resolve_dependencies_multiple_independent_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() handles multiple plugins without dependencies."""

        class PluginA(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-a"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        class PluginB(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-b"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        registry = PluginRegistry()
        plugins = [PluginA(), PluginB()]

        result = registry.resolve_dependencies(plugins)

        assert len(result) == 2
        # Both should be returned (order doesn't matter for independent plugins)
        names = [p.name for p in result]
        assert "plugin-a" in names
        assert "plugin-b" in names

    @pytest.mark.requirement("FR-015")
    def test_resolve_dependencies_simple_chain(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() handles A -> B -> C chain correctly."""

        class PluginC(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-c"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        class PluginB(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-b"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-c"]

        class PluginA(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-a"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-b"]

        registry = PluginRegistry()
        # Provide in wrong order to test sorting
        plugins = [PluginA(), PluginB(), PluginC()]

        result = registry.resolve_dependencies(plugins)

        assert len(result) == 3
        names = [p.name for p in result]
        # C must come before B, B must come before A
        assert names.index("plugin-c") < names.index("plugin-b")
        assert names.index("plugin-b") < names.index("plugin-a")

    @pytest.mark.requirement("FR-015")
    def test_resolve_dependencies_diamond_pattern(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() handles diamond dependency pattern.

        Diamond: A depends on B and C, both B and C depend on D.
        Expected order: D, then B and C (in any order), then A.
        """

        class PluginD(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-d"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        class PluginC(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-c"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-d"]

        class PluginB(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-b"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-d"]

        class PluginA(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-a"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-b", "plugin-c"]

        registry = PluginRegistry()
        plugins = [PluginA(), PluginB(), PluginC(), PluginD()]

        result = registry.resolve_dependencies(plugins)

        assert len(result) == 4
        names = [p.name for p in result]
        # D must be first
        assert names[0] == "plugin-d"
        # A must be last
        assert names[3] == "plugin-a"
        # B and C must be between D and A
        assert names.index("plugin-b") < names.index("plugin-a")
        assert names.index("plugin-c") < names.index("plugin-a")

    @pytest.mark.requirement("SC-008")
    def test_resolve_dependencies_raises_on_missing_dependency(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() raises MissingDependencyError."""
        from floe_core.plugin_errors import MissingDependencyError

        class DependentPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "dependent"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["missing-plugin"]

        registry = PluginRegistry()

        with pytest.raises(MissingDependencyError) as exc_info:
            registry.resolve_dependencies([DependentPlugin()])

        assert exc_info.value.plugin_name == "dependent"
        assert "missing-plugin" in exc_info.value.missing_dependencies

    @pytest.mark.requirement("FR-015")
    def test_activate_all_uses_dependency_order(
        self,
        reset_registry: None,
    ) -> None:
        """Test activate_all() activates plugins in dependency order."""
        activation_order: list[str] = []

        class BasePlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "base"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def startup(self) -> None:
                activation_order.append("base")

        class DependentPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "dependent"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["base"]

            def startup(self) -> None:
                activation_order.append("dependent")

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, BasePlugin())
        registry.register(PluginType.CATALOG, DependentPlugin())

        # Activate all - should use dependency order
        registry.activate_all()

        # Base should be activated before dependent
        assert activation_order.index("base") < activation_order.index("dependent")


# =============================================================================
# T057: Unit tests for circular dependency detection
# =============================================================================


class TestPluginRegistryCircularDependencyDetection:
    """Tests for circular dependency detection in resolve_dependencies() (T057).

    Tests that the Kahn's algorithm implementation properly detects and
    reports circular dependencies in the plugin dependency graph.
    """

    @pytest.mark.requirement("FR-016")
    def test_circular_dependency_self_reference(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() detects self-referencing dependency."""
        from floe_core.plugin_errors import CircularDependencyError

        class SelfRefPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "self-ref"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["self-ref"]  # Depends on itself

        registry = PluginRegistry()

        with pytest.raises(CircularDependencyError) as exc_info:
            registry.resolve_dependencies([SelfRefPlugin()])

        assert "self-ref" in exc_info.value.cycle

    @pytest.mark.requirement("FR-016")
    def test_circular_dependency_two_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() detects A -> B -> A cycle."""
        from floe_core.plugin_errors import CircularDependencyError

        class PluginA(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-a"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-b"]

        class PluginB(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-b"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-a"]

        registry = PluginRegistry()

        with pytest.raises(CircularDependencyError) as exc_info:
            registry.resolve_dependencies([PluginA(), PluginB()])

        # Cycle should contain both plugins
        cycle = exc_info.value.cycle
        assert "plugin-a" in cycle
        assert "plugin-b" in cycle

    @pytest.mark.requirement("FR-016")
    def test_circular_dependency_three_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test resolve_dependencies() detects A -> B -> C -> A cycle."""
        from floe_core.plugin_errors import CircularDependencyError

        class PluginA(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-a"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-b"]

        class PluginB(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-b"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-c"]

        class PluginC(PluginMetadata):
            @property
            def name(self) -> str:
                return "plugin-c"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["plugin-a"]

        registry = PluginRegistry()

        with pytest.raises(CircularDependencyError) as exc_info:
            registry.resolve_dependencies([PluginA(), PluginB(), PluginC()])

        # Cycle should contain all three plugins
        cycle = exc_info.value.cycle
        assert "plugin-a" in cycle
        assert "plugin-b" in cycle
        assert "plugin-c" in cycle

    @pytest.mark.requirement("FR-016")
    def test_circular_dependency_error_message_format(
        self,
        reset_registry: None,
    ) -> None:
        """Test CircularDependencyError has informative message format."""
        from floe_core.plugin_errors import CircularDependencyError

        class CycleA(PluginMetadata):
            @property
            def name(self) -> str:
                return "cycle-a"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["cycle-b"]

        class CycleB(PluginMetadata):
            @property
            def name(self) -> str:
                return "cycle-b"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["cycle-a"]

        registry = PluginRegistry()

        with pytest.raises(CircularDependencyError) as exc_info:
            registry.resolve_dependencies([CycleA(), CycleB()])

        # Error message should show the cycle with arrows
        error_msg = str(exc_info.value)
        assert "Circular dependency" in error_msg
        assert " -> " in error_msg

    @pytest.mark.requirement("FR-016")
    def test_activate_all_raises_on_circular_dependency(
        self,
        reset_registry: None,
    ) -> None:
        """Test activate_all() raises CircularDependencyError."""
        from floe_core.plugin_errors import CircularDependencyError

        class MutualA(PluginMetadata):
            @property
            def name(self) -> str:
                return "mutual-a"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["mutual-b"]

        class MutualB(PluginMetadata):
            @property
            def name(self) -> str:
                return "mutual-b"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["mutual-a"]

        registry = PluginRegistry()
        registry.register(PluginType.COMPUTE, MutualA())
        registry.register(PluginType.CATALOG, MutualB())

        with pytest.raises(CircularDependencyError):
            registry.activate_all()

    @pytest.mark.requirement("SC-008")
    def test_partial_cycle_with_independent_plugins(
        self,
        reset_registry: None,
    ) -> None:
        """Test circular detection when only some plugins form a cycle."""
        from floe_core.plugin_errors import CircularDependencyError

        class IndependentPlugin(PluginMetadata):
            @property
            def name(self) -> str:
                return "independent"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

        class CycleX(PluginMetadata):
            @property
            def name(self) -> str:
                return "cycle-x"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["cycle-y"]

        class CycleY(PluginMetadata):
            @property
            def name(self) -> str:
                return "cycle-y"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def dependencies(self) -> list[str]:
                return ["cycle-x"]

        registry = PluginRegistry()
        # Mix independent plugin with cycle
        plugins = [IndependentPlugin(), CycleX(), CycleY()]

        with pytest.raises(CircularDependencyError) as exc_info:
            registry.resolve_dependencies(plugins)

        # Cycle should only contain the cyclic plugins
        cycle = exc_info.value.cycle
        assert "cycle-x" in cycle
        assert "cycle-y" in cycle
        # Independent plugin should not be in cycle
        # (independent may or may not be in cycle list depending on implementation)
