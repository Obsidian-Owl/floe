"""Ingestion plugin pytest fixtures for unit and integration tests.

Provides fixtures for DltIngestionPlugin testing including configuration,
plugin instances, sample source configs, mock dlt sources, and helpers.

Example:
    from testing.fixtures.ingestion import dlt_config, dlt_plugin

    def test_with_dlt(dlt_plugin):
        assert dlt_plugin.name == "dlt"

Requirements Covered:
    - 4F-FR-001: Test fixtures for ingestion plugin
    - 4F-FR-002: Sample source configuration fixture
    - 4F-FR-003: Mock dlt source fixture
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any

import pytest
from floe_core.plugins.ingestion import IngestionConfig
from floe_ingestion_dlt.config import (
    DltIngestionConfig,
    IngestionSourceConfig,
    RetryConfig,
)
from floe_ingestion_dlt.plugin import DltIngestionPlugin
from pydantic import SecretStr


@pytest.fixture(scope="session")
def dlt_config() -> DltIngestionConfig:
    """Session-scoped DltIngestionConfig for testing.

    Returns:
        DltIngestionConfig with test defaults.
    """
    return DltIngestionConfig(
        sources=[
            IngestionSourceConfig(
                name="test_source",
                source_type="rest_api",
                source_config={
                    "url": "https://api.example.com/data",
                    "method": "GET",
                },
                destination_table="test_schema.test_table",
                write_mode="append",
                schema_contract="evolve",
            )
        ],
        catalog_config={},
        retry_config=RetryConfig(),
    )


@pytest.fixture
def dlt_plugin() -> Generator[DltIngestionPlugin, None, None]:
    """Function-scoped DltIngestionPlugin instance.

    Creates a plugin, runs startup, yields it, then runs shutdown.

    Note:
        DltIngestionPlugin does not take config in __init__.
        Configuration is passed via create_pipeline() method.

    Yields:
        Started DltIngestionPlugin instance.
    """
    plugin = DltIngestionPlugin()
    plugin.startup()
    yield plugin
    plugin.shutdown()


@pytest.fixture
def sample_ingestion_source_config() -> IngestionSourceConfig:
    """Create a sample IngestionSourceConfig for testing.

    Returns:
        IngestionSourceConfig with REST API source configuration.
    """
    return IngestionSourceConfig(
        name="sample_rest_api",
        source_type="rest_api",
        source_config={
            "url": "https://api.example.com/users",
            "method": "GET",
            "headers": {"Accept": "application/json"},
        },
        destination_table="analytics.users",
        write_mode="append",
        schema_contract="evolve",
        cursor_field="updated_at",
        primary_key="user_id",
    )


@pytest.fixture
def mock_dlt_source() -> Callable[[], Generator[dict[str, Any], None, None]]:
    """Create a mock dlt source that yields sample data dicts.

    Returns:
        Callable that yields dictionaries representing data rows.
    """

    def _source() -> Generator[dict[str, Any], None, None]:
        """Yield sample data records."""
        yield {"id": 1, "name": "Alice", "email": "alice@example.com"}
        yield {"id": 2, "name": "Bob", "email": "bob@example.com"}
        yield {"id": 3, "name": "Charlie", "email": "charlie@example.com"}

    return _source


@pytest.fixture
def sample_ingestion_config() -> IngestionConfig:
    """Create a minimal IngestionConfig (floe-core dataclass) for testing.

    Returns:
        IngestionConfig with minimal required fields.
    """
    return IngestionConfig(
        source_type="rest_api",
        source_config={
            "url": "https://api.example.com/data",
            "method": "GET",
        },
        destination_table="analytics.sample_data",
        write_mode="append",
        schema_contract="evolve",
    )


def create_ingestion_source_config(
    name: str = "test_source",
    source_type: str = "rest_api",
    source_config: dict[str, Any] | None = None,
    destination_table: str = "test_schema.test_table",
    write_mode: str = "append",
    schema_contract: str = "evolve",
    cursor_field: str | None = None,
    primary_key: str | list[str] | None = None,
    credentials: SecretStr | None = None,
) -> IngestionSourceConfig:
    """Factory function to create IngestionSourceConfig with overrides.

    Args:
        name: Source name (alphanumeric + _ -).
        source_type: Source type (rest_api, sql_database, filesystem).
        source_config: Source-specific configuration.
        destination_table: Destination table name.
        write_mode: Write mode (append, replace, merge).
        schema_contract: Schema evolution policy (evolve, freeze, discard_value).
        cursor_field: Optional cursor field for incremental loading.
        primary_key: Optional primary key(s) for merge operations.
        credentials: Optional credentials for source connection.

    Returns:
        IngestionSourceConfig with provided overrides.
    """
    if source_config is None:
        source_config = {"url": "https://api.example.com/data"}

    return IngestionSourceConfig(
        name=name,
        source_type=source_type,
        source_config=source_config,
        destination_table=destination_table,
        write_mode=write_mode,
        schema_contract=schema_contract,
        cursor_field=cursor_field,
        primary_key=primary_key,
        credentials=credentials,
    )


def create_dlt_ingestion_config(
    sources: list[IngestionSourceConfig] | None = None,
    catalog_config: dict[str, Any] | None = None,
    retry_config: RetryConfig | None = None,
) -> DltIngestionConfig:
    """Factory function to create DltIngestionConfig with overrides.

    Args:
        sources: List of source configurations. Defaults to single test source.
        catalog_config: Catalog configuration. Defaults to empty dict.
        retry_config: Retry configuration. Defaults to RetryConfig().

    Returns:
        DltIngestionConfig with provided overrides.
    """
    if sources is None:
        sources = [
            IngestionSourceConfig(
                name="default_test_source",
                source_type="rest_api",
                source_config={"url": "https://api.example.com/data"},
                destination_table="test_schema.test_table",
                write_mode="append",
                schema_contract="evolve",
            )
        ]

    if catalog_config is None:
        catalog_config = {}

    if retry_config is None:
        retry_config = RetryConfig()

    return DltIngestionConfig(
        sources=sources,
        catalog_config=catalog_config,
        retry_config=retry_config,
    )


__all__ = [
    "dlt_config",
    "dlt_plugin",
    "sample_ingestion_source_config",
    "mock_dlt_source",
    "sample_ingestion_config",
    "create_ingestion_source_config",
    "create_dlt_ingestion_config",
]
