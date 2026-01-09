# Epic 4D: Storage Plugin

## Summary

The StoragePlugin ABC defines the interface for table storage management. Built on Apache Iceberg via PyIceberg, it provides table creation, schema evolution, snapshot management, and ACID transaction support.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-04d-storage-plugin](https://linear.app/obsidianowl/project/floe-04d-storage-plugin-bb164b41d4c3)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-041 | StoragePlugin ABC definition | CRITICAL |
| REQ-042 | PyIceberg integration | CRITICAL |
| REQ-043 | Table creation | CRITICAL |
| REQ-044 | Schema evolution | HIGH |
| REQ-045 | Snapshot management | HIGH |
| REQ-046 | Time travel queries | MEDIUM |
| REQ-047 | Partition management | HIGH |
| REQ-048 | Compaction support | MEDIUM |
| REQ-049 | ACID transaction support | CRITICAL |
| REQ-050 | Storage metrics | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0001](../../../architecture/adr/0001-plugin-architecture.md) - Plugin architecture
- [ADR-0007](../../../architecture/adr/0007-storage-abstraction.md) - Storage abstraction (Iceberg)

### Interface Docs
- [plugin-interfaces.md](../../../architecture/plugin-system/plugin-interfaces.md) - Plugin interface definitions

### Contracts
- `StoragePlugin` - Storage management ABC
- `TableConfig` - Table configuration model
- `SnapshotInfo` - Snapshot metadata model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── plugin_interfaces.py         # StoragePlugin ABC (shared)
└── plugins/
    └── storage/
        └── __init__.py

packages/floe-iceberg/
├── src/floe_iceberg/
│   ├── __init__.py
│   ├── plugin.py                # IcebergStoragePlugin
│   ├── table.py                 # Table operations
│   ├── schema.py                # Schema evolution
│   ├── snapshot.py              # Snapshot management
│   ├── partition.py             # Partition management
│   └── io_manager.py            # Dagster IOManager
└── tests/
    ├── unit/
    └── integration/

# Test Fixtures (extends Epic 9C framework)
testing/fixtures/storage.py          # StoragePlugin test fixtures
testing/tests/unit/test_storage_fixtures.py  # Fixture tests
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 4C | Uses catalog for table registration |
| Blocked By | Epic 9C | Uses testing framework for fixtures |
| Blocks | Epic 3C | Data contracts reference Iceberg schemas |
| Blocks | Epic 5A | dbt writes to Iceberg tables |
| Blocks | Epic 6B | OpenLineage captures storage events |

---

## User Stories (for SpecKit)

### US1: StoragePlugin ABC (P0)
**As a** plugin developer
**I want** a clear ABC for storage plugins
**So that** I can implement alternative storage formats if needed

**Acceptance Criteria**:
- [ ] `StoragePlugin.create_table(config)` defined
- [ ] `StoragePlugin.evolve_schema(table, changes)` defined
- [ ] `StoragePlugin.create_snapshot(table)` defined
- [ ] Configuration via Pydantic models

### US2: PyIceberg Implementation (P0)
**As a** data engineer
**I want** Iceberg tables managed via PyIceberg
**So that** I get ACID guarantees and time travel

**Acceptance Criteria**:
- [ ] `IcebergStoragePlugin` implements ABC
- [ ] Table creation with schema
- [ ] Append, overwrite, upsert operations
- [ ] Catalog integration (Polaris)

### US3: Schema Evolution (P1)
**As a** data engineer
**I want** to evolve table schemas safely
**So that** I can add columns without breaking consumers

**Acceptance Criteria**:
- [ ] Add nullable column
- [ ] Widen column type (e.g., int to long)
- [ ] Rename column (metadata only)
- [ ] Schema evolution history tracked

### US4: Dagster IOManager (P1)
**As a** data engineer
**I want** an IOManager for Iceberg tables
**So that** Dagster assets write to Iceberg automatically

**Acceptance Criteria**:
- [ ] `IcebergIOManager` handles asset outputs
- [ ] Configurable write mode (append/overwrite)
- [ ] Partition writing support
- [ ] Transaction coordination

---

## Technical Notes

### Key Decisions
- Iceberg is ENFORCED (not pluggable at storage format level)
- PyIceberg is the only supported client
- Storage plugin delegates to catalog for table registration
- Compaction is triggered by orchestrator, not storage plugin

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PyIceberg version compatibility | MEDIUM | MEDIUM | Pin version, test upgrades |
| Large table performance | MEDIUM | HIGH | Partitioning, compaction |
| Transaction conflicts | LOW | HIGH | Optimistic concurrency, retries |

### Test Strategy
- **Unit**: `packages/floe-iceberg/tests/unit/test_plugin.py`
- **Integration**: `packages/floe-iceberg/tests/integration/test_iceberg_operations.py`
- **Contract**: `tests/contract/test_storage_plugin_abc.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/01-plugin-architecture/`
- `docs/architecture/plugin-system/`
- `packages/floe-iceberg/`

### Related Existing Code
- PluginRegistry from Epic 1
- CatalogPlugin from Epic 4C

### External Dependencies
- `pyiceberg>=0.5.0`
- Object storage (S3, MinIO, GCS)
