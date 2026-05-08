# Iceberg Writer Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move direct Iceberg table mutation out of the Dagster exporter and behind a typed, orchestrator-neutral writer contract in `floe-iceberg`.

**Architecture:** `floe-iceberg` owns the public writer contract and default implementation because Iceberg is enforced platform behavior. Dagster keeps runtime coordination and DuckDB result extraction, then delegates Arrow table writes to the writer. Catalog and storage plugins remain injected dependencies and do not learn Dagster-specific concepts.

**Tech Stack:** Python 3.10+, dataclasses, typing protocols, Pydantic v2, PyArrow, DuckDB, PyIceberg, pytest, Ruff, mypy.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-05-07-iceberg-writer-contract-design.md`
- Issue: `https://github.com/Obsidian-Owl/floe/issues/318`
- Current exporter: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
- Iceberg package: `packages/floe-iceberg/src/floe_iceberg/`
- Export tests: `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`
- Storage architecture doc: `docs/architecture/storage-integration.md`
- Composition tracker: `docs/architecture/plugin-composition-uplift-tracker.md`

## File Structure

- Create `packages/floe-iceberg/src/floe_iceberg/writer.py`
  - Owns `IcebergWriteMode`, `IcebergTableWriter`, `IcebergTableWrite`, `IcebergWriterResult`, helper protocols, and `DefaultIcebergTableWriter`.
  - Contains all namespace/table mutation and stale metadata repair logic currently embedded in the Dagster exporter.
- Modify `packages/floe-iceberg/src/floe_iceberg/__init__.py`
  - Lazy-export writer types so package consumers can import them without eager PyIceberg imports.
- Create `packages/floe-iceberg/tests/unit/test_writer.py`
  - Covers writer behavior with mocks and PyArrow tables.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
  - Remove write-capable catalog protocols and direct table mutation.
  - Keep DuckDB profile resolution, table discovery, safety filtering, and plugin loading.
  - Construct `DefaultIcebergTableWriter` after the DuckDB file exists and delegate writes.
- Modify `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`
  - Replace direct catalog mutation assertions with writer delegation assertions where relevant.
  - Preserve existing skip, profile-path, missing file, unsafe identifier, empty table, and no-tables behavior.
- Modify `docs/architecture/storage-integration.md`
  - Document the writer ownership boundary.
- Modify `docs/architecture/plugin-composition-uplift-tracker.md`
  - Mark issue #318 as the Iceberg runtime writer boundary follow-up.

## Task 1: Add the `floe-iceberg` Writer Contract

**Files:**
- Create: `packages/floe-iceberg/src/floe_iceberg/writer.py`
- Modify: `packages/floe-iceberg/src/floe_iceberg/__init__.py`
- Test: `packages/floe-iceberg/tests/unit/test_writer.py`

- [ ] **Step 1: Write failing writer contract tests**

