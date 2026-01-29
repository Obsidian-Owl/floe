"""Unit tests for LineageBackendPlugin ABC in floe-core.

These tests verify LineageBackendPlugin ABC instantiation and behavior at the
package level. Package-specific tests focus on internal implementation
details that don't affect external consumers.

Requirements Covered:
- FR-019: LineageBackendPlugin ABC with get_transport_config() method
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core import HealthState, HealthStatus
from floe_core.plugins.lineage import LineageBackendPlugin


class TestLineageBackendPluginABCInstantiation:
    """Unit tests for LineageBackendPlugin ABC instantiation."""

    @pytest.mark.requirement("FR-019")
    def test_cannot_instantiate_lineage_backend_plugin_directly(self) -> None:
        """Verify LineageBackendPlugin cannot be instantiated directly.

        The ABC enforces that concrete implementations must be created.
        """
        with pytest.raises(TypeError, match="abstract"):
            LineageBackendPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-019")
    def test_mock_lineage_backend_plugin_instantiation(self) -> None:
        """Verify a complete mock implementation can be instantiated."""

        class MockLineageBackendPlugin(LineageBackendPlugin):
            """Complete mock implementation for testing."""

            @property
            def name(self) -> str:
                return "mock-lineage"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_transport_config(self) -> dict[str, Any]:
                return {
                    "type": "http",
                    "url": "http://localhost:5000/api/v1/lineage",
                    "timeout": 5.0,
                }

            def get_namespace_strategy(self) -> dict[str, Any]:
                return {
                    "strategy": "environment_based",
                    "template": "floe-{environment}",
                }

            def get_helm_values(self) -> dict[str, Any]:
                return {"marquez": {"enabled": True}}

            def validate_connection(self) -> bool:
                return True

        plugin = MockLineageBackendPlugin()

        assert plugin.name == "mock-lineage"
        assert plugin.version == "1.0.0"
        assert plugin.floe_api_version == "1.0"


class TestLineageBackendPluginDefaultImplementations:
    """Unit tests for LineageBackendPlugin default method implementations."""

    @pytest.mark.requirement("FR-019")
    def test_health_check_inherits_default_healthy(self) -> None:
        """Verify health_check() inherits default HEALTHY from PluginMetadata.

        LineageBackendPlugin does not override health_check(), so it inherits
        the default implementation from PluginMetadata which returns HEALTHY.
        Concrete implementations should override with real health checks.
        """

        class MinimalLineageBackendPlugin(LineageBackendPlugin):
            """Plugin with only required methods to test defaults."""

            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_transport_config(self) -> dict[str, Any]:
                return {"type": "http", "url": "http://localhost/lineage"}

            def get_namespace_strategy(self) -> dict[str, Any]:
                return {"strategy": "static", "namespace": "default"}

            def get_helm_values(self) -> dict[str, Any]:
                return {}

            def validate_connection(self) -> bool:
                return False

        plugin = MinimalLineageBackendPlugin()
        health = plugin.health_check()

        assert isinstance(health, HealthStatus)
        assert health.state == HealthState.HEALTHY


class TestLineageBackendPluginInheritance:
    """Unit tests for LineageBackendPlugin inheritance chain."""

    @pytest.mark.requirement("FR-019")
    def test_inherits_from_plugin_metadata(self) -> None:
        """Verify LineageBackendPlugin inherits from PluginMetadata."""
        from floe_core import PluginMetadata

        assert issubclass(LineageBackendPlugin, PluginMetadata)


class TestLineageBackendPluginMethods:
    """Unit tests for LineageBackendPlugin method behaviors."""

    @pytest.mark.requirement("FR-019")
    def test_get_transport_config_returns_valid_structure(self) -> None:
        """Verify get_transport_config() returns expected structure."""

        class TransportTestPlugin(LineageBackendPlugin):
            """Plugin that returns transport config."""

            @property
            def name(self) -> str:
                return "transport-test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_transport_config(self) -> dict[str, Any]:
                return {
                    "type": "http",
                    "url": "http://marquez:5000/api/v1/lineage",
                    "timeout": 10.0,
                }

            def get_namespace_strategy(self) -> dict[str, Any]:
                return {"strategy": "static", "namespace": "floe"}

            def get_helm_values(self) -> dict[str, Any]:
                return {}

            def validate_connection(self) -> bool:
                return True

        plugin = TransportTestPlugin()
        config = plugin.get_transport_config()

        assert config["type"] == "http"
        assert "url" in config
        assert config["timeout"] == 10.0

    @pytest.mark.requirement("FR-019")
    def test_get_namespace_strategy_returns_valid_structure(self) -> None:
        """Verify get_namespace_strategy() returns expected structure."""

        class NamespaceTestPlugin(LineageBackendPlugin):
            """Plugin that returns namespace strategy."""

            @property
            def name(self) -> str:
                return "namespace-test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_transport_config(self) -> dict[str, Any]:
                return {"type": "http", "url": "http://localhost/lineage"}

            def get_namespace_strategy(self) -> dict[str, Any]:
                return {
                    "strategy": "environment_based",
                    "template": "floe-{environment}",
                    "environment_var": "FLOE_ENVIRONMENT",
                }

            def get_helm_values(self) -> dict[str, Any]:
                return {}

            def validate_connection(self) -> bool:
                return True

        plugin = NamespaceTestPlugin()
        strategy = plugin.get_namespace_strategy()

        assert strategy["strategy"] == "environment_based"
        assert "template" in strategy

    @pytest.mark.requirement("FR-019")
    def test_get_helm_values_returns_empty_for_saas(self) -> None:
        """Verify SaaS backends return empty Helm values."""

        class SaaSPlugin(LineageBackendPlugin):
            """Plugin representing a SaaS backend (no self-hosting)."""

            @property
            def name(self) -> str:
                return "atlan"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_transport_config(self) -> dict[str, Any]:
                return {"type": "http", "url": "https://api.atlan.com/lineage"}

            def get_namespace_strategy(self) -> dict[str, Any]:
                return {"strategy": "static", "namespace": "floe"}

            def get_helm_values(self) -> dict[str, Any]:
                return {}

            def validate_connection(self) -> bool:
                return True

        plugin = SaaSPlugin()
        helm_values = plugin.get_helm_values()

        assert helm_values == {}

    @pytest.mark.requirement("FR-019")
    def test_validate_connection_returns_bool(self) -> None:
        """Verify validate_connection() returns boolean."""

        class ConnectionTestPlugin(LineageBackendPlugin):
            """Plugin for testing connection validation."""

            @property
            def name(self) -> str:
                return "connection-test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_transport_config(self) -> dict[str, Any]:
                return {"type": "http", "url": "http://localhost/lineage"}

            def get_namespace_strategy(self) -> dict[str, Any]:
                return {"strategy": "static", "namespace": "floe"}

            def get_helm_values(self) -> dict[str, Any]:
                return {}

            def validate_connection(self) -> bool:
                return True

        plugin = ConnectionTestPlugin()
        result = plugin.validate_connection()

        assert isinstance(result, bool)
        assert result is True
