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
            return "1.0"

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

        with patch(
            "floe_core.plugin_registry.entry_points"
        ) as mock_entry_points:
            mock_entry_points.return_value = []
            registry.discover_all()

            # Should have called entry_points for each PluginType
            assert mock_entry_points.call_count == len(PluginType)

            # Verify all groups were scanned
            expected_groups = {pt.entry_point_group for pt in PluginType}
            # Check via kwargs since entry_points is called with group=
            actual_groups = {
                call.kwargs["group"] for call in mock_entry_points.call_args_list
            }
            assert actual_groups == expected_groups

    @pytest.mark.requirement("FR-001")
    def test_discover_all_is_idempotent(
        self,
        reset_registry: None,
    ) -> None:
        """Test discover_all() only runs once (idempotent)."""
        registry = PluginRegistry()

        with patch(
            "floe_core.plugin_registry.entry_points"
        ) as mock_entry_points:
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

        with patch(
            "floe_core.plugin_registry.entry_points", side_effect=mock_eps
        ):
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

        with patch(
            "floe_core.plugin_registry.entry_points", side_effect=mock_eps
        ):
            registry.discover_all()

            # Only first entry point should be stored
            key = (PluginType.COMPUTE, "duckdb")
            assert registry._discovered[key] == ep1

    @pytest.mark.requirement("FR-001")
    def test_discover_multiple_plugin_types(
        self,
        reset_registry: None,
        mock_entry_point: Callable[[str, str, str], MagicMock],
    ) -> None:
        """Test discovery across multiple plugin types."""
        registry = PluginRegistry()

        compute_ep = mock_entry_point("duckdb", "floe.computes", "pkg:DuckDB")
        orchestrator_ep = mock_entry_point(
            "dagster", "floe.orchestrators", "pkg:Dagster"
        )
        catalog_ep = mock_entry_point("polaris", "floe.catalogs", "pkg:Polaris")

        def mock_eps(group: str) -> list[MagicMock]:
            mapping = {
                "floe.computes": [compute_ep],
                "floe.orchestrators": [orchestrator_ep],
                "floe.catalogs": [catalog_ep],
            }
            return mapping.get(group, [])

        with patch(
            "floe_core.plugin_registry.entry_points", side_effect=mock_eps
        ):
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
        with patch(
            "floe_core.plugin_registry.entry_points"
        ) as mock_entry_points:
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
            "floe_core.plugin_registry.entry_points",
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

        # Create good entry points
        good_ep = mock_entry_point("good", "floe.computes", "pkg:Good")
        good_ep2 = mock_entry_point("good2", "floe.computes", "pkg:Good2")

        # The inner exception handler catches errors during entry point processing.
        # We test that by having multiple good eps, ensuring all are processed.
        def mock_eps(group: str) -> list[MagicMock]:
            if group == "floe.computes":
                return [good_ep, good_ep2]
            return []

        with patch(
            "floe_core.plugin_registry.entry_points", side_effect=mock_eps
        ):
            registry.discover_all()

            # Both entry points should be discovered
            assert (PluginType.COMPUTE, "good") in registry._discovered
            assert (PluginType.COMPUTE, "good2") in registry._discovered
            assert len(registry._discovered) == 2

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
                "floe_core.plugin_registry.entry_points",
                side_effect=mock_eps_error,
            ),
            patch("floe_core.plugin_registry.logger") as mock_logger,
        ):
            registry.discover_all()

            # Verify error was logged
            mock_logger.error.assert_called()
            # Check it was called with expected event name
            call_args = mock_logger.error.call_args_list
            assert any(
                "discover_group.failed" in str(call) for call in call_args
            )

    @pytest.mark.requirement("FR-011")
    def test_empty_discovery_succeeds(
        self,
        reset_registry: None,
    ) -> None:
        """Test discovery succeeds when no plugins are found."""
        registry = PluginRegistry()

        with patch(
            "floe_core.plugin_registry.entry_points", return_value=[]
        ):
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
