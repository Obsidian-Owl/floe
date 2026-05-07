"""Unit tests for the orchestrator-neutral Iceberg writer contract."""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pytest

from floe_iceberg.errors import StaleTableMetadataError
from floe_iceberg.models import IcebergTableManagerConfig, StaleTableRecoveryMode
from floe_iceberg.writer import (
    DefaultIcebergTableWriter,
    IcebergTableWrite,
    IcebergWriterResult,
)


class _NoSuchTableError(Exception):
    """Test-local missing table signal."""


class _NamespaceAlreadyExistsError(Exception):
    """Test-local existing namespace signal."""


class _FakeTable:
    """Minimal Iceberg table test double."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        self.appended: list[Any] = []
        self.overwritten: list[Any] = []
        self.refreshed = 0

    def append(self, data: Any) -> None:
        self.appended.append(data)

    def overwrite(self, data: Any) -> None:
        self.overwritten.append(data)

    def refresh(self) -> None:
        self.refreshed += 1


class _WriteCapableCatalog:
    """Write-capable catalog test double."""

    def __init__(self) -> None:
        self.namespaces: list[str] = []
        self.create_namespace_calls: list[tuple[str, dict[str, str] | None]] = []
        self.load_table_calls: list[str] = []
        self.created_tables: list[tuple[str, Any]] = []
        self.tables: dict[str, _FakeTable] = {}
        self.raise_namespace_exists = False

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        self.create_namespace_calls.append((namespace, properties))
        if self.raise_namespace_exists:
            raise _NamespaceAlreadyExistsError(f"Namespace {namespace} already exists")
        self.namespaces.append(namespace)

    def load_table(self, identifier: str) -> _FakeTable:
        self.load_table_calls.append(identifier)
        if identifier not in self.tables:
            raise _NoSuchTableError(identifier)
        return self.tables[identifier]

    def create_table(self, identifier: str, schema: Any) -> _FakeTable:
        table = _FakeTable(identifier)
        self.created_tables.append((identifier, schema))
        self.tables[identifier] = table
        return table


class _CatalogPlugin:
    """Catalog plugin test double returning a connected catalog."""

    def __init__(self, catalog: _WriteCapableCatalog) -> None:
        self.catalog = catalog
        self.connect_configs: list[dict[str, Any]] = []

    def connect(self, config: dict[str, Any]) -> _WriteCapableCatalog:
        self.connect_configs.append(config)
        return self.catalog


class _EndpointPreservingCatalogPlugin(_CatalogPlugin):
    """Catalog plugin with endpoint-preserving load hook."""

    def __init__(
        self,
        catalog: _WriteCapableCatalog,
        endpoint_table: _FakeTable,
    ) -> None:
        super().__init__(catalog)
        self.endpoint_table = endpoint_table
        self.endpoint_loads: list[str] = []

    def load_table_with_client_endpoint(self, identifier: str) -> _FakeTable:
        self.endpoint_loads.append(identifier)
        return self.endpoint_table


class _StaleMetadataCatalog(_WriteCapableCatalog):
    """Catalog that fails loads with a stale metadata not-found error."""

    def load_table(self, identifier: str) -> _FakeTable:
        self.load_table_calls.append(identifier)
        raise RuntimeError(
            "metadata file "
            "s3://warehouse/customer_360/customers/metadata/v1.metadata.json not found"
        )


class _ReconnectCatalogPlugin:
    """Catalog plugin returning a stale catalog first and repair catalog next."""

    def __init__(
        self,
        stale_catalog: _StaleMetadataCatalog,
        repaired_catalog: _WriteCapableCatalog,
    ) -> None:
        self._catalogs: list[_WriteCapableCatalog] = [stale_catalog, repaired_catalog]
        self.connect_configs: list[dict[str, Any]] = []
        self.drop_table_calls: list[tuple[str, bool]] = []

    def connect(self, config: dict[str, Any]) -> _WriteCapableCatalog:
        self.connect_configs.append(config)
        if len(self.connect_configs) == 1:
            return self._catalogs[0]
        return self._catalogs[1]

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        self.drop_table_calls.append((identifier, purge))


def _arrow_table() -> pa.Table:
    return pa.table({"id": [1], "name": ["Ada"]})


def _writer(catalog: _WriteCapableCatalog) -> DefaultIcebergTableWriter:
    return DefaultIcebergTableWriter(
        catalog_plugin=_CatalogPlugin(catalog),
        storage_plugin=object(),
        catalog_connection_config={"uri": "http://catalog.example"},
    )


def test_write_tables_creates_namespace_and_returns_written_result() -> None:
    catalog = _WriteCapableCatalog()
    arrow_table = _arrow_table()
    write = IcebergTableWrite(
        identifier="customer_360.customers",
        arrow_table=arrow_table,
    )

    result = _writer(catalog).write_tables("customer_360", [write])

    assert result == IcebergWriterResult(
        tables_written=1,
        table_names=("customer_360.customers",),
    )
    assert catalog.create_namespace_calls == [("customer_360", None)]
    assert catalog.tables["customer_360.customers"].appended == [arrow_table]


def test_existing_namespace_exception_is_success() -> None:
    catalog = _WriteCapableCatalog()
    catalog.raise_namespace_exists = True
    arrow_table = _arrow_table()
    write = IcebergTableWrite(
        identifier="customer_360.customers",
        arrow_table=arrow_table,
    )

    result = _writer(catalog).write_tables("customer_360", [write])

    assert result.tables_written == 1
    assert result.table_names == ("customer_360.customers",)


def test_missing_table_creates_table_with_arrow_schema_then_appends() -> None:
    catalog = _WriteCapableCatalog()
    arrow_table = _arrow_table()
    write = IcebergTableWrite(
        identifier="customer_360.customers",
        arrow_table=arrow_table,
        mode="append",
    )

    _writer(catalog).write_table(write.identifier, write.arrow_table, mode=write.mode)

    assert catalog.created_tables == [("customer_360.customers", arrow_table.schema)]
    assert catalog.tables["customer_360.customers"].appended == [arrow_table]


def test_write_table_defaults_to_overwrite_existing_table() -> None:
    catalog = _WriteCapableCatalog()
    arrow_table = _arrow_table()
    table = _FakeTable("customer_360.customers")
    catalog.tables["customer_360.customers"] = table

    _writer(catalog).write_table("customer_360.customers", arrow_table)

    assert table.overwritten == [arrow_table]
    assert table.appended == []


def test_write_table_rejects_invalid_mode_before_catalog_mutation() -> None:
    catalog = _WriteCapableCatalog()
    writer = _writer(catalog)

    with pytest.raises(ValueError, match="Unsupported Iceberg write mode"):
        writer.write_table(
            "customer_360.customers",
            _arrow_table(),
            mode="replace",  # type: ignore[arg-type]
        )

    assert catalog.create_namespace_calls == []
    assert catalog.load_table_calls == []
    assert catalog.created_tables == []


def test_write_tables_rejects_invalid_mode_before_catalog_mutation() -> None:
    catalog = _WriteCapableCatalog()
    writer = _writer(catalog)

    with pytest.raises(ValueError, match="Unsupported Iceberg write mode"):
        writer.write_tables(
            "customer_360",
            [
                IcebergTableWrite(
                    identifier="customer_360.customers",
                    arrow_table=_arrow_table(),
                    mode="replace",  # type: ignore[arg-type]
                )
            ],
        )

    assert catalog.create_namespace_calls == []
    assert catalog.load_table_calls == []
    assert catalog.created_tables == []


def test_write_table_repairs_stale_metadata_in_repair_mode() -> None:
    stale_catalog = _StaleMetadataCatalog()
    repaired_catalog = _WriteCapableCatalog()
    plugin = _ReconnectCatalogPlugin(stale_catalog, repaired_catalog)
    arrow_table = _arrow_table()
    writer = DefaultIcebergTableWriter(
        catalog_plugin=plugin,
        storage_plugin=object(),
        catalog_connection_config={"uri": "http://catalog.example"},
        config=IcebergTableManagerConfig(
            stale_table_recovery_mode=StaleTableRecoveryMode.REPAIR,
        ),
    )

    writer.write_table("customer_360.customers", arrow_table)

    assert stale_catalog.created_tables == []
    assert plugin.drop_table_calls == [("customer_360.customers", False)]
    assert len(plugin.connect_configs) == 2
    assert repaired_catalog.created_tables == [("customer_360.customers", arrow_table.schema)]
    assert repaired_catalog.tables["customer_360.customers"].appended == [arrow_table]


def test_write_table_raises_stale_metadata_error_in_strict_mode() -> None:
    class _StaleOverwriteTable(_FakeTable):
        def overwrite(self, data: Any) -> None:
            raise RuntimeError(
                "metadata file "
                "s3://warehouse/customer_360/customers/metadata/v1.metadata.json not found"
            )

    catalog = _WriteCapableCatalog()
    catalog.tables["customer_360.customers"] = _StaleOverwriteTable(
        "customer_360.customers",
    )
    plugin = _CatalogPlugin(catalog)
    writer = DefaultIcebergTableWriter(
        catalog_plugin=plugin,
        storage_plugin=object(),
        catalog_connection_config={"uri": "http://catalog.example"},
        config=IcebergTableManagerConfig(
            stale_table_recovery_mode=StaleTableRecoveryMode.STRICT,
        ),
    )

    with pytest.raises(StaleTableMetadataError) as exc_info:
        writer.write_table("customer_360.customers", _arrow_table(), mode="overwrite")

    stale_error = exc_info.value
    assert stale_error.table_identifier == "customer_360.customers"
    assert stale_error.recovery_mode is StaleTableRecoveryMode.STRICT
    assert (
        stale_error.metadata_location
        == "s3://warehouse/customer_360/customers/metadata/v1.metadata.json"
    )
    assert stale_error.details["recovery_mode"] == "strict"


def test_endpoint_preserving_loader_on_catalog_plugin_is_used_when_available() -> None:
    catalog = _WriteCapableCatalog()
    catalog.tables["customer_360.customers"] = _FakeTable("customer_360.customers")
    endpoint_table = _FakeTable("customer_360.customers")
    plugin = _EndpointPreservingCatalogPlugin(catalog, endpoint_table)
    arrow_table = _arrow_table()
    writer = DefaultIcebergTableWriter(
        catalog_plugin=plugin,
        storage_plugin=object(),
    )

    writer.write_table("customer_360.customers", arrow_table)

    assert plugin.endpoint_loads == ["customer_360.customers"]
    assert endpoint_table.overwritten == [arrow_table]
    assert catalog.tables["customer_360.customers"].overwritten == []


def test_catalog_without_write_methods_is_rejected() -> None:
    class ReadOnlyCatalogPlugin:
        def connect(self, config: dict[str, Any]) -> object:
            return object()

    writer = DefaultIcebergTableWriter(
        catalog_plugin=ReadOnlyCatalogPlugin(),
        storage_plugin=object(),
    )

    with pytest.raises(RuntimeError, match="write-capable Iceberg catalog"):
        writer.write_tables(
            "customer_360",
            [
                IcebergTableWrite(
                    identifier="customer_360.customers",
                    arrow_table=_arrow_table(),
                )
            ],
        )
