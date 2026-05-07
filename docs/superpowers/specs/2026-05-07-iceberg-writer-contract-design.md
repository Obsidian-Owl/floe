# Iceberg Writer Contract Design

Status: Ready for implementation planning
Date: 2026-05-07
Author: Codex

## Summary

Floe should extract direct Iceberg table mutation from the Dagster exporter into
an orchestrator-neutral writer contract owned by `floe-iceberg`.

Dagster should coordinate runtime execution and collect dbt outputs. It should
not own the semantics for creating namespaces, loading tables, creating tables,
choosing append versus overwrite, or repairing stale Iceberg table metadata.
Those semantics belong in `floe-iceberg` because Apache Iceberg is enforced
platform behavior, while orchestration is pluggable.

The first implementation should be narrow: move the existing direct write path
behind a typed contract without redesigning storage, catalog, dbt, or Dagster
resource wiring. Future orchestrators such as Airflow should be able to produce
the same writer inputs and reuse the same Iceberg mutation behavior.

## Context

Issue #318 was deferred from the storage composition PR because
`floe-orchestrator-dagster` currently writes Iceberg tables directly from
`plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`.

That exporter currently owns:

- DuckDB profile path resolution from `CompiledArtifacts.dbt_profiles`.
- DuckDB table discovery and conversion to Arrow tables.
- Catalog and storage plugin lookup/configuration.
- PyIceberg catalog connection setup.
- Namespace creation.
- Table load, create, append, and overwrite.
- Stale metadata and repairable overwrite-state recovery.

The first two responsibilities are runtime-export concerns. The remaining
responsibilities are Iceberg writer concerns and should move out of the
orchestrator plugin.

## Goals

- Close issue #318 with a typed writer contract owned outside Dagster.
- Keep the writer contract orchestrator-neutral from day one.
- Preserve current Dagster export behavior.
- Keep storage and catalog plugins free of Dagster concepts.
- Keep `CompiledArtifacts` secret-free.
- Prefer a narrow adapter boundary over a broad storage or catalog rewrite.
- Add focused regression tests proving Dagster delegates writes through the
  writer contract.
- Update architecture docs where the public boundary changes.

## Non-Goals

- Do not introduce a new pluggable table format abstraction. Iceberg remains
  enforced.
- Do not move DuckDB table discovery into `floe-iceberg` in this slice.
- Do not change `CompiledArtifacts` schema unless implementation discovers an
  unavoidable typed binding gap.
- Do not add Airflow support in this branch.
- Do not change catalog or storage plugin capability models beyond what the
  existing writer path already needs.
- Do not add raw credentials to artifacts, logs, tests, or generated values.

## Alternatives Considered

### Recommended: `floe-iceberg` Owned Writer Contract

`floe-iceberg` owns public writer types and the implementation. Dagster resolves
runtime output tables and calls the writer.

This best matches Floe's composability model:

- Iceberg is enforced, so common table mutation semantics belong in the Iceberg
  package.
- Orchestrators are pluggable, so they should not each implement Iceberg write
  policy.
- Catalog and storage plugins remain peer dependencies injected into the writer,
  not consumers of orchestrator-specific concepts.

### Wider: `floe-core` Protocol With `floe-iceberg` Implementation

`floe-core` could define an abstract writer protocol and `floe-iceberg` could
implement it.

This is useful only if packages must depend on a writer interface without
depending on `floe-iceberg`. Today that adds indirection without improving the
current boundary because Iceberg is the enforced table format and the neutral
runtime package already exists.

### Narrower: Dagster-Local Protocol

Dagster could define a local protocol and inject a writer object internally.

This would reduce test friction but would not really close the architecture
debt. It would still make the first durable writer boundary an orchestrator
concern and would invite future orchestrators to copy the same logic.

## Architecture Decision

Create a public `floe_iceberg.writer` module that owns the typed writer
contract and default implementation.

The writer accepts resolved catalog/storage plugin instances plus an
`IcebergTableManagerConfig` or governance-derived equivalent. It writes Arrow
tables to fully qualified Iceberg identifiers and returns a secret-free result.

The Dagster exporter keeps responsibility for:

- Deciding whether export is enabled from `CompiledArtifacts.plugins`.
- Resolving the DuckDB database path from compiled dbt profiles.
- Opening DuckDB read-only.
- Listing exportable DuckDB tables.
- Validating SQL identifiers before querying DuckDB.
- Converting each non-empty DuckDB table to a PyArrow table.
- Logging orchestration-level progress.

The `floe-iceberg` writer owns responsibility for:

- Validating that a catalog is write-capable.
- Applying catalog connection config supplied by storage/catalog runtime
  bindings.
- Creating namespaces idempotently.
- Loading existing tables for overwrite.
- Creating missing tables from Arrow schema.
- Appending new tables and overwriting existing tables.
- Handling stale metadata and repairable overwrite-state recovery according to
  `IcebergTableManagerConfig.stale_table_recovery_mode`.
- Refreshing catalog handles after repair when required.

## Proposed API Shape