Create `packages/floe-iceberg/tests/unit/test_writer.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pyarrow as pa
import pytest

from floe_iceberg.models import IcebergTableManagerConfig, StaleTableRecoveryMode
from floe_iceberg.writer import (
    DefaultIcebergTableWriter,
    IcebergTableWrite,
    IcebergWriterResult,
)


class _NoSuchTableError(Exception):
    """Local sentinel for missing-table branches."""


def _arrow_table() -> pa.Table:
    return pa.table({"id": [1], "name": ["Ada"]})


def _writer(
    *,
    catalog_plugin: MagicMock | None = None,
    storage_plugin: MagicMock | None = None,
    catalog: MagicMock | None = None,
    config: IcebergTableManagerConfig | None = None,
) -> DefaultIcebergTableWriter:
    catalog = catalog or MagicMock()
    catalog_plugin = catalog_plugin or MagicMock()
    storage_plugin = storage_plugin or MagicMock()
    catalog_plugin.connect.return_value = catalog
    storage_plugin.get_pyiceberg_fileio.return_value = MagicMock()
    return DefaultIcebergTableWriter(
        catalog_plugin=catalog_plugin,
        storage_plugin=storage_plugin,
        catalog_connection_config={"s3.endpoint": "http://minio:9000"},
        config=config,
    )


def test_write_tables_creates_namespace_and_returns_result() -> None:
    catalog = MagicMock()
    table = MagicMock()
    catalog.load_table.return_value = table
    writer = _writer(catalog=catalog)

    result = writer.write_tables(
        namespace="customer_360",
        writes=[
            IcebergTableWrite(
                identifier="customer_360.customers",
                arrow_table=_arrow_table(),
            )
        ],
    )

    catalog.create_namespace.assert_called_once_with("customer_360")
    table.overwrite.assert_called_once()
    assert result == IcebergWriterResult(
        tables_written=1,
        table_names=("customer_360.customers",),
    )


def test_write_tables_treats_existing_namespace_as_success() -> None:
    catalog = MagicMock()
    catalog.create_namespace.side_effect = RuntimeError("Namespace already exists")
    catalog.load_table.return_value = MagicMock()
    writer = _writer(catalog=catalog)

    result = writer.write_tables(
        namespace="customer_360",
        writes=[
            IcebergTableWrite(
                identifier="customer_360.customers",
                arrow_table=_arrow_table(),
            )
        ],
    )

    assert result.tables_written == 1


def test_write_table_creates_missing_table_then_appends(monkeypatch: pytest.MonkeyPatch) -> None:
    import floe_iceberg.writer as writer_module

    monkeypatch.setattr(writer_module, "NoSuchTableError", _NoSuchTableError)
    catalog = MagicMock()
    created_table = MagicMock()
    catalog.load_table.side_effect = _NoSuchTableError("missing")
    catalog.create_table.return_value = created_table
    writer = _writer(catalog=catalog)
    data = _arrow_table()

    writer.write_table("customer_360.customers", data)

    catalog.create_table.assert_called_once_with(
        "customer_360.customers",
        schema=data.schema,
    )
    created_table.append.assert_called_once_with(data)


def test_write_table_uses_endpoint_preserving_loader_when_available() -> None:
    catalog = MagicMock()
    table = MagicMock()
    catalog_plugin = MagicMock()
    catalog_plugin.connect.return_value = catalog
    catalog_plugin.load_table_with_client_endpoint.return_value = table
    writer = _writer(catalog_plugin=catalog_plugin, catalog=catalog)
    data = _arrow_table()

    writer.write_table("customer_360.customers", data)

    catalog_plugin.load_table_with_client_endpoint.assert_called_once_with(
        "customer_360.customers"
    )
    table.overwrite.assert_called_once_with(data)


def test_write_table_rejects_catalog_without_write_methods() -> None:
    catalog = object()
    catalog_plugin = MagicMock()
    catalog_plugin.connect.return_value = catalog
    storage_plugin = MagicMock()
    storage_plugin.get_pyiceberg_fileio.return_value = MagicMock()

    with pytest.raises(RuntimeError, match="write-capable Iceberg catalog"):
        DefaultIcebergTableWriter(
            catalog_plugin=catalog_plugin,
            storage_plugin=storage_plugin,
            catalog_connection_config={},
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_writer.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'floe_iceberg.writer'`.

- [ ] **Step 3: Implement `writer.py`**

Create `packages/floe-iceberg/src/floe_iceberg/writer.py`:

