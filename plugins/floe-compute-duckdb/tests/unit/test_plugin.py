"""Unit tests for DuckDBComputePlugin.

These tests verify the DuckDB compute plugin implementation without
requiring external services.

Note: @pytest.mark.requirement markers are only used for integration tests.
Unit tests validate implementation correctness; integration tests validate requirements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.compute_config import CatalogConfig, ComputeConfig

    from floe_compute_duckdb import DuckDBComputePlugin


class TestDuckDBComputePluginMetadata:
    """Test plugin metadata properties."""

    def test_plugin_name(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test plugin name is 'duckdb'."""
        assert duckdb_plugin.name == "duckdb"

    def test_plugin_version(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test plugin version follows semver format."""
        version = duckdb_plugin.version
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_floe_api_version(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test floe API version is specified."""
        api_version = duckdb_plugin.floe_api_version
        assert api_version == "1.0"

    def test_is_self_hosted(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test DuckDB is self-hosted (runs in platform K8s)."""
        assert duckdb_plugin.is_self_hosted is True

    def test_plugin_description(self, duckdb_plugin: DuckDBComputePlugin) -> None:
        """Test plugin has a description."""
        assert len(duckdb_plugin.description) > 0
        assert "DuckDB" in duckdb_plugin.description


class TestGenerateDBTProfile:
    """Test dbt profile generation.

    Tests implementation of generate_dbt_profile() method which should:
    - Return correct dbt profile structure for dbt-duckdb adapter
    - Support Iceberg extension configuration (FR-007)
    - Generate valid profiles (FR-008)
    """

    def test_generate_dbt_profile_minimal(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test profile generation with minimal configuration.

        Verifies correct dbt profile structure with required keys.
        """
        profile = duckdb_plugin.generate_dbt_profile(memory_config)

        assert profile["type"] == "duckdb"
        assert profile["path"] == ":memory:"
        assert profile["threads"] == 4

    def test_generate_dbt_profile_structure(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test dbt profile has all required keys for dbt-duckdb adapter."""
        profile = duckdb_plugin.generate_dbt_profile(memory_config)

        # Required keys for dbt-duckdb adapter
        assert "type" in profile
        assert "path" in profile
        assert "threads" in profile
        assert profile["type"] == "duckdb"

    def test_generate_dbt_profile_with_iceberg_extension(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation includes iceberg extension for Iceberg support."""
        from floe_core.compute_config import ComputeConfig

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
        assert "iceberg" in profile["extensions"]
        assert profile["threads"] == 8

    def test_generate_dbt_profile_with_extensions(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation includes extensions when specified."""
        from floe_core.compute_config import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=8,
            connection={
                "path": "/data/analytics.duckdb",
                "extensions": ["parquet", "json"],
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert profile["extensions"] == ["parquet", "json"]
        assert profile["threads"] == 8

    def test_generate_dbt_profile_with_settings(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation includes DuckDB settings."""
        from floe_core.compute_config import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            connection={
                "path": ":memory:",
                "settings": {"memory_limit": "4GB"},
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert profile["settings"]["memory_limit"] == "4GB"

    def test_generate_dbt_profile_normalizes_top_level_settings(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile normalizes memory_limit from top-level connection to settings.

        When manifest config places memory_limit at the connection top level
        (not nested under 'settings'), the plugin must move it into
        profile['settings'] so the dbt-duckdb adapter picks it up.
        """
        from floe_core.compute_config import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={
                "memory_limit": "2GB",
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert "settings" in profile
        assert profile["settings"]["memory_limit"] == "2GB"

    def test_generate_dbt_profile_explicit_settings_override_top_level(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test explicit settings dict takes precedence over top-level keys."""
        from floe_core.compute_config import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            connection={
                "memory_limit": "2GB",
                "settings": {"memory_limit": "8GB", "threads": 2},
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert profile["settings"]["memory_limit"] == "8GB"
        assert profile["settings"]["threads"] == 2

    def test_generate_dbt_profile_with_file_path(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation with file-based database path."""
        from floe_core.compute_config import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={
                "path": "/data/analytics.duckdb",
            },
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert profile["path"] == "/data/analytics.duckdb"
        assert profile["threads"] == 4

    def test_generate_dbt_profile_no_extensions_when_empty(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test profile omits extensions key when no extensions specified."""
        profile = duckdb_plugin.generate_dbt_profile(memory_config)

        # Extensions should not be in profile when empty
        assert "extensions" not in profile

    def test_generate_dbt_profile_with_timeout(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation includes timeout_seconds when configured.

        Validates FR-021: Query timeout enforcement via dbt profile.
        The dbt-duckdb adapter handles actual timeout enforcement.
        """
        from floe_core.compute_config import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            timeout_seconds=300,  # 5 minute timeout
            connection={"path": ":memory:"},
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        assert profile["timeout_seconds"] == 300

    def test_generate_dbt_profile_uses_default_timeout(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile includes default timeout_seconds value (3600).

        When timeout_seconds is not explicitly set in ComputeConfig,
        the default value (3600 seconds = 1 hour) is used in the
        generated dbt profile.
        """
        from floe_core.compute_config import ComputeConfig

        config = ComputeConfig(
            plugin="duckdb",
            threads=4,
            connection={"path": ":memory:"},
        )

        profile = duckdb_plugin.generate_dbt_profile(config)

        # Default timeout (3600) should be included in profile
        assert "timeout_seconds" in profile
        assert profile["timeout_seconds"] == 3600  # Default value


class TestGenerateDBTProfileWithAttach:
    """Test dbt profile generation with attach blocks.

    Tests attach block support for Iceberg catalog attachment.
    """

    def test_generate_dbt_profile_with_attach(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation includes attach blocks when configured."""
        from floe_core.compute_config import ComputeConfig

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

    def test_generate_dbt_profile_with_multiple_attach(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test profile generation with multiple attach blocks."""
        from floe_core.compute_config import ComputeConfig

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

    def test_generate_dbt_profile_attach_with_options(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test attach block options are rendered properly."""
        from floe_core.compute_config import ComputeConfig

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

    def test_generate_dbt_profile_without_attach(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        memory_config: ComputeConfig,
    ) -> None:
        """Test profile generation without attach blocks."""
        profile = duckdb_plugin.generate_dbt_profile(memory_config)

        assert "attach" not in profile

    def test_generate_dbt_profile_attach_minimal(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test attach with only required path field."""
        from floe_core.compute_config import ComputeConfig

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

    def test_get_resource_requirements_invalid_size(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test resource requirements raises error for invalid size."""
        with pytest.raises(ValueError, match="Unknown workload size"):
            duckdb_plugin.get_resource_requirements("invalid")

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

    def test_catalog_attachment_installs_extension(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        catalog_config: CatalogConfig,
    ) -> None:
        """Test catalog attachment includes INSTALL iceberg."""
        sql = duckdb_plugin.get_catalog_attachment_sql(catalog_config)

        assert sql is not None
        assert any("INSTALL iceberg" in stmt for stmt in sql)

    def test_catalog_attachment_loads_extension(
        self,
        duckdb_plugin: DuckDBComputePlugin,
        catalog_config: CatalogConfig,
    ) -> None:
        """Test catalog attachment includes LOAD iceberg."""
        sql = duckdb_plugin.get_catalog_attachment_sql(catalog_config)

        assert sql is not None
        assert any("LOAD iceberg" in stmt for stmt in sql)

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


class TestCatalogAttachmentSecurity:
    """Test SQL injection prevention in catalog attachment.

    These tests verify that the get_catalog_attachment_sql method
    properly validates and escapes inputs to prevent SQL injection.
    """

    @pytest.mark.requirement("001-FR-002")
    def test_invalid_catalog_name_raises_error(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test that invalid catalog names raise ValueError.

        Catalog names are used as SQL identifiers (in AS clause),
        so they must be validated to prevent SQL injection.
        """
        from floe_core.compute_config import CatalogConfig

        # SQL injection attempt via catalog_name
        config = CatalogConfig(
            catalog_type="rest",
            catalog_name="malicious'; DROP TABLE users; --",
            catalog_uri="http://polaris:8181/api/catalog",
        )

        with pytest.raises(ValueError, match="Invalid catalog_name"):
            duckdb_plugin.get_catalog_attachment_sql(config)

    @pytest.mark.requirement("001-FR-002")
    def test_catalog_name_with_special_chars_raises_error(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test that catalog names with special characters raise ValueError."""
        from floe_core.compute_config import CatalogConfig

        invalid_names = [
            "catalog-with-dash",
            "catalog.with.dots",
            "catalog with spaces",
            "catalog'quote",
            "123startwithnumber",
        ]

        for name in invalid_names:
            config = CatalogConfig(
                catalog_type="rest",
                catalog_name=name,
                catalog_uri="http://polaris:8181/api/catalog",
            )

            with pytest.raises(ValueError, match="Invalid catalog_name"):
                duckdb_plugin.get_catalog_attachment_sql(config)

    @pytest.mark.requirement("001-FR-002")
    def test_valid_catalog_names_accepted(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test that valid catalog names are accepted."""
        from floe_core.compute_config import CatalogConfig

        valid_names = [
            "floe",
            "my_catalog",
            "_private",
            "catalog123",
            "UPPERCASE",
            "MixedCase_123",
        ]

        for name in valid_names:
            config = CatalogConfig(
                catalog_type="rest",
                catalog_name=name,
                catalog_uri="http://polaris:8181/api/catalog",
            )

            # Should not raise
            sql = duckdb_plugin.get_catalog_attachment_sql(config)
            assert sql is not None

    @pytest.mark.requirement("001-FR-002")
    def test_uri_with_quotes_escaped(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test that single quotes in URI are properly escaped."""
        from floe_core.compute_config import CatalogConfig

        config = CatalogConfig(
            catalog_type="rest",
            catalog_name="test_catalog",
            catalog_uri="http://example.com/path?param='value'",
        )

        sql = duckdb_plugin.get_catalog_attachment_sql(config)
        assert sql is not None

        attach_stmt = [s for s in sql if "ATTACH" in s][0]
        # Single quotes should be doubled for SQL escaping
        assert "''value''" in attach_stmt

    @pytest.mark.requirement("001-FR-002")
    def test_warehouse_with_quotes_escaped(
        self,
        duckdb_plugin: DuckDBComputePlugin,
    ) -> None:
        """Test that single quotes in warehouse path are properly escaped."""
        from floe_core.compute_config import CatalogConfig

        config = CatalogConfig(
            catalog_type="rest",
            catalog_name="test_catalog",
            catalog_uri="http://polaris:8181/api/catalog",
            warehouse="s3://bucket/path'with'quotes",
        )

        sql = duckdb_plugin.get_catalog_attachment_sql(config)
        assert sql is not None

        attach_stmt = [s for s in sql if "ATTACH" in s][0]
        # Single quotes should be doubled for SQL escaping
        assert "path''with''quotes" in attach_stmt
