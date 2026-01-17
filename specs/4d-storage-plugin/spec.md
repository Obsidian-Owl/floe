# Feature Specification: Storage Plugin

**Epic**: 4D (Storage Plugin)
**Feature Branch**: `4d-storage-plugin`
**Created**: 2026-01-17
**Status**: Draft
**Input**: User description: "Implement StoragePlugin ABC and IcebergStoragePlugin reference implementation for table storage management, including table creation, schema evolution, snapshot management, and ACID transaction support via PyIceberg"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Platform Provides IcebergTableManager Utility (Priority: P0)

A platform developer needs an internal utility class that encapsulates PyIceberg table operations. The `IcebergTableManager` provides a clean API for table creation, schema evolution, snapshot management, and data writes that other floe components (like IOManagers and orchestration code) can use.

**Why this priority**: Without a centralized utility for Iceberg operations, each component would duplicate PyIceberg integration code. This utility provides consistency and testability.

**Independent Test**: Can be fully tested by using IcebergTableManager with a mock catalog, verifying all operations work correctly without external dependencies.

**Acceptance Scenarios**:

1. **Given** platform code needing Iceberg table operations, **When** they use IcebergTableManager, **Then** they get a consistent API that wraps PyIceberg complexity
2. **Given** a complete IcebergTableManager implementation, **When** used with a CatalogPlugin, **Then** it correctly delegates catalog operations while handling table-level logic
3. **Given** the IcebergTableManager class, **When** a developer reviews the interface, **Then** all method signatures include typed parameters and return values with documentation

---

### User Story 2 - Data Engineer Creates and Manages Iceberg Tables (Priority: P0)

A data engineer needs to create and manage Iceberg tables through the platform. They want to define table schemas, specify partitioning strategies, and have tables automatically registered with the catalog. The Iceberg format provides ACID guarantees and enables time travel queries.

**Why this priority**: Table creation is the fundamental capability of a storage plugin. Without it, there is no way to persist data in the platform.

**Independent Test**: Can be fully tested by creating an Iceberg table with a defined schema, inserting data, and verifying the table exists in the catalog with correct metadata.

**Acceptance Scenarios**:

1. **Given** a valid table configuration (schema, namespace, name), **When** the plugin creates the table, **Then** the table is registered in the catalog and accessible for writes
2. **Given** a table configuration with partitioning, **When** created, **Then** the partition spec is correctly applied to the table
3. **Given** an existing table name in the same namespace, **When** creation is attempted, **Then** the system handles the conflict appropriately (error or update based on configuration)
4. **Given** a table configuration with custom properties, **When** created, **Then** the properties are stored with the table metadata

---

### User Story 3 - Data Engineer Evolves Table Schema (Priority: P1)

A data engineer needs to safely evolve table schemas as business requirements change. They want to add new columns, widen column types, and rename columns without breaking existing consumers or requiring data migration.

**Why this priority**: Schema evolution is essential for long-lived data assets. Without it, any schema change requires recreating tables and migrating data.

**Independent Test**: Can be fully tested by creating a table, adding a nullable column, and verifying existing queries and new queries both work correctly.

**Acceptance Scenarios**:

1. **Given** an existing table, **When** a nullable column is added, **Then** the column appears in the schema and existing data has null values
2. **Given** an existing table with an int column, **When** the column type is widened to long, **Then** existing data is readable and new data can use the wider type
3. **Given** an existing table, **When** a column is renamed (metadata-only), **Then** the column name changes without data rewrite
4. **Given** a schema change that would break compatibility (e.g., dropping required column), **When** attempted, **Then** the system rejects the change with a clear error

---

### User Story 4 - Data Engineer Manages Snapshots and Time Travel (Priority: P1)

A data engineer needs to manage table snapshots for data versioning and recovery. They want to query historical data at specific points in time, roll back to previous states, and understand the history of table changes.

**Why this priority**: Snapshot management enables data versioning, audit trails, and recovery from errors. These are critical for production data systems.

**Independent Test**: Can be fully tested by creating a table, making multiple writes, and querying data at different snapshot points to verify time travel works.

**Acceptance Scenarios**:

1. **Given** a table with multiple writes, **When** snapshots are listed, **Then** all snapshots are returned with their timestamps and metadata
2. **Given** a table with history, **When** queried at a specific snapshot, **Then** the data as of that snapshot is returned
3. **Given** a corrupted or erroneous write, **When** rollback to previous snapshot is requested, **Then** the table state reverts to the selected snapshot
4. **Given** many old snapshots, **When** expire snapshots is called with retention policy, **Then** snapshots older than the retention period are removed

---

### User Story 5 - Data Engineer Writes Data with ACID Guarantees (Priority: P1)