```python
"""Orchestrator-neutral Iceberg table writer contract."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from inspect import getattr_static
from typing import Any, Literal, Protocol, cast, runtime_checkable

from floe_iceberg.errors import (
    is_stale_table_metadata_error,
    stale_table_metadata_error_from_exception,
)
from floe_iceberg.models import IcebergTableManagerConfig, StaleTableRecoveryMode

try:
    from pyiceberg.exceptions import NoSuchTableError
except Exception:  # pragma: no cover - exercised only when optional dependency is absent
    class NoSuchTableError(Exception):
        """Fallback used when PyIceberg is unavailable during tests."""


IcebergWriteMode = Literal["append", "overwrite"]
_NULL_SEQUENCE_OVERWRITE_ERROR = "only entries with status added can have null sequence number"


@runtime_checkable
class WriteCapableIcebergCatalog(Protocol):
    """Iceberg catalog operations required by writer execution."""

    def create_namespace(self, namespace: str) -> None:
        """Create an Iceberg namespace."""

    def load_table(self, identifier: str) -> Any:
        """Load an Iceberg table."""

    def create_table(self, identifier: str, schema: Any) -> Any:
        """Create an Iceberg table."""


class EndpointPreservingTableLoader(Protocol):
    """Optional catalog plugin hook for endpoint-preserving table loads."""

    def load_table_with_client_endpoint(self, identifier: str) -> Any:
        """Load a table while preserving client-side storage endpoint config."""


class IcebergTableWriter(Protocol):
    """Writes Arrow tables into Iceberg table identifiers."""

    def ensure_namespace(self, namespace: str) -> None:
        """Create the namespace if needed."""

    def write_table(
        self,
        identifier: str,
        arrow_table: Any,
        *,
        mode: IcebergWriteMode = "overwrite",
    ) -> None:
        """Write an Arrow table to Iceberg."""


@dataclass(frozen=True)
class IcebergTableWrite:
    """A single table write request."""

    identifier: str
    arrow_table: Any
    mode: IcebergWriteMode = "overwrite"


@dataclass(frozen=True)
class IcebergWriterResult:
    """Result proving concrete Iceberg table outputs were written."""

    tables_written: int
    table_names: tuple[str, ...]


def _require_write_capable_catalog(catalog: object, catalog_type: str) -> WriteCapableIcebergCatalog:
    required_methods: Sequence[str] = ("create_namespace", "load_table", "create_table")
    missing_methods = [
        method for method in required_methods if not callable(getattr(catalog, method, None))
    ]
    if missing_methods:
        missing = ", ".join(missing_methods)
        raise RuntimeError(
            f"Catalog plugin {catalog_type} did not return a write-capable Iceberg catalog; "
            f"missing method(s): {missing}"
        )
    return cast(WriteCapableIcebergCatalog, catalog)


def _load_table_for_overwrite(
    catalog_plugin: object,
    catalog: WriteCapableIcebergCatalog,
    identifier: str,
) -> Any:
    method_marker = getattr_static(catalog_plugin, "load_table_with_client_endpoint", None)
    method = getattr(catalog_plugin, "load_table_with_client_endpoint", None)
    if method_marker is not None and callable(method):
        endpoint_preserving_loader = cast(EndpointPreservingTableLoader, catalog_plugin)
        return endpoint_preserving_loader.load_table_with_client_endpoint(identifier)
    return catalog.load_table(identifier)


def _is_repairable_overwrite_state_error(exc: BaseException) -> bool:
    return _NULL_SEQUENCE_OVERWRITE_ERROR in str(exc).lower()


class DefaultIcebergTableWriter:
    """Default writer for Arrow tables backed by catalog and storage plugins."""

    def __init__(
        self,
        *,
        catalog_plugin: Any,
        storage_plugin: Any,
        catalog_connection_config: dict[str, Any] | None = None,
        config: IcebergTableManagerConfig | None = None,
    ) -> None:
        """Create an Iceberg writer from resolved catalog and storage plugins."""
        self._catalog_plugin = catalog_plugin
        self._storage_plugin = storage_plugin
        self._catalog_connection_config = dict(catalog_connection_config or {})
        self._config = config if config is not None else IcebergTableManagerConfig()
        self._catalog_type = str(getattr(catalog_plugin, "name", "unknown"))

        if not hasattr(storage_plugin, "get_pyiceberg_fileio"):
            raise RuntimeError("Storage plugin did not return PyIceberg FileIO support")
        storage_plugin.get_pyiceberg_fileio()
        self._catalog = self._connect_catalog()

    def _connect_catalog(self) -> WriteCapableIcebergCatalog:
        catalog = self._catalog_plugin.connect(config=self._catalog_connection_config)
        return _require_write_capable_catalog(catalog, self._catalog_type)

    def ensure_namespace(self, namespace: str) -> None:
        """Create the namespace if needed."""
        try:
            self._catalog.create_namespace(namespace)
        except Exception as exc:
            exc_name = type(exc).__name__
            if "AlreadyExists" in exc_name or "already exists" in str(exc).lower():
                return
            raise

    def write_table(
        self,
        identifier: str,
        arrow_table: Any,
        *,
        mode: IcebergWriteMode = "overwrite",
    ) -> None:
        """Write one Arrow table to Iceberg."""
        if mode == "append":
            self._append_table(identifier, arrow_table)
            return
        if mode == "overwrite":
            self._overwrite_table(identifier, arrow_table)
            return
        raise ValueError(f"Unsupported Iceberg write mode: {mode}")

    def write_tables(
        self,
        namespace: str,
        writes: Iterable[IcebergTableWrite],
    ) -> IcebergWriterResult:
        """Write a batch of Arrow tables to one namespace."""
        self.ensure_namespace(namespace)
        table_names: list[str] = []
        for write in writes:
            self.write_table(write.identifier, write.arrow_table, mode=write.mode)
            table_names.append(write.identifier)
        return IcebergWriterResult(
            tables_written=len(table_names),
            table_names=tuple(table_names),
        )

    def _append_table(self, identifier: str, arrow_table: Any) -> None:
        try:
            table = _load_table_for_overwrite(self._catalog_plugin, self._catalog, identifier)
        except NoSuchTableError:
            table = self._catalog.create_table(identifier, schema=arrow_table.schema)
        table.append(arrow_table)

    def _overwrite_table(self, identifier: str, arrow_table: Any) -> None:
        try:
            table = _load_table_for_overwrite(self._catalog_plugin, self._catalog, identifier)
            table.overwrite(arrow_table)
        except NoSuchTableError:
            table = self._catalog.create_table(identifier, schema=arrow_table.schema)
            table.append(arrow_table)
        except Exception as exc:
            if not self._should_repair(exc):
                raise
            self._repair_table(identifier, arrow_table, exc)

    def _should_repair(self, exc: BaseException) -> bool:
        return is_stale_table_metadata_error(exc) or _is_repairable_overwrite_state_error(exc)

    def _repair_table(self, identifier: str, arrow_table: Any, exc: BaseException) -> None:
        is_stale_metadata = is_stale_table_metadata_error(exc)
        if self._config.stale_table_recovery_mode is StaleTableRecoveryMode.STRICT:
            if is_stale_metadata:
                stale_error = stale_table_metadata_error_from_exception(
                    table_identifier=identifier,
                    recovery_mode=self._config.stale_table_recovery_mode,
                    original_error=exc,
                )
                raise stale_error from exc
            raise exc

        self._catalog_plugin.drop_table(identifier, purge=False)
        self._catalog = self._connect_catalog()
        table = self._catalog.create_table(identifier, schema=arrow_table.schema)
        table.append(arrow_table)


__all__ = [
    "DefaultIcebergTableWriter",
    "EndpointPreservingTableLoader",
    "IcebergTableWrite",
    "IcebergTableWriter",
    "IcebergWriteMode",
    "IcebergWriterResult",
    "WriteCapableIcebergCatalog",
]
```

