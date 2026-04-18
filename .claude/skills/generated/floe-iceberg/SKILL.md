---
name: floe-iceberg
description: "Skill for the Floe_iceberg area of floe. 84 symbols across 11 files."
---

# Floe_iceberg

84 symbols | 11 files | Cohesion: 89%

## When to Use

- Working with code in `packages/`
- Understanding how create_table, load_table, table_exists work
- Modifying floe_iceberg-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-iceberg/src/floe_iceberg/errors.py` | IcebergError, ValidationError, TableError, TableAlreadyExistsError, NoSuchTableError (+19) |
| `packages/floe-iceberg/src/floe_iceberg/manager.py` | _validate_namespace_exists, _validate_identifier, __init__, _validate_catalog_plugin, _validate_storage_plugin (+6) |
| `packages/floe-iceberg/src/floe_iceberg/models.py` | FieldType, IcebergTableManagerConfig, from_pyiceberg_snapshot, CompactionStrategy, SchemaField (+6) |
| `packages/floe-iceberg/src/floe_iceberg/_schema_manager.py` | _get_pyiceberg_type_mapping, evolve_schema, _apply_real_schema_changes, _validate_schema_evolution, _is_incompatible_change (+5) |
| `packages/floe-iceberg/src/floe_iceberg/compaction.py` | CompactionResult, _analyze_files_for_compaction, execute, execute, execute (+5) |
| `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py` | create_table, load_table, table_exists, drop_table, _validate_namespace_exists (+3) |
| `packages/floe-iceberg/src/floe_iceberg/_snapshot_manager.py` | _IcebergSnapshotManager, list_snapshots, rollback_to_snapshot |
| `packages/floe-iceberg/src/floe_iceberg/_compaction_manager.py` | _IcebergCompactionManager, compact_table |
| `packages/floe-iceberg/src/floe_iceberg/drift_detector.py` | compare_schemas, _is_type_compatible |
| `packages/floe-core/src/floe_core/schemas/data_contract.py` | TypeMismatch, SchemaComparisonResult |

## Entry Points

Start here when exploring this area:

- **`create_table`** (Function) — `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py:107`
- **`load_table`** (Function) — `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py:187`
- **`table_exists`** (Function) — `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py:220`
- **`drop_table`** (Function) — `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py:260`
- **`evolve_schema`** (Function) — `packages/floe-iceberg/src/floe_iceberg/_schema_manager.py:129`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `IcebergError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 36 |
| `ValidationError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 77 |
| `TableError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 124 |
| `TableAlreadyExistsError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 151 |
| `NoSuchTableError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 167 |
| `NoSuchNamespaceError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 183 |
| `WriteError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 290 |
| `CommitConflictError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 332 |
| `FieldType` | Class | `packages/floe-iceberg/src/floe_iceberg/models.py` | 92 |
| `SchemaEvolutionError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 224 |
| `IncompatibleSchemaChangeError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 267 |
| `IcebergTableManagerConfig` | Class | `packages/floe-iceberg/src/floe_iceberg/models.py` | 1128 |
| `SnapshotError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 375 |
| `SnapshotNotFoundError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 408 |
| `RollbackError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 425 |
| `CompactionError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 441 |
| `CompactionAnalysisError` | Class | `packages/floe-iceberg/src/floe_iceberg/errors.py` | 479 |
| `CompactionResult` | Class | `packages/floe-iceberg/src/floe_iceberg/compaction.py` | 51 |
| `CompactionStrategy` | Class | `packages/floe-iceberg/src/floe_iceberg/models.py` | 1050 |
| `SchemaField` | Class | `packages/floe-iceberg/src/floe_iceberg/models.py` | 281 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Create_table → ValidationError` | intra_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Oci | 7 calls |
| Schemas | 1 calls |
| Floe_catalog_polaris | 1 calls |

## How to Explore

1. `gitnexus_context({name: "create_table"})` — see callers and callees
2. `gitnexus_query({query: "floe_iceberg"})` — find related execution flows
3. Read key files listed above for implementation details
