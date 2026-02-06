# Research: IcebergTableManager (Epic 4D)

**Created**: 2026-01-17
**Status**: Complete
**Clarifications Resolved**: 5/5

## Prior Decisions (from Agent-Memory)

Agent-memory returned prior context about storage plugin architecture:
1. **File I/O Compatibility**: StoragePlugin provides FileIO implementations for Iceberg
2. **Existing StoragePlugin ABC**: Already defined in floe-core, focused on object storage (S3/GCS/Azure), NOT table operations

This validates our clarification decision: IcebergTableManager is an **internal utility class**, not a plugin ABC.

## Executive Summary

IcebergTableManager will be an internal utility class in `packages/floe-iceberg/` that wraps PyIceberg table operations. It accepts CatalogPlugin and StoragePlugin via dependency injection, NOT as a plugin ABC itself.

**Key Architecture Decisions:**
- IcebergTableManager is NOT a plugin (Iceberg is ENFORCED, not pluggable)
- Uses CatalogPlugin.connect() to get PyIceberg Catalog
- Uses StoragePlugin.get_pyiceberg_fileio() for storage operations
- Provides IcebergIOManager for Dagster asset integration

## 1. Existing Plugin Architecture

### StoragePlugin ABC (packages/floe-core/src/floe_core/plugins/storage.py)

**Purpose**: Object storage backend providing FileIO for Iceberg data access

**Key Methods:**
| Method | Returns | Purpose |
|--------|---------|---------|
| `get_pyiceberg_fileio()` | `FileIO` | PyIceberg FileIO for reading/writing data |
| `get_warehouse_uri(namespace)` | `str` | Storage URI for namespace (e.g., "s3://bucket/warehouse/bronze") |
| `get_dbt_profile_config()` | `dict` | Storage config for dbt profiles.yml |
| `get_dagster_io_manager_config()` | `dict` | Config for Dagster IOManager |
| `get_helm_values_override()` | `dict` | Helm values for self-hosted storage (MinIO) |

**FileIO Protocol:**
```python
@runtime_checkable
class FileIO(Protocol):
    def new_input(self, location: str) -> Any: ...
    def new_output(self, location: str) -> Any: ...
    def delete(self, location: str) -> None: ...
```

### CatalogPlugin ABC (packages/floe-core/src/floe_core/plugins/catalog.py)

**Purpose**: Iceberg catalog management (Polaris, Glue, Hive)

**Key Methods:**
| Method | Returns | Purpose |
|--------|---------|---------|
| `connect(config)` | `Catalog` | Get PyIceberg Catalog instance |
| `create_namespace(namespace, properties)` | `None` | Create namespace in catalog |
| `list_namespaces(parent)` | `list[str]` | List namespaces |
| `delete_namespace(namespace)` | `None` | Delete namespace |
| `create_table(identifier, schema, ...)` | `None` | Create table (basic) |
| `list_tables(namespace)` | `list[str]` | List tables in namespace |
| `drop_table(identifier, purge)` | `None` | Drop table |
| `vend_credentials(table_path, operations)` | `dict` | Short-lived credential vending |

**Catalog Protocol:**
```python
@runtime_checkable
class Catalog(Protocol):
    def list_namespaces(self) -> list[tuple[str, ...]]: ...
    def list_tables(self, namespace: str) -> list[str]: ...
    def load_table(self, identifier: str) -> Any: ...
```

### PluginMetadata Base (packages/floe-core/src/floe_core/plugin_metadata.py)

**Required Properties:**
- `name: str` - Plugin identifier
- `version: str` - Semver (X.Y.Z)
- `floe_api_version: str` - API version (X.Y)

**Optional Properties:**
- `description: str`
- `dependencies: list[str]` - Plugin names this depends on

**Lifecycle Methods:**
- `startup() -> None` - Called on activation (30s timeout)
- `shutdown() -> None` - Called on shutdown
- `health_check() -> HealthStatus` - Health status (5s timeout)
- `get_config_schema() -> type[BaseModel] | None` - Pydantic config schema

### Plugin Registry (packages/floe-core/src/floe_core/plugin_registry.py)

**Plugin Types Available:**
- `floe.computes`, `floe.orchestrators`, `floe.catalogs`, `floe.storage`
- `floe.telemetry_backends`, `floe.lineage_backends`, `floe.dbt`
- `floe.semantic_layers`, `floe.ingestion`, `floe.secrets`, `floe.identity`, `floe.quality`

