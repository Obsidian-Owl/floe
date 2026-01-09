"""Unit tests for DuckDBComputePlugin.

These tests verify the DuckDB compute plugin implementation without
requiring external services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_compute_duckdb import DuckDBComputePlugin
    from floe_core import CatalogConfig, ComputeConfig


class TestDuckDBComputePluginMetadata:
    """Test plugin metadata properties."""

    @pytest.mark.requirement("001-FR-001")
    def test_plugin_name(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test plugin name is 'duckdb'."""
        assert duckdb_plugin.name == "duckdb"

    @pytest.mark.requirement("001-FR-001")
    def test_plugin_version(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test plugin version follows semver format."""
        version = duckdb_plugin.version
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    @pytest.mark.requirement("001-FR-001")
    def test_floe_api_version(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test floe API version is specified."""
        api_version = duckdb_plugin.floe_api_version
        assert api_version == "1.0"

    @pytest.mark.requirement("001-FR-002")
    def test_is_self_hosted(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test DuckDB is self-hosted (runs in platform K8s)."""
        assert duckdb_plugin.is_self_hosted is True

    @pytest.mark.requirement("001-FR-001")
    def test_plugin_description(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test plugin has a description."""
        assert len(duckdb_plugin.description) > 0
        assert "DuckDB" in duckdb_plugin.description


class TestGenerateDBTProfile:
    """Test dbt profile generation."""

    @pytest.mark.requirement("001-FR-003")
    def test_generate_dbt_profile_minimal(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test profile generation with minimal configuration."""
        profile = duckdb_plugin.generate_dbt_profile(memory_config)

        assert profile["type"] == "duckdb"
        assert profile["path"] == ":memory:"
        assert profile["threads"] == 4

    @pytest.mark.requirement("001-FR-003")
    def test_generate_dbt_profile_with_extensions(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation includes extensions when specified."""
        from floe_core import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=8,
            connection={
                "path": "/data/analytics.duckdb",
                "extensions": ["iceberg", "httpfs"],
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert profile["extensions"] == ["iceberg", "httpfs"]
        assert profile["threads"] == 8

    @pytest.mark.requirement("001-FR-003")
    def test_generate_dbt_profile_with_settings(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation includes DuckDB settings."""
        from floe_core import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            connection={
                "path": ":memory:",
                "settings": {"memory_limit": "4GB"},
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert profile["settings"]["memory_limit"] == "4GB"


class TestGenerateDBTProfileWithAttach:
    """Test dbt profile generation with attach blocks."""

    @pytest.mark.requirement("001-FR-009")
    def test_generate_dbt_profile_with_attach(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation includes attach blocks when configured."""
        from floe_core import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={
                "path": ":memory:",
                "attach": [
                    {
                        "path": "iceberg:polaris",
                        "alias": "iceberg_catalog",
                        "type": "iceberg",
                    }
                ],
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert "attach" in profile
        assert len(profile["attach"]) == 1
        assert profile["attach"][0]["path"] == "iceberg:polaris"
        assert profile["attach"][0]["alias"] == "iceberg_catalog"
        assert profile["attach"][0]["type"] == "iceberg"

    @pytest.mark.requirement("001-FR-009")
    def test_generate_dbt_profile_with_multiple_attach(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation with multiple attach blocks."""
        from floe_core import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={
                "path": ":memory:",
                "attach": [
                    {"path": "other_db.duckdb", "alias": "other_db"},
                    {"path": "third_db.duckdb", "alias": "third_db"},
                ],
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert len(profile["attach"]) == 2
        assert profile["attach"][0]["path"] == "other_db.duckdb"
        assert profile["attach"][1]["alias"] == "third_db"

    @pytest.mark.requirement("001-FR-009")
    def test_generate_dbt_profile_attach_with_options(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test attach block options are rendered properly."""
        from floe_core import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={
                "path": ":memory:",
                "attach": [
                    {
                        "path": "iceberg:catalog",
                        "alias": "ice",
                        "type": "iceberg",
                        "options": {"catalog_uri": "http://polaris:8181"},
                    }
                ],
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert profile["attach"][0]["catalog_uri"] == "http://polaris:8181"

    @pytest.mark.requirement("001-FR-009")
    def test_generate_dbt_profile_without_attach(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test profile generation without attach blocks."""
        profile = duckdb_plugin.generate_dbt_profile(memory_config)

        assert "attach" not in profile

    @pytest.mark.requirement("001-FR-009")
    def test_generate_dbt_profile_attach_minimal(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test attach with only required path field."""
        from floe_core import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            connection={
                "path": ":memory:",
                "attach": [{"path": "my_db.duckdb"}],
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert len(profile["attach"]) == 1
        assert profile["attach"][0]["path"] == "my_db.duckdb"
        assert "alias" not in profile["attach"][0]
        assert "type" not in profile["attach"][0]


class TestRequiredDBTPackages:
    """Test required dbt packages."""

    @pytest.mark.requirement("001-FR-004")
    def test_get_required_dbt_packages(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test required packages include dbt-duckdb."""
        packages = duckdb_plugin.get_required_dbt_packages()

        assert isinstance(packages, list)
        assert len(packages) > 0

        # Should include dbt-duckdb
        dbt_duckdb_found = any("dbt-duckdb" in pkg for pkg in packages)
        assert dbt_duckdb_found

    @pytest.mark.requirement("001-FR-004")
    def test_packages_have_version_constraints(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test packages include version constraints."""
        packages = duckdb_plugin.get_required_dbt_packages()

        # Each package should have version constraint (>=, ==, etc.)
        for pkg in packages:
            assert ">=" in pkg or "==" in pkg or "~=" in pkg, f"Missing version constraint: {pkg}"


class TestResourceRequirements:
    """Test K8s resource requirements."""

    @pytest.mark.requirement("001-FR-005")
    @pytest.mark.parametrize("size", ["small", "medium", "large"])
    def test_get_resource_requirements_valid_sizes(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        size: str,
    ) -> None:
        """Test resource requirements for valid workload sizes."""
        spec = duckdb_plugin.get_resource_requirements(size)

        assert spec.cpu_request is not None
        assert spec.cpu_limit is not None
        assert spec.memory_request is not None
        assert spec.memory_limit is not None

    @pytest.mark.requirement("001-FR-005")
    def test_get_resource_requirements_invalid_size(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test resource requirements raises error for invalid size."""
        with pytest.raises(ValueError, match="Unknown workload size"):
            duckdb_plugin.get_resource_requirements("invalid")

    @pytest.mark.requirement("001-FR-005")
    def test_resource_requirements_scaling(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test larger sizes have more resources."""
        small = duckdb_plugin.get_resource_requirements("small")
        medium = duckdb_plugin.get_resource_requirements("medium")
        large = duckdb_plugin.get_resource_requirements("large")

        # Memory should scale: small < medium < large
        def parse_memory(mem: str) -> int:
            """Parse memory string to bytes."""
            if mem.endswith("Gi"):
                return int(mem[:-2]) * 1024
            if mem.endswith("Mi"):
                return int(mem[:-2])
            return int(mem)

        small_mem = parse_memory(small.memory_limit)
        medium_mem = parse_memory(medium.memory_limit)
        large_mem = parse_memory(large.memory_limit)

        assert small_mem < medium_mem < large_mem


class TestCatalogAttachment:
    """Test Iceberg catalog attachment SQL generation."""

    @pytest.mark.requirement("001-FR-006")
    def test_get_catalog_attachment_sql(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        catalog_config: CatalogConfig,
    ) -> None:
        """Test catalog attachment SQL is generated."""
        sql = duckdb_plugin.get_catalog_attachment_sql(catalog_config)

        assert sql is not None
        assert isinstance(sql, list)
        assert len(sql) > 0

    @pytest.mark.requirement("001-FR-006")
    def test_catalog_attachment_installs_extension(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        catalog_config: CatalogConfig,
    ) -> None:
        """Test catalog attachment includes INSTALL iceberg."""
        sql = duckdb_plugin.get_catalog_attachment_sql(catalog_config)

        assert sql is not None
        assert any("INSTALL iceberg" in stmt for stmt in sql)

    @pytest.mark.requirement("001-FR-006")
    def test_catalog_attachment_loads_extension(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        catalog_config: CatalogConfig,
    ) -> None:
        """Test catalog attachment includes LOAD iceberg."""
        sql = duckdb_plugin.get_catalog_attachment_sql(catalog_config)

        assert sql is not None
        assert any("LOAD iceberg" in stmt for stmt in sql)

    @pytest.mark.requirement("001-FR-006")
    def test_catalog_attachment_includes_endpoint(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        catalog_config: CatalogConfig,
    ) -> None:
        """Test catalog attachment includes catalog endpoint."""
        sql = duckdb_plugin.get_catalog_attachment_sql(catalog_config)

        assert sql is not None
        attach_stmt = [s for s in sql if "ATTACH" in s][0]
        assert catalog_config.catalog_uri in attach_stmt
