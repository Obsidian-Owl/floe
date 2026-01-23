"""Cross-package contract tests: floe-core to floe-compute-duckdb.

These tests validate that the floe-compute-duckdb plugin correctly
implements the ComputePlugin ABC contract from floe-core.

Contract tests ensure:
- DuckDBComputePlugin is a valid ComputePlugin implementation
- All ABC methods return correct types
- Configuration models are properly consumed
- Return values match expected schemas

Requirements Covered:
- FR-001: ComputePlugin ABC implementation
- FR-002: generate_dbt_profile returns valid dbt profile
- FR-003: validate_connection returns ConnectionResult
- FR-004: get_resource_requirements returns ResourceSpec
"""

from __future__ import annotations

import pytest


class TestDuckDBImplementsComputePluginContract:
    """Verify DuckDBComputePlugin correctly implements ComputePlugin ABC."""

    @pytest.mark.requirement("001-FR-001")
    def test_duckdb_is_compute_plugin_instance(self) -> None:
        """Test DuckDBComputePlugin is a ComputePlugin instance."""
        from floe_compute_duckdb import DuckDBComputePlugin
        from floe_core.plugins import ComputePlugin

        plugin = DuckDBComputePlugin()

        assert isinstance(plugin, ComputePlugin)

    @pytest.mark.requirement("001-FR-001")
    def test_duckdb_has_required_properties(self) -> None:
        """Test DuckDBComputePlugin has all required PluginMetadata properties."""
        from floe_compute_duckdb import DuckDBComputePlugin

        plugin = DuckDBComputePlugin()

        # Required PluginMetadata properties
        assert isinstance(plugin.name, str)
        assert plugin.name == "duckdb"

        assert isinstance(plugin.version, str)
        assert len(plugin.version.split(".")) == 3  # Semver

        assert isinstance(plugin.floe_api_version, str)

        assert isinstance(plugin.description, str)
        assert len(plugin.description) > 0

        # ComputePlugin-specific property
        assert isinstance(plugin.is_self_hosted, bool)
        assert plugin.is_self_hosted is True  # DuckDB runs in platform K8s

    @pytest.mark.requirement("001-FR-002")
    def test_generate_dbt_profile_returns_dict(self) -> None:
        """Test generate_dbt_profile returns valid dict with required keys."""
        from floe_compute_duckdb import DuckDBComputePlugin
        from floe_core.compute_config import ComputeConfig

        plugin = DuckDBComputePlugin()
        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={"path": ":memory:"},
        )

        profile = plugin.generate_dbt_profile(config)

        # Must return dict
        assert isinstance(profile, dict)

        # Must have required dbt-duckdb keys
        assert "type" in profile
        assert profile["type"] == "duckdb"
        assert "path" in profile
        assert "threads" in profile

    @pytest.mark.requirement("001-FR-003")
    def test_validate_connection_returns_connection_result(self) -> None:
        """Test validate_connection returns ConnectionResult model."""
        from floe_compute_duckdb import DuckDBComputePlugin
        from floe_core.compute_config import ComputeConfig, ConnectionResult, ConnectionStatus

        plugin = DuckDBComputePlugin()
        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={"path": ":memory:"},
        )

        result = plugin.validate_connection(config)

        # Must return ConnectionResult
        assert isinstance(result, ConnectionResult)

        # ConnectionResult fields must be correct types
        assert isinstance(result.status, ConnectionStatus)
        assert isinstance(result.latency_ms, float)
        assert isinstance(result.message, str)
        assert isinstance(result.warnings, list)

    @pytest.mark.requirement("001-FR-004")
    def test_get_resource_requirements_returns_resource_spec(self) -> None:
        """Test get_resource_requirements returns ResourceSpec model."""
        from floe_compute_duckdb import DuckDBComputePlugin
        from floe_core.compute_config import ResourceSpec

        plugin = DuckDBComputePlugin()

        for size in ["small", "medium", "large"]:
            spec = plugin.get_resource_requirements(size)

            # Must return ResourceSpec
            assert isinstance(spec, ResourceSpec)

            # ResourceSpec fields must be strings with K8s units
            assert isinstance(spec.cpu_request, str)
            assert isinstance(spec.cpu_limit, str)
            assert isinstance(spec.memory_request, str)
            assert isinstance(spec.memory_limit, str)

    @pytest.mark.requirement("001-FR-002")
    def test_get_required_dbt_packages_returns_list(self) -> None:
        """Test get_required_dbt_packages returns list of package specs."""
        from floe_compute_duckdb import DuckDBComputePlugin

        plugin = DuckDBComputePlugin()

        packages = plugin.get_required_dbt_packages()

        # Must return list
        assert isinstance(packages, list)
        assert len(packages) > 0

        # Each package should be a pip-installable string
        for pkg in packages:
            assert isinstance(pkg, str)
            # Should have version constraint
            assert ">=" in pkg or "==" in pkg or "~=" in pkg

        # Should include dbt-duckdb
        assert any("dbt-duckdb" in pkg for pkg in packages)

    @pytest.mark.requirement("001-FR-007")
    def test_get_catalog_attachment_sql_returns_list_or_none(self) -> None:
        """Test get_catalog_attachment_sql returns SQL list or None."""
        from floe_compute_duckdb import DuckDBComputePlugin
        from floe_core.compute_config import CatalogConfig

        plugin = DuckDBComputePlugin()
        catalog_config = CatalogConfig(
            catalog_type="rest",
            catalog_uri="http://polaris:8181/api/catalog",
            catalog_name="floe",
        )

        sql = plugin.get_catalog_attachment_sql(catalog_config)

        # Must return list or None
        assert sql is None or isinstance(sql, list)

        if sql is not None:
            # Each element should be a SQL string
            for stmt in sql:
                assert isinstance(stmt, str)
                assert len(stmt) > 0