- [ ] **Step 4: Export writer types lazily**

Modify `packages/floe-iceberg/src/floe_iceberg/__init__.py` by adding these names to `__all__`:

```python
    "DefaultIcebergTableWriter",
    "IcebergTableWrite",
    "IcebergTableWriter",
    "IcebergWriterResult",
```

Add these branches to `__getattr__`:

```python
    if name == "DefaultIcebergTableWriter":
        from floe_iceberg.writer import DefaultIcebergTableWriter

        return DefaultIcebergTableWriter
    if name == "IcebergTableWrite":
        from floe_iceberg.writer import IcebergTableWrite

        return IcebergTableWrite
    if name == "IcebergTableWriter":
        from floe_iceberg.writer import IcebergTableWriter

        return IcebergTableWriter
    if name == "IcebergWriterResult":
        from floe_iceberg.writer import IcebergWriterResult

        return IcebergWriterResult
```

- [ ] **Step 5: Run writer tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_writer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit writer contract**

Run:

```bash
git add packages/floe-iceberg/src/floe_iceberg/writer.py packages/floe-iceberg/src/floe_iceberg/__init__.py packages/floe-iceberg/tests/unit/test_writer.py
git commit -m "Add orchestrator-neutral Iceberg writer contract"
```

## Task 2: Move Dagster Export Writes Behind the Contract

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`

- [ ] **Step 1: Add a failing delegation test**

Append this test to `TestExportDbtToIceberg` in `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`:

```python
    @pytest.mark.requirement("AC-318")
    def test_export_delegates_table_mutation_to_iceberg_writer(
        self,
        context: MagicMock,
        project_dir: Path,
        artifacts_with_catalog: CompiledArtifacts,
    ) -> None:
        """Dagster must extract Arrow tables and delegate Iceberg mutation to floe-iceberg."""
        from floe_core.plugin_types import PluginType

        mock_conn = MagicMock()
        _configure_mock_duckdb_table(mock_conn, table_name="customers")

        registry = MagicMock()
        catalog_plugin = MagicMock()
        storage_plugin = MagicMock()
        storage_plugin.get_pyiceberg_catalog_config.return_value = {
            "s3.endpoint": "http://minio:9000"
        }

        def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
            if plugin_type is PluginType.CATALOG:
                return catalog_plugin
            return storage_plugin

        registry.get.side_effect = get_side_effect
        registry.configure.return_value = {}
        writer = MagicMock()
        writer.write_tables.return_value.tables_written = 1
        writer.write_tables.return_value.table_names = ("customer_360.customers",)

        with (
            patch("duckdb.connect", return_value=mock_conn),
            patch.object(Path, "exists", return_value=True),
            patch("floe_core.plugin_registry.get_registry", return_value=registry),
            patch(
                "floe_orchestrator_dagster.export.iceberg.DefaultIcebergTableWriter",
                return_value=writer,
            ) as writer_cls,
        ):
            result = export_dbt_to_iceberg(
                context=context,
                product_name=PRODUCT_NAME,
                project_dir=project_dir,
                artifacts=artifacts_with_catalog,
            )

        writer_cls.assert_called_once()
        writer.write_tables.assert_called_once()
        assert writer.write_tables.call_args.kwargs["namespace"] == SAFE_NAME
        writes = list(writer.write_tables.call_args.kwargs["writes"])
        assert len(writes) == 1
        assert writes[0].identifier == "customer_360.customers"
        assert result.tables_written == 1
        assert result.table_names == ["customer_360.customers"]
        catalog_plugin.connect.assert_not_called()