A data engineer needs to write data to Iceberg tables with full ACID transaction support. They want append, overwrite, and upsert operations that are atomic and consistent, with proper isolation from concurrent readers.

**Why this priority**: ACID guarantees are fundamental for reliable data pipelines. Without them, concurrent operations can corrupt data or produce inconsistent results.

**Independent Test**: Can be fully tested by performing concurrent writes and reads, verifying that all operations are atomic and isolation is maintained.

**Acceptance Scenarios**:

1. **Given** data to append, **When** the append operation completes, **Then** the data is atomically visible in the table
2. **Given** data to overwrite a partition, **When** the overwrite completes, **Then** the old partition data is atomically replaced
3. **Given** concurrent writes to the same table, **When** both complete, **Then** both writes are visible and no data is lost
4. **Given** a write operation that fails mid-way, **When** the failure is detected, **Then** no partial data is visible in the table

---

### User Story 6 - Data Engineer Configures Partitioning Strategy (Priority: P2)

A data engineer needs to configure partitioning strategies for optimal query performance. They want to partition by date, category, or other dimensions to enable partition pruning during queries.

**Why this priority**: Proper partitioning is essential for performance at scale, but tables can function without it. It's an optimization rather than core functionality.

**Independent Test**: Can be fully tested by creating a partitioned table, writing data, and verifying that queries with partition filters only scan relevant partitions.

**Acceptance Scenarios**:

1. **Given** a table configuration with date partitioning, **When** created, **Then** the table uses the specified partition transform (year, month, day, hour)
2. **Given** a partitioned table, **When** data is written, **Then** data files are organized according to partition values
3. **Given** a query with partition filter, **When** executed, **Then** only relevant partitions are scanned (partition pruning)
4. **Given** partition evolution requirements, **When** partition spec is updated, **Then** new data uses the new spec while old data remains accessible

---

### User Story 7 - Platform Operator Monitors Storage Operations (Priority: P2)

A platform operator needs to monitor storage operations for performance and troubleshooting. They want metrics and traces for all storage operations to integrate with existing observability systems.

**Why this priority**: Observability enables proactive issue detection but is not required for basic storage functionality.

**Independent Test**: Can be fully tested by performing storage operations and verifying that appropriate metrics and traces are emitted.

**Acceptance Scenarios**:

1. **Given** a storage operation (create, write, read), **When** completed, **Then** an OpenTelemetry span is emitted with operation details
2. **Given** storage operations over time, **When** metrics are queried, **Then** operation counts, latencies, and error rates are available
3. **Given** a storage operation that fails, **When** the failure occurs, **Then** the error is captured in the span with diagnostic details

---

### User Story 8 - Data Engineer Integrates Storage with Dagster (Priority: P1)

A data engineer needs to use Iceberg tables as inputs and outputs for Dagster assets. They want an IOManager that handles Iceberg table operations automatically, enabling seamless integration between orchestration and storage.

**Why this priority**: Dagster integration enables the platform's core workflow of orchestrated data transformations. Without it, users must manually manage storage in their asset code.

**Independent Test**: Can be fully tested by creating a Dagster asset that outputs to an Iceberg table and another that reads from it, verifying the data flows correctly.

**Acceptance Scenarios**:

1. **Given** a Dagster asset with IcebergIOManager configured, **When** the asset materializes, **Then** output data is written to the configured Iceberg table
2. **Given** an asset that depends on an Iceberg table, **When** the dependent asset runs, **Then** it can read the upstream table data
3. **Given** IOManager configuration with write mode (append/overwrite), **When** asset materializes multiple times, **Then** the correct write behavior is applied
4. **Given** a partitioned Dagster asset, **When** a partition materializes, **Then** only that partition's data is written/replaced

---

### Edge Cases

- What happens when the catalog is unreachable during table creation?
- How does the system handle partial write failures during large transactions?
- What happens when schema evolution conflicts with existing data?
- How does the system behave when storage quota is exceeded?
- What happens when concurrent schema evolution operations conflict?
- How does the system handle corrupted metadata files?
- What happens when partition pruning cannot be applied due to predicate complexity?
- How does the system handle very large snapshots during expiration?

## Requirements *(mandatory)*

### Functional Requirements

**IcebergTableManager (Internal Utility Class)**