class TestComputeConfigSerialization:
    """Test ComputeConfig serialization/deserialization roundtrip."""

    @pytest.mark.requirement("001-FR-001")
    def test_compute_config_roundtrip(self) -> None:
        """Test ComputeConfig can be serialized and deserialized."""
        from floe_core.compute_config import ComputeConfig

        original = ComputeConfig(
            plugin="duckdb",
            threads=8,
            timeout_seconds=600,
            connection={"path": "/data/floe.duckdb", "extensions": ["iceberg"]},
        )

        # Serialize to dict (JSON-compatible)
        exported = original.model_dump(mode="json")

        # Verify exported is JSON-serializable dict
        assert isinstance(exported, dict)
        assert exported["plugin"] == "duckdb"
        assert exported["threads"] == 8
        assert exported["timeout_seconds"] == 600
        assert exported["connection"]["path"] == "/data/floe.duckdb"

        # Deserialize back
        reimported = ComputeConfig.model_validate(exported)

        # Verify roundtrip
        assert reimported.plugin == original.plugin
        assert reimported.threads == original.threads
        assert reimported.timeout_seconds == original.timeout_seconds
        assert reimported.connection == original.connection

    @pytest.mark.requirement("001-FR-003")
    def test_connection_result_roundtrip(self) -> None:
        """Test ConnectionResult can be serialized and deserialized."""
        from floe_core.compute_config import ConnectionResult, ConnectionStatus

        original = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=42.5,
            message="Connected to :memory:",
            warnings=["Extension not installed"],
        )

        # Serialize to dict
        exported = original.model_dump(mode="json")

        # Verify exported is JSON-serializable
        assert isinstance(exported, dict)
        assert exported["status"] == "healthy"  # Enum serialized as string
        assert exported["latency_ms"] == 42.5

        # Deserialize back
        reimported = ConnectionResult.model_validate(exported)

        # Verify roundtrip
        assert reimported.status == original.status
        assert reimported.latency_ms == original.latency_ms
        assert reimported.message == original.message
        assert reimported.warnings == original.warnings

    @pytest.mark.requirement("001-FR-004")
    def test_resource_spec_roundtrip(self) -> None:
        """Test ResourceSpec can be serialized and deserialized."""
        from floe_core.compute_config import ResourceSpec

        original = ResourceSpec(
            cpu_request="500m",
            cpu_limit="2000m",
            memory_request="1Gi",
            memory_limit="4Gi",
        )

        # Serialize to dict
        exported = original.model_dump(mode="json")

        # Verify exported
        assert exported["cpu_request"] == "500m"
        assert exported["memory_limit"] == "4Gi"

        # Deserialize back
        reimported = ResourceSpec.model_validate(exported)

        # Verify roundtrip
        assert reimported.cpu_request == original.cpu_request
        assert reimported.cpu_limit == original.cpu_limit
        assert reimported.memory_request == original.memory_request
        assert reimported.memory_limit == original.memory_limit

    @pytest.mark.requirement("001-FR-007")
    def test_catalog_config_roundtrip(self) -> None:
        """Test CatalogConfig can be serialized and deserialized."""
        from floe_core.compute_config import CatalogConfig

        original = CatalogConfig(
            catalog_type="rest",
            catalog_uri="http://polaris:8181/api/catalog",
            catalog_name="floe",
        )

        # Serialize to dict
        exported = original.model_dump(mode="json")

        # Verify exported
        assert exported["catalog_type"] == "rest"
        assert exported["catalog_uri"] == "http://polaris:8181/api/catalog"
        assert exported["catalog_name"] == "floe"

        # Deserialize back
        reimported = CatalogConfig.model_validate(exported)

        # Verify roundtrip
        assert reimported.catalog_type == original.catalog_type
        assert reimported.catalog_uri == original.catalog_uri
        assert reimported.catalog_name == original.catalog_name