Use these public names unless implementation exposes a concrete conflict with
existing package conventions:

```python
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Protocol

from floe_iceberg.models import IcebergTableManagerConfig


IcebergWriteMode = Literal["append", "overwrite"]


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
    """Result of writing one or more Iceberg tables."""

    tables_written: int
    table_names: tuple[str, ...]
```

The default implementation can expose a batch method if that keeps the Dagster
call site simple:

```python
class DefaultIcebergTableWriter:
    def __init__(
        self,
        *,
        catalog_plugin: Any,
        storage_plugin: Any,
        catalog_connection_config: dict[str, Any] | None = None,
        config: IcebergTableManagerConfig | None = None,
    ) -> None:
        """Create an Iceberg writer from resolved catalog and storage plugins."""

    def write_tables(
        self,
        namespace: str,
        writes: Iterable[IcebergTableWrite],
    ) -> IcebergWriterResult:
        ...
```

The writer should keep PyIceberg types behind `Any` or local protocols where
upstream packages lack stable typing. The Floe-facing contract remains typed
through dataclasses, protocols, and explicit result models.

Dagster should construct the default writer only after the configured DuckDB
output file exists. That preserves the current fast failure mode where missing
dbt output does not force optional DuckDB/PyIceberg write dependencies to load.

## Data Flow

```text
CompiledArtifacts
  -> Dagster export path checks catalog/storage/plugin refs
  -> Dagster resolves DuckDB profile path
  -> Dagster extracts non-empty DuckDB tables as Arrow tables
  -> Dagster builds IcebergTableWrite requests
  -> floe-iceberg writer mutates Iceberg tables through catalog/storage plugins
  -> Dagster logs IcebergWriterResult
```

This keeps runtime extraction separate from table mutation. A future Airflow
runtime can replace only the orchestration and extraction layer while reusing
the same writer.

## Error Handling

The first implementation should preserve current behavior:

- Missing catalog or storage plugin means Dagster skips export.
- Missing or invalid DuckDB profile path fails before writer creation.
- Missing DuckDB output file fails before optional PyIceberg/DuckDB write work.
- Catalogs without required write methods fail loudly with a clear runtime
  error.
- Existing namespaces are treated as success.
- Missing tables are created and appended.
- Existing tables are overwritten.
- Stale metadata follows configured governance-derived recovery mode.
- Repair mode drops only the stale catalog registration with `purge=False`,
  reconnects the catalog, recreates the table, and appends data.

The writer must not log raw plugin config or credential material.

## Test Plan

Add focused tests before or alongside implementation:

- `packages/floe-iceberg/tests/unit/test_writer.py`
  - Creates namespaces idempotently.
  - Creates missing tables and appends data.
  - Overwrites existing tables.
  - Uses endpoint-preserving table load when the catalog plugin exposes it.
  - Repairs stale metadata in repair mode.
  - Raises structured stale metadata errors in strict mode.
  - Rejects non-write-capable catalogs with a clear message.

- `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`
  - Proves Dagster delegates table mutation to the writer.
  - Proves Dagster still derives namespace and table identifiers correctly.
  - Proves Dagster still skips unsafe identifiers and empty tables.
  - Proves Dagster does not call writer when DuckDB output is missing.

Existing export tests should be preserved where they still describe the
orchestrator behavior. Tests that assert direct catalog mutation from Dagster
should be rewritten to assert writer calls instead.

## Documentation Updates

Update `docs/architecture/storage-integration.md` or a nearby architecture
interface document to state:

- Iceberg table mutation is owned by `floe-iceberg`.
- Orchestrator plugins coordinate runtime execution and call the writer.
- Catalog and storage plugins provide capabilities, connections, and FileIO
  inputs without depending on orchestrator-specific APIs.
- `CompiledArtifacts` remains a secret-free handoff; runtime credentials flow
  through resolved bindings and plugin-owned connection logic.

Update `docs/architecture/plugin-composition-uplift-tracker.md` to mark issue
#318 as the Iceberg runtime writer boundary follow-up for the orchestrator path.

## Implementation Notes

- Start with an extraction, not a rewrite.
- Keep the public writer module small and stable.
- Move helper protocols such as the write-capable catalog and endpoint-preserving
  loader from the Dagster exporter into `floe-iceberg`.
- Reuse existing stale metadata helpers from `floe_iceberg.errors`.
- Reuse `IcebergTableManagerConfig.from_governance()` for current governance
  behavior.
- Keep DuckDB imports in the Dagster exporter because DuckDB is the current
  export source, not an Iceberg writer concern.

## Acceptance Criteria Mapping

- Typed writer contract owned outside Dagster:
  `floe_iceberg.writer` defines the public writer contract and result types.
- Direct PyIceberg table creation/write logic moved behind contract:
  Dagster no longer calls catalog `create_namespace`, `load_table`, or
  `create_table` directly for export writes.
- Current Dagster export behavior preserved:
  Existing behavior remains covered by focused unit tests.
- Ownership boundaries documented:
  Architecture docs explain orchestrator, Iceberg, catalog, and storage
  responsibilities.