**Note**: There is NO `floe.table_managers` type - IcebergTableManager is NOT registered as a plugin.

## 2. PyIceberg Best Practices

### Table Creation

**Schema Definition with Field IDs (CRITICAL for evolution):**
```python
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, LongType, TimestampType

schema = Schema(
    NestedField(field_id=1, name="id", field_type=LongType(), required=True),
    NestedField(field_id=2, name="name", field_type=StringType(), required=False),
    NestedField(field_id=3, name="created_at", field_type=TimestampType(), required=True),
)
```

**Partition Specs:**
```python
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import DayTransform, MonthTransform, BucketTransform

partition_spec = PartitionSpec(
    PartitionField(source_id=3, field_id=1000, transform=DayTransform(), name="created_day")
)
```

**Table Properties (Production Recommended):**
| Property | Value | Purpose |
|----------|-------|---------|
| `write.target-file-size-bytes` | `134217728` (128MB) | Optimal file size |
| `write.parquet.row-group-size-bytes` | `134217728` | Row group sizing |
| `history.expire.max-snapshot-age-ms` | `604800000` (7 days) | Snapshot retention |
| `history.expire.min-snapshots-to-keep` | `10` | Minimum versions |
| `commit.manifest-merge.enabled` | `true` | Reduce manifest sprawl |

### Write Operations

**Commit Strategies:**
- **Fast Append** (default): Creates new manifest files, minimal latency
- **Merge Commit**: Consolidates manifests, better for high-frequency writes

```python
# Fast append (default) - best for most use cases
table.append(data)

# With snapshot properties for lineage
table.append(data, snapshot_properties={
    "pipeline_run_id": "run-12345",
    "source_system": "crm",
})

# Overwrite with filter
table.overwrite(data, overwrite_filter=EqualTo('status', 'pending'))

# Dynamic partition overwrite
table.dynamic_partition_overwrite(data)
```

### Concurrent Write Handling

**PyIceberg does NOT auto-retry on CommitFailedException.** Manual retry required:

```python
from pyiceberg.exceptions import CommitFailedException

def append_with_retry(table, data, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            table.refresh()  # Get latest metadata
            table.append(data)
            return
        except CommitFailedException:
            if attempt == max_retries - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))  # Exponential backoff
```

### Schema Evolution

**Safe Operations (No Data Rewrite):**
- Add nullable column
- Rename column (metadata-only)
- Widen type: int → long, float → double
- Make column optional

```python
with table.update_schema() as update:
    update.add_column("phone", StringType(), doc="Customer phone")
    update.rename_column("name", "full_name")
    update.update_column("id", field_type=LongType())  # Widen int → long
```

**Incompatible Changes (Require Flag):**
```python
with table.update_schema(allow_incompatible_changes=True) as update:
    update.delete_column("deprecated_field")
    update.update_column("email", required=True)  # Make required
```

### Snapshot Management

**List and Query:**
```python
# Snapshot metadata
snapshots_df = table.inspect.snapshots()

# Time travel
historical_scan = table.scan(snapshot_id=805611270568163028)
df = historical_scan.to_arrow()

# Current snapshot
current = table.current_snapshot()
```

**Tags and Branches:**
```python
# Immutable tag (for releases)
table.manage_snapshots().create_tag(
    snapshot_id=current.snapshot_id,
    tag_name="v1.0.0",
    max_ref_age_ms=31536000000,  # 1 year
).commit()

# Mutable branch (for testing)
table.manage_snapshots().create_branch(
    snapshot_id=current.snapshot_id,
    branch_name="feature-testing",
).commit()
```

**Expiration (Governance-Aware):**
```python
# IcebergTableManager accepts retention from Policy Enforcer
table.maintenance.expire_snapshots().older_than(
    datetime.now() - timedelta(days=retention_days)  # Default: 7
).commit()
```

**Rollback:**
```python
table.manage_snapshots().rollback_to_snapshot(target_snapshot_id).commit()
```

### Error Handling

**Key Exception Types:**
| Exception | When | Handling |
|-----------|------|----------|
| `CommitFailedException` | Concurrent write conflict | Retry with backoff |
| `TableAlreadyExistsError` | Table exists on create | Return existing or raise |
| `NoSuchTableError` | Table not found | Clear error message |
| `NoSuchNamespaceError` | Namespace missing | Create or raise |
| `ValidationError` | Schema/data invalid | Don't retry |
| `ServiceUnavailableError` | Catalog unreachable | Retry or fail gracefully |

## 3. Design Decisions

