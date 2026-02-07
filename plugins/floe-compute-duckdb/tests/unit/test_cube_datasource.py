"""Unit tests for DuckDB Cube datasource configuration.

Tests validate get_cube_datasource_config() returns correct configuration
for Cube to use DuckDB as a datasource, including initSql with Iceberg
INSTALL/LOAD/ATTACH statements when catalog config is provided.

Requirements Covered:
    - FR-029: DuckDB provides Cube datasource config
    - FR-030: Datasource config includes initSql with Iceberg attachment
    - FR-031: Datasource config includes DuckDB-specific settings
    - SC-009: DuckDB compute plugin provides Cube-compatible config
"""

from __future__ import annotations

import pytest
from floe_core.compute_config import CatalogConfig

from floe_compute_duckdb.plugin import DuckDBComputePlugin


@pytest.mark.requirement("FR-029")
class TestCubeDatasourceConfigBasic:
    """Test basic get_cube_datasource_config() behavior."""

    def test_returns_dict(self) -> None:
        """Test get_cube_datasource_config returns a dictionary."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config()
        assert isinstance(result, dict)

    def test_includes_type_duckdb(self) -> None:
        """Test config includes type=duckdb."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config()
        assert result["type"] == "duckdb"

    def test_includes_database_path(self) -> None:
        """Test config includes databasePath."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config()
        assert "database_path" in result

    def test_default_database_path_is_memory(self) -> None:
        """Test default database path is :memory:."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config()
        assert result["database_path"] == ":memory:"


@pytest.mark.requirement("FR-030")
class TestCubeDatasourceWithCatalog:
    """Test get_cube_datasource_config with CatalogConfig."""

    @pytest.fixture
    def catalog_config(self) -> CatalogConfig:
        """Create a test CatalogConfig."""
        return CatalogConfig(
            catalog_type="rest",
            catalog_uri="http://polaris:8181/api/catalog",
            catalog_name="ice",
            warehouse="floe_warehouse",
        )

    def test_includes_init_sql_with_catalog(self, catalog_config: CatalogConfig) -> None:
        """Test config includes initSql when catalog_config provided."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config(catalog_config=catalog_config)
        assert "init_sql" in result
        assert isinstance(result["init_sql"], str)

    def test_init_sql_contains_install_iceberg(self, catalog_config: CatalogConfig) -> None:
        """Test initSql contains INSTALL iceberg."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config(catalog_config=catalog_config)
        assert "INSTALL iceberg" in result["init_sql"]

    def test_init_sql_contains_load_iceberg(self, catalog_config: CatalogConfig) -> None:
        """Test initSql contains LOAD iceberg."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config(catalog_config=catalog_config)
        assert "LOAD iceberg" in result["init_sql"]

    def test_init_sql_contains_attach(self, catalog_config: CatalogConfig) -> None:
        """Test initSql contains ATTACH statement."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config(catalog_config=catalog_config)
        assert "ATTACH" in result["init_sql"]


@pytest.mark.requirement("FR-029")
class TestCubeDatasourceWithoutCatalog:
    """Test get_cube_datasource_config without CatalogConfig."""

    def test_no_init_sql_without_catalog(self) -> None:
        """Test no initSql when catalog_config is None."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config()
        assert "init_sql" not in result

    def test_basic_config_without_catalog(self) -> None:
        """Test basic config structure without catalog."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config()
        assert result["type"] == "duckdb"
        assert result["database_path"] == ":memory:"


@pytest.mark.requirement("FR-031")
@pytest.mark.requirement("SC-009")
class TestCubeDatasourceAllKeys:
    """Test all Cube-required keys are present."""

    def test_all_required_keys_present(self) -> None:
        """Test all keys needed by Cube are present."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config()
        required_keys = {"type", "database_path"}
        assert required_keys.issubset(result.keys())

    def test_custom_database_path(self) -> None:
        """Test custom database path is passed through."""
        plugin = DuckDBComputePlugin()
        result = plugin.get_cube_datasource_config(database_path="/data/analytics.duckdb")
        assert result["database_path"] == "/data/analytics.duckdb"