- **FR-001**: System MUST provide an `IcebergTableManager` class with `create_table(config)` method that creates an Iceberg table via the catalog
- **FR-002**: System MUST provide `evolve_schema(table, changes)` method in IcebergTableManager for safe schema modifications
- **FR-003**: System MUST provide `manage_snapshots(table)` method in IcebergTableManager for snapshot operations (create tags, branches, expire)
- **FR-004**: IcebergTableManager MUST accept a CatalogPlugin instance for catalog operations (dependency injection)
- **FR-005**: System MUST provide `write_data(table, data, mode, commit_strategy)` method supporting append, overwrite, and upsert modes with configurable commit strategy (fast_append default, merge_commit optional). Upsert uses PyIceberg's native `table.upsert()` with `join_cols` parameter for key matching.
- **FR-006**: System MUST provide `list_snapshots(table)` method returning snapshot metadata with timestamps
- **FR-007**: System MUST provide `rollback_to_snapshot(table, snapshot_id)` method for reverting table state

**PyIceberg Integration**

- **FR-008**: IcebergTableManager MUST use PyIceberg for all table operations
- **FR-009**: IcebergTableManager MUST integrate with CatalogPlugin's `connect()` method to obtain PyIceberg Catalog instance
- **FR-010**: IcebergTableManager MUST coordinate with the existing StoragePlugin ABC for FileIO configuration (S3, GCS, Azure, local)
- **FR-011**: System MUST support configurable storage locations via StoragePlugin's `get_pyiceberg_fileio()` method

**Table Creation**

- **FR-012**: System MUST support creating tables with Iceberg schema definitions
- **FR-013**: System MUST support partition specifications during table creation
- **FR-014**: System MUST support custom table properties during creation
- **FR-015**: System MUST validate table configuration before creation
- **FR-016**: System MUST raise `TableAlreadyExistsError` by default when table exists; MUST support `if_not_exists=True` parameter for idempotent behavior

**Schema Evolution**

- **FR-017**: System MUST support adding nullable columns to existing tables
- **FR-018**: System MUST support widening column types (e.g., int to long) where compatible
- **FR-019**: System MUST support renaming columns (metadata-only operation)
- **FR-020**: System MUST reject incompatible schema changes with clear error messages
- **FR-021**: System MUST track schema evolution history in table metadata

**Snapshot Management**

- **FR-022**: System MUST create snapshots atomically after successful writes
- **FR-023**: System MUST support querying table data at specific snapshots (time travel). **Note**: Time-travel queries use PyIceberg's native `table.scan(snapshot_id=snapshot_id)` API directly; IcebergTableManager does not wrap this operation.
- **FR-024**: System MUST support expiring old snapshots via `expire_snapshots(older_than_days=7)` with configurable retention (default 7 days, governance-aware)
- **FR-025**: System MUST preserve snapshot metadata including timestamps and operation type

**ACID Transactions**

- **FR-026**: System MUST ensure atomic visibility of writes (all-or-nothing)
- **FR-027**: System MUST provide isolation for concurrent readers during writes
- **FR-028**: System MUST support optimistic concurrency control for conflicting writes
- **FR-029**: System MUST retry transactions with configurable backoff on conflict

**Compaction (Execution Only)**

- **FR-030**: System MUST provide `compact_table(table, strategy)` method for rewriting data files to optimize performance
- **FR-031**: Compaction MUST support bin-packing strategy for combining small files
- **FR-032**: Compaction MUST NOT be auto-triggered; orchestrator is responsible for scheduling

**Partitioning**

- **FR-033**: System MUST support partition transforms (identity, year, month, day, hour, bucket, truncate)
- **FR-034**: System MUST organize data files according to partition values
- **FR-035**: System MUST support partition evolution (changing partition spec for new data)
- **FR-036**: System MUST enable partition pruning during queries with compatible predicates

**Dagster IOManager Integration**

- **FR-037**: System MUST provide an IcebergIOManager for Dagster asset integration
- **FR-038**: IOManager MUST support configurable write modes (append, overwrite)
- **FR-039**: IOManager MUST support reading input data from Iceberg tables
- **FR-040**: IOManager MUST support partitioned asset outputs

**Observability**

- **FR-041**: System MUST emit OpenTelemetry spans for all storage operations
- **FR-042**: OTel spans MUST include operation type, table name, duration, and status
- **FR-043**: System MUST emit structured logs for all storage operations
- **FR-044**: System MUST NOT include data values or sensitive information in logs or traces

**Configuration**

- **FR-045**: System MUST accept configuration through Pydantic models with validation
- **FR-046**: System MUST support credential configuration via environment variables or secret references
- **FR-047**: System MUST validate storage location accessibility at plugin initialization

### Key Entities

- **IcebergTableManager**: Internal utility class that wraps PyIceberg table operations. Provides methods for table creation, schema evolution, snapshot management, and data writes. Accepts CatalogPlugin and StoragePlugin via dependency injection. Not a plugin ABC itself.