### Decision 1: IcebergTableManager as Internal Utility (Not Plugin)

**Decision**: IcebergTableManager is an internal utility class in `packages/floe-iceberg/`

**Rationale**:
- Iceberg is ENFORCED (ADR-0005), not pluggable
- StoragePlugin already exists for FileIO (S3/GCS/Azure)
- CatalogPlugin already handles catalog operations (Polaris/Glue)
- No need for abstraction when there's only one implementation

**Alternative Rejected**: New plugin ABC for table operations
- Would duplicate CatalogPlugin functionality
- Would add unnecessary abstraction layer

### Decision 2: Dependency Injection Pattern

**Decision**: IcebergTableManager accepts CatalogPlugin and StoragePlugin in constructor

**Rationale**:
- Follows SOLID principles (Dependency Inversion)
- Enables easy testing with mock plugins
- Clear separation of concerns

**Interface:**
```python
class IcebergTableManager:
    def __init__(
        self,
        catalog_plugin: CatalogPlugin,
        storage_plugin: StoragePlugin,
        config: IcebergTableManagerConfig | None = None,
    ) -> None:
        ...
```

### Decision 3: Create Table - Fail by Default

**Decision**: `create_table()` raises `TableAlreadyExistsError` by default; `if_not_exists=True` for idempotent behavior

**Rationale**:
- Matches PyIceberg native behavior
- Follows "fail fast" principle
- Explicit idempotency when needed

### Decision 4: Fast Append Default with Configurable Strategy

**Decision**: `write_data()` defaults to fast append; `commit_strategy` parameter allows merge commit

**Rationale**:
- Fast append has fewer conflicts (good default)
- Merge commit available for high-frequency scenarios
- Caller controls based on workload

```python
def write_data(
    self,
    table: Table,
    data: pa.Table,
    mode: WriteMode,
    commit_strategy: CommitStrategy = CommitStrategy.FAST_APPEND,
) -> SnapshotInfo:
    ...
```

### Decision 5: 7-Day Snapshot Retention (Governance-Aware)

**Decision**: Default 7 days, configurable via `older_than_days` parameter

**Rationale**:
- 7 days balances storage cost vs recovery window
- Policy Enforcer (Epic 3A-3D) validates retention at enterprise/domain/product levels
- IcebergTableManager accepts validated parameters, doesn't enforce governance itself

### Decision 6: Compaction Execution, Not Scheduling

**Decision**: IcebergTableManager provides `compact_table(strategy)` method; orchestrator decides when to call

**Rationale**:
- Compaction scheduling is orchestration concern (Dagster)
- IcebergTableManager is stateless utility
- Separation of execution from scheduling

## 4. Package Structure

```
packages/floe-iceberg/
├── src/
│   └── floe_iceberg/
│       ├── __init__.py
│       ├── manager.py          # IcebergTableManager
│       ├── io_manager.py       # IcebergIOManager for Dagster
│       ├── models.py           # Pydantic models (TableConfig, SchemaChange, etc.)
│       ├── errors.py           # Custom exceptions
│       ├── compaction.py       # Compaction strategies
│       └── telemetry.py        # OTel instrumentation
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_manager.py
│   │   ├── test_io_manager.py
│   │   └── test_models.py
│   └── integration/
│       ├── test_manager_integration.py
│       └── test_io_manager_integration.py
└── pyproject.toml
```

## 5. Integration Points

### With CatalogPlugin (Epic 4C)

```python
# IcebergTableManager gets PyIceberg Catalog from CatalogPlugin
catalog_plugin = plugin_registry.get(PluginType.CATALOG, "polaris")
pyiceberg_catalog = catalog_plugin.connect(config)

# Use catalog for table operations
table = pyiceberg_catalog.load_table("bronze.customers")
```

### With StoragePlugin (Future)

```python
# IcebergTableManager gets FileIO from StoragePlugin
storage_plugin = plugin_registry.get(PluginType.STORAGE, "s3")
fileio = storage_plugin.get_pyiceberg_fileio()
warehouse_uri = storage_plugin.get_warehouse_uri("bronze")
```

### With Dagster (via IcebergIOManager)

```python
from floe_iceberg.io_manager import IcebergIOManager

@asset(io_manager_key="iceberg_io_manager")
def customers_silver():
    return transformed_data  # Written to Iceberg table

defs = Definitions(
    assets=[customers_silver],
    resources={
        "iceberg_io_manager": IcebergIOManager(
            table_manager=table_manager,
            default_write_mode=WriteMode.APPEND,
        ),
    },
)
```