```

- [ ] **Step 2: Run the failing delegation test**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py::TestExportDbtToIceberg::test_export_delegates_table_mutation_to_iceberg_writer -q
```

Expected: FAIL because `DefaultIcebergTableWriter` is not imported or the exporter still mutates the catalog directly.

- [ ] **Step 3: Refactor exporter imports and remove local writer protocols**

Modify the imports at the top of `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`.

Remove:

```python
from collections.abc import Sequence
from dataclasses import dataclass
from inspect import getattr_static
from typing import Any, Protocol, cast, runtime_checkable
from floe_core.plugins.catalog import CatalogPlugin
from floe_iceberg.errors import (
    is_stale_table_metadata_error,
    stale_table_metadata_error_from_exception,
)
from floe_iceberg.models import IcebergTableManagerConfig, StaleTableRecoveryMode
```

Use:

```python
from dataclasses import dataclass
from typing import Any, cast

from floe_core.plugins.catalog import CatalogPlugin
from floe_core.plugins.storage import StoragePlugin
from floe_iceberg.models import IcebergTableManagerConfig
from floe_iceberg.writer import (
    DefaultIcebergTableWriter,
    IcebergTableWrite,
    IcebergWriterResult,
)
```

Delete these local definitions from the exporter:

```python
WriteCapableIcebergCatalog
EndpointPreservingTableLoader
_NULL_SEQUENCE_OVERWRITE_ERROR
_require_write_capable_catalog
_load_table_for_overwrite
_is_repairable_overwrite_state_error
```

- [ ] **Step 4: Replace direct mutation loop with writer delegation**

Inside `export_dbt_to_iceberg`, keep registry/configuration and DuckDB path checks. After `Path(duckdb_path).exists()` succeeds, replace direct catalog connection and mutation setup with:

```python
    import duckdb

    catalog_connection_config = _apply_compiled_storage_endpoint(
        storage_plugin.get_pyiceberg_catalog_config(),
        artifacts,
    )
    iceberg_config = IcebergTableManagerConfig.from_governance(artifacts.governance)
    writer = DefaultIcebergTableWriter(
        catalog_plugin=catalog_plugin,
        storage_plugin=storage_plugin,
        catalog_connection_config=catalog_connection_config,
        config=iceberg_config,
    )

    product_namespace = safe_name
```

Replace the per-table mutation block with:

```python
            iceberg_id = f"{product_namespace}.{table_name}"
            writes.append(
                IcebergTableWrite(
                    identifier=iceberg_id,
                    arrow_table=arrow_table,
                    mode="overwrite",
                )
            )
```

Initialize `writes` before the table loop:

```python
        writes: list[IcebergTableWrite] = []
```

After the table loop, replace the old no-table/result block with:

```python
        if not writes:
            raise RuntimeError(
                f"Configured Iceberg export wrote no tables for product {product_name}"
            )
        write_result: IcebergWriterResult = writer.write_tables(
            namespace=product_namespace,
            writes=writes,
        )
        for table_name in write_result.table_names:
            context.log.info("Exported %s to Iceberg", table_name)
        return IcebergExportResult(
            tables_written=write_result.tables_written,
            table_names=list(write_result.table_names),
        )
```

- [ ] **Step 5: Run the delegation test**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py::TestExportDbtToIceberg::test_export_delegates_table_mutation_to_iceberg_writer -q
```

Expected: PASS.

- [ ] **Step 6: Run exporter unit tests and update stale direct-mutation assertions**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py -q
```

Expected on first run: tests that assert direct `catalog.create_namespace`, `catalog.create_table`, `table.overwrite`, or `catalog_plugin.drop_table` calls may fail.

For each failed test:

- Keep tests that validate Dagster-owned behavior, such as profile resolution, missing file handling, unsafe identifier filtering, empty table filtering, no catalog/storage skips, and no disk re-read behavior.
- Rewrite tests that validate Iceberg mutation behavior to live in `packages/floe-iceberg/tests/unit/test_writer.py`.
- Where the exporter still needs coverage, patch `DefaultIcebergTableWriter` and assert `write_tables()` inputs instead of catalog calls.

Use this replacement pattern:

```python
        writer = MagicMock()
        writer.write_tables.return_value = IcebergWriterResult(
            tables_written=1,
            table_names=("customer_360.customers",),
        )

        with patch(
            "floe_orchestrator_dagster.export.iceberg.DefaultIcebergTableWriter",
            return_value=writer,
        ):
            result = export_dbt_to_iceberg(...)

        assert result.table_names == ["customer_360.customers"]
        writer.write_tables.assert_called_once()
```

- [ ] **Step 7: Commit Dagster delegation**

Run:

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py
git commit -m "Delegate Dagster Iceberg exports to writer contract"
```

## Task 3: Add Writer Regression Coverage for Repair and Strict Modes

**Files:**
- Modify: `packages/floe-iceberg/tests/unit/test_writer.py`
- Modify: `packages/floe-iceberg/src/floe_iceberg/writer.py` if tests expose small gaps

- [ ] **Step 1: Add repair-mode tests**

Append these tests to `packages/floe-iceberg/tests/unit/test_writer.py`:

```python
def test_write_table_repairs_stale_metadata_in_repair_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import floe_iceberg.writer as writer_module

    stale_error = RuntimeError(
        "metadata file s3://warehouse/customer_360/customers/metadata/v1.metadata.json not found"
    )
    monkeypatch.setattr(writer_module, "is_stale_table_metadata_error", lambda _exc: True)

    first_catalog = MagicMock()
    second_catalog = MagicMock()
    table = MagicMock()
    first_catalog.load_table.side_effect = stale_error
    second_catalog.create_table.return_value = table

    catalog_plugin = MagicMock()
    catalog_plugin.name = "polaris"
    catalog_plugin.connect.side_effect = [first_catalog, second_catalog]
    storage_plugin = MagicMock()
    storage_plugin.get_pyiceberg_fileio.return_value = MagicMock()
    writer = DefaultIcebergTableWriter(
        catalog_plugin=catalog_plugin,
        storage_plugin=storage_plugin,
        catalog_connection_config={"s3.endpoint": "http://minio:9000"},
        config=IcebergTableManagerConfig(
            stale_table_recovery_mode=StaleTableRecoveryMode.REPAIR
        ),
    )
    data = _arrow_table()

    writer.write_table("customer_360.customers", data)

    catalog_plugin.drop_table.assert_called_once_with(
        "customer_360.customers",
        purge=False,
    )
    second_catalog.create_table.assert_called_once_with(
        "customer_360.customers",
        schema=data.schema,
    )
    table.append.assert_called_once_with(data)


def test_write_table_raises_stale_metadata_error_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import floe_iceberg.writer as writer_module

    stale_error = RuntimeError("metadata file missing")
    monkeypatch.setattr(writer_module, "is_stale_table_metadata_error", lambda _exc: True)
    catalog = MagicMock()
    catalog.load_table.return_value.overwrite.side_effect = stale_error
    writer = _writer(
        catalog=catalog,
        config=IcebergTableManagerConfig(
            stale_table_recovery_mode=StaleTableRecoveryMode.STRICT
        ),
    )

    with pytest.raises(Exception, match="customer_360.customers"):
        writer.write_table("customer_360.customers", _arrow_table())