- **StoragePlugin** (existing ABC): Object storage backend interface from floe-core. Provides `get_pyiceberg_fileio()` for S3/GCS/Azure FileIO, `get_warehouse_uri()` for storage locations. IcebergTableManager uses this for storage configuration.

- **TableConfig**: Configuration model for table creation. Includes table identifier (namespace + name), schema definition, partition spec, storage location, and custom properties.

- **SchemaChange**: Represents a schema modification operation. Types include AddColumn, WidenType, RenameColumn. Each change is validated for compatibility before application.

- **SnapshotInfo**: Metadata about a table snapshot. Includes snapshot ID, timestamp, operation type (append, overwrite, delete), summary statistics, and parent snapshot reference.

- **IcebergIOManager**: Dagster IOManager implementation for Iceberg tables. Handles asset outputs by writing to configured tables and asset inputs by reading from tables. Supports configurable write modes and partitioned assets.

- **WriteMode**: Enumeration of supported write operations (APPEND, OVERWRITE, UPSERT). Determines how new data is combined with existing table data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Platform developers can integrate IcebergTableManager into new components within 2 hours by following the class documentation
- **SC-002**: Data engineers can create an Iceberg table and perform first write within 10 minutes of configuration
- **SC-003**: Table creation, single-partition writes, and reads complete within 5 seconds under normal conditions
- **SC-004**: Schema evolution operations complete within 2 seconds for metadata-only changes
- **SC-005**: Time travel queries return correct historical data for any valid snapshot within 10 seconds
- **SC-006**: Concurrent writes to different partitions complete without conflict
- **SC-007**: 100% of storage operations produce OpenTelemetry spans suitable for observability integration
- **SC-008**: Dagster assets can read and write Iceberg tables with zero custom storage code in asset definitions

## Assumptions

- Catalog plugin (Epic 4C) is available for table registration operations
- PyIceberg library (>=0.5.0) provides the underlying Iceberg client operations
- Object storage (S3, GCS, Azure Blob, or local) is configured and accessible
- Plugin registry from Epic 1 is available for plugin discovery
- Iceberg REST catalog or Polaris is the catalog backend
- Storage operations are synchronous (async patterns may be added in future iterations)

## Clarifications

### Session 2026-01-17

- Q: Should the table operations abstraction be a new ABC that conflicts with the existing `StoragePlugin`, or should we use a different architecture? A: Option B - Rename to `IcebergTableManager` and position as an internal utility class (not a plugin ABC). The existing `StoragePlugin` ABC (FileIO for S3/GCS/Azure) remains unchanged. `IcebergTableManager` is an internal utility that wraps PyIceberg table operations, not a pluggable interface.
- Q: What should be the default behavior when `create_table()` is called for a table that already exists? A: Option A - Fail by default. Raise `TableAlreadyExistsError` by default; provide `if_not_exists=True` parameter for idempotent behavior. This matches PyIceberg's native behavior and follows "fail fast" principle.
- Q: Should IcebergTableManager provide a compaction execution method for the orchestrator to call? A: Option B - Provide execution method. IcebergTableManager provides `compact_table(strategy)` method; orchestrator (Dagster) decides when to call it. Scheduling/auto-trigger logic remains out of scope.
- Q: Should IcebergTableManager use PyIceberg's fast append default or expose commit strategy as a parameter? A: Option C with fast append default - Add `commit_strategy` parameter to `write_data()` letting caller choose, but default to fast append for fewer conflicts. Merge commit available for callers who need consolidated metadata.
- Q: What should be the default snapshot retention policy for `expire_snapshots()`? A: Option B - 7 days default with configurable override via `older_than_days` parameter. IcebergTableManager is governance-aware: it accepts configurable parameters that the Policy Enforcer (Epic 3A-3D) validates at enterprise, domain, or data product levels. IcebergTableManager does not enforce governance itself but respects whatever validated value is passed.
- Q: What are the semantics of UPSERT mode in write_data()? A: UPSERT uses PyIceberg's native `table.upsert()` with `join_cols` for key matching. Rows matching keys are updated; non-matching rows are inserted. Limitations: in-memory processing (partition large tables for >1GB datasets), basic predicates only (use dbt for complex MERGE INTO logic with conditional updates).

## Out of Scope

- Alternative storage formats beyond Iceberg (Iceberg is ENFORCED, not pluggable)
- Delta Lake or Apache Hudi implementations
- Direct S3/GCS/Azure Blob operations outside of Iceberg
- Streaming writes (batch only in this iteration)
- Compaction scheduling/auto-trigger (orchestrator decides when to call `compact_table()`; IcebergTableManager only provides execution)
- Data encryption at rest (handled by underlying storage provider)
- Cross-table transactions
- Table cloning or branching operations