### With Policy Enforcer (Epic 3A-3D)

```python
# Policy Enforcer validates retention at governance level
validated_retention = policy_enforcer.get_snapshot_retention(
    enterprise_policy=enterprise_config,
    domain_policy=domain_config,
    product_policy=product_config,
)

# IcebergTableManager uses validated value
table_manager.expire_snapshots(table, older_than_days=validated_retention)
```

## 6. Open Questions (Resolved)

| Question | Resolution | Source |
|----------|------------|--------|
| Should IcebergTableManager be a plugin ABC? | No, internal utility class | Clarification Q1 |
| Default behavior for existing table? | Fail with `if_not_exists=True` option | Clarification Q2 |
| Include compaction methods? | Yes, execution only (no scheduling) | Clarification Q3 |
| Commit strategy exposure? | Configurable with fast append default | Clarification Q4 |
| Snapshot retention default? | 7 days, governance-aware | Clarification Q5 |

## 7. Dependencies

### Required
- `pyiceberg>=0.10.0,<0.11.0` - Core Iceberg operations (0.10.0+ required for native table.upsert())
- `pydantic>=2.0` - Configuration models
- `structlog` - Structured logging
- `opentelemetry-api>=1.20.0` - Tracing
- `pyarrow` - Data format

### Development
- `pytest>=7.0` - Testing
- `pytest-cov` - Coverage
- `mypy` - Type checking

## 9. Post-Research Findings (Integration Analysis)

These findings emerged during integration analysis after the initial research was complete. They document gaps between the spec documents and the actual codebase.

### Finding 1: create_table() Overlap Between CatalogPlugin and IcebergTableManager

**Issue**: Both CatalogPlugin and IcebergTableManager expose a `create_table()` method, which could confuse implementors.

**Resolution**: Clear boundary documented in spec.md. CatalogPlugin.create_table() = basic catalog registration (thin wrapper). IcebergTableManager.create_table() = rich table lifecycle operation that DELEGATES to PyIceberg Catalog (obtained via CatalogPlugin.connect()), adding config validation, retry logic, partition specs, default properties, OTel tracing, and typed exceptions. CatalogPlugin manages catalog lifecycle; IcebergTableManager manages table lifecycle.

### Finding 2: IOManager Location Mismatch in Plan Docs

**Issue**: plan.md listed `io_manager.py` inside `packages/floe-iceberg/`, but it actually lives in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/io_manager.py`.

**Resolution**: Plan docs corrected. Per component ownership (Principle I), Dagster-specific integration code belongs in the orchestrator plugin, not in the iceberg package. The `PrivateAttr` pattern is used to bypass Dagster's ConfigurableIOManager serialization requirements for the live IcebergTableManager connection.

### Finding 3: Missing Wiring in DagsterOrchestratorPlugin

**Issue**: `DagsterOrchestratorPlugin.create_definitions()` does not yet wire IcebergIOManager into the Dagster resource dict. This means even after IcebergIOManager is implemented, it won't be discoverable by Dagster assets without manual wiring.

**Resolution**: Phase 14 (Wiring & Integration) added to tasks.md with tasks T108-T118. A reusable `create_iceberg_resources()` factory function will be created to extract catalog/storage config from CompiledArtifacts, load plugins via PluginRegistry, and return the resource dict.

### Finding 4: No Concrete StoragePlugin Exists

**Issue**: The `floe.storage` entry point group has zero registrations. IcebergTableManager requires a StoragePlugin for FileIO configuration, but no implementation (e.g., floe-storage-s3) has been built.

**Resolution**: A MockStoragePlugin test fixture (T114) is created for testing. The wiring code will gracefully degrade when no StoragePlugin is configured (T117 negative test). A concrete implementation is out of scope for Epic 4D but documented as a dependency.

### Finding 5: DriftDetector Circular Dependency

**Issue**: DriftDetector in `packages/floe-iceberg/` imports from `floe_core`, which may transitively reference iceberg types, creating a soft circular dependency.

**Resolution**: Mitigated via lazy imports (documented in T119). A formal `DriftDetectorProtocol` defined in floe-core (T121, future task) will eliminate the lazy import pattern entirely.

## 8. References

- ADR-0005: Iceberg Table Format (ENFORCED)
- ADR-0036: Storage Plugin Interface
- PyIceberg Documentation: https://py.iceberg.apache.org/
- Apache Iceberg Spec: https://iceberg.apache.org/spec/