```

- [ ] **Step 2: Run repair tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_writer.py -q
```

Expected: PASS. If a test fails because the stale metadata string does not match current helper heuristics, keep the monkeypatch and fix only writer control flow.

- [ ] **Step 3: Commit repair coverage**

Run:

```bash
git add packages/floe-iceberg/tests/unit/test_writer.py packages/floe-iceberg/src/floe_iceberg/writer.py
git commit -m "Cover Iceberg writer recovery modes"
```

## Task 4: Update Architecture Documentation

**Files:**
- Modify: `docs/architecture/storage-integration.md`
- Modify: `docs/architecture/plugin-composition-uplift-tracker.md`

- [ ] **Step 1: Document writer ownership in storage integration**

In `docs/architecture/storage-integration.md`, add this section after the overview diagram:

```markdown
## Iceberg Writer Ownership

Iceberg table mutation is owned by `floe-iceberg`, not by orchestrator plugins.

Runtime orchestrators such as Dagster or Airflow coordinate execution, collect
runtime outputs, and call the `floe_iceberg.writer` contract with Arrow tables
and Iceberg identifiers. The writer owns namespace creation, table load/create,
append/overwrite behavior, and stale metadata repair.

Catalog and storage plugins remain injected dependencies. They provide catalog
connections, FileIO support, endpoint configuration, and credential references,
but they do not depend on Dagster, Airflow, or any orchestrator-specific API.

`CompiledArtifacts` remains secret-free. Runtime credential material flows
through resolved deployment bindings and plugin-owned connection logic rather
than through writer results or orchestrator logs.
```

- [ ] **Step 2: Update composition tracker**

In `docs/architecture/plugin-composition-uplift-tracker.md`, add this row to `Future Tracking Items` after `PCU-006`:

```markdown
| PCU-007 | Iceberg runtime | Extract writer contract from orchestrator export paths | Dagster and future orchestrators delegate Iceberg table mutation to `floe-iceberg` |
```

If the tracker already has a better location for issue #318 after recent edits, use that location but keep the exact ownership statement.

- [ ] **Step 3: Commit docs**

Run:

```bash
git add docs/architecture/storage-integration.md docs/architecture/plugin-composition-uplift-tracker.md
git commit -m "Document Iceberg writer ownership boundary"
```

## Task 5: Validate the Full Slice

**Files:**
- Verify all changed files from Tasks 1-4.

- [ ] **Step 1: Run narrow unit tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_writer.py plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py -q
```

Expected: PASS.

- [ ] **Step 2: Run package-adjacent tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py plugins/floe-orchestrator-dagster/tests/unit/test_loader.py -q
```

Expected: PASS. These tests catch broken lazy exports, resource wiring assumptions, and runtime loader regressions.

- [ ] **Step 3: Run static checks for touched Python packages**

Run:

```bash
uv run ruff check packages/floe-iceberg/src/floe_iceberg packages/floe-iceberg/tests/unit/test_writer.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py
uv run ruff format --check packages/floe-iceberg/src/floe_iceberg packages/floe-iceberg/tests/unit/test_writer.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py
```

Expected: PASS.

- [ ] **Step 4: Run repository standard check if narrow tests pass**

Run:

```bash
make check
```

Expected: PASS. If this fails outside the touched surface, capture the failing command and error summary before deciding whether it is in scope.

- [ ] **Step 5: Final status**

Run:

```bash
git status --short --branch
git log --oneline --decorate -5
```

Expected: branch has the design commit plus implementation commits, and the worktree is clean.

## Self-Review

- Spec coverage:
  - Typed writer contract owned outside Dagster: Task 1.
  - Direct PyIceberg table mutation moved behind contract: Task 2.
  - Current Dagster behavior preserved: Tasks 2 and 5.
  - Stale metadata and repair behavior preserved: Task 3.
  - Architecture docs updated: Task 4.
  - Validation evidence: Task 5.
- Completeness scan:
  - No unfilled task descriptions remain.
- Type consistency:
  - `IcebergTableWrite`, `IcebergWriterResult`, `DefaultIcebergTableWriter`, and `IcebergWriteMode` match across tests, implementation, exporter, and docs.
