---
name: lineage
description: "Skill for the Lineage area of floe. 43 symbols across 9 files."
---

# Lineage

43 symbols | 9 files | Cohesion: 89%

## When to Use

- Working with code in `packages/`
- Understanding how from_columns, from_snapshot, from_dbt_columns work
- Modifying lineage-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/lineage/transport.py` | _create_ssl_context, _apply_insecure_settings, _sanitized_url, emit, _ensure_consumer (+9) |
| `packages/floe-core/src/floe_core/lineage/catalog_integration.py` | resolve_namespace, resolve_dataset, enrich_with_snapshot, NamespaceStrategy, SimpleNamespaceStrategy (+3) |
| `packages/floe-core/src/floe_core/lineage/events.py` | to_openlineage_event, start_run, complete_run, fail_run, EventBuilder |
| `packages/floe-core/src/floe_core/lineage/types.py` | LineageDataset, LineageRun, LineageJob, LineageEvent |
| `packages/floe-core/src/floe_core/lineage/emitter.py` | SyncLineageEmitter, create_sync_emitter, LineageEmitter, create_emitter |
| `packages/floe-core/src/floe_core/lineage/facets.py` | from_columns, from_snapshot, from_dbt_columns |
| `packages/floe-core/src/floe_core/lineage/extractors/dbt.py` | extract_test, _create_dataset_from_node |
| `packages/floe-core/src/floe_core/lineage/protocols.py` | close, close_async |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py` | _enrich_outputs_with_column_lineage |

## Entry Points

Start here when exploring this area:

- **`from_columns`** (Function) — `packages/floe-core/src/floe_core/lineage/facets.py:36`
- **`from_snapshot`** (Function) — `packages/floe-core/src/floe_core/lineage/facets.py:319`
- **`from_dbt_columns`** (Function) — `packages/floe-core/src/floe_core/lineage/facets.py:374`
- **`resolve_namespace`** (Function) — `packages/floe-core/src/floe_core/lineage/catalog_integration.py:306`
- **`resolve_dataset`** (Function) — `packages/floe-core/src/floe_core/lineage/catalog_integration.py:324`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `LineageDataset` | Class | `packages/floe-core/src/floe_core/lineage/types.py` | 50 |
| `LineageRun` | Class | `packages/floe-core/src/floe_core/lineage/types.py` | 80 |
| `LineageJob` | Class | `packages/floe-core/src/floe_core/lineage/types.py` | 103 |
| `LineageEvent` | Class | `packages/floe-core/src/floe_core/lineage/types.py` | 133 |
| `SyncNoOpTransport` | Class | `packages/floe-core/src/floe_core/lineage/transport.py` | 381 |
| `SyncConsoleLineageTransport` | Class | `packages/floe-core/src/floe_core/lineage/transport.py` | 399 |
| `SyncHttpLineageTransport` | Class | `packages/floe-core/src/floe_core/lineage/transport.py` | 431 |
| `EventBuilder` | Class | `packages/floe-core/src/floe_core/lineage/events.py` | 27 |
| `SyncLineageEmitter` | Class | `packages/floe-core/src/floe_core/lineage/emitter.py` | 194 |
| `NoOpLineageTransport` | Class | `packages/floe-core/src/floe_core/lineage/transport.py` | 74 |
| `ConsoleLineageTransport` | Class | `packages/floe-core/src/floe_core/lineage/transport.py` | 95 |
| `HttpLineageTransport` | Class | `packages/floe-core/src/floe_core/lineage/transport.py` | 186 |
| `LineageEmitter` | Class | `packages/floe-core/src/floe_core/lineage/emitter.py` | 28 |
| `NamespaceStrategy` | Class | `packages/floe-core/src/floe_core/lineage/catalog_integration.py` | 26 |
| `SimpleNamespaceStrategy` | Class | `packages/floe-core/src/floe_core/lineage/catalog_integration.py` | 47 |
| `CentralizedNamespaceStrategy` | Class | `packages/floe-core/src/floe_core/lineage/catalog_integration.py` | 79 |
| `DataMeshNamespaceStrategy` | Class | `packages/floe-core/src/floe_core/lineage/catalog_integration.py` | 116 |
| `from_columns` | Function | `packages/floe-core/src/floe_core/lineage/facets.py` | 36 |
| `from_snapshot` | Function | `packages/floe-core/src/floe_core/lineage/facets.py` | 319 |
| `from_dbt_columns` | Function | `packages/floe-core/src/floe_core/lineage/facets.py` | 374 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Extract_dbt_model_lineage → Items` | cross_community | 5 |
| `Extract_dbt_model_lineage → From_columns` | cross_community | 4 |
| `Extract_dbt_model_lineage → LineageDataset` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Schemas | 2 calls |

## How to Explore

1. `gitnexus_context({name: "from_columns"})` — see callers and callees
2. `gitnexus_query({query: "lineage"})` — find related execution flows
3. Read key files listed above for implementation details
