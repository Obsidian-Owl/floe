---
name: floe-core
description: "Skill for the Floe_core area of floe. 87 symbols across 29 files."
---

# Floe_core

87 symbols | 29 files | Cohesion: 75%

## When to Use

- Working with code in `packages/`
- Understanding how create_iceberg_io_manager, from_governance, discover_all work
- Modifying floe_core-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/plugin_registry.py` | PluginRegistry, discover_all, get, list, configure (+7) |
| `packages/floe-core/src/floe_core/compute_registry.py` | ComputeRegistry, __init__, _validate_approved_plugins, get, get_default (+3) |
| `packages/floe-core/src/floe_core/compute_errors.py` | ComputeError, ComputeConnectionError, ComputeTimeoutError, ComputeConfigurationError, __init__ (+3) |
| `packages/floe-core/src/floe_core/compiler.py` | EnvironmentParityError, resolve_transform_compute, resolve_transforms_compute, check_environment_parity, validate_environment_parity (+2) |
| `packages/floe-core/src/floe_core/plugin_errors.py` | PluginConfigurationError, PluginError, PluginNotFoundError, PluginIncompatibleError, DuplicatePluginError |
| `packages/floe-core/src/floe_core/quality_errors.py` | QualityError, QualityProviderNotFoundError, QualityCheckFailedError, QualityColumnReferenceError, QualityMissingTestsError |
| `packages/floe-core/src/floe_core/observability.py` | get_meter, _get_validation_duration_histogram, _get_validation_errors_counter, record_validation_duration, record_validation_error |
| `packages/floe-core/src/floe_core/plugins/loader.py` | get, _load_plugin, register, list_loaded_names |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | _create_semantic_resources, _create_ingestion_resources, get_resource_requirements |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/io_manager.py` | IcebergIOManagerConfig, IcebergIOManager, create_iceberg_io_manager |

## Entry Points

Start here when exploring this area:

- **`create_iceberg_io_manager`** (Function) — `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/io_manager.py:637`
- **`from_governance`** (Function) — `packages/floe-iceberg/src/floe_iceberg/models.py:1216`
- **`discover_all`** (Function) — `packages/floe-core/src/floe_core/plugin_registry.py:160`
- **`get`** (Function) — `packages/floe-core/src/floe_core/plugin_registry.py:191`
- **`list`** (Function) — `packages/floe-core/src/floe_core/plugin_registry.py:209`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `IcebergIOManagerConfig` | Class | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/io_manager.py` | 57 |
| `IcebergIOManager` | Class | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/io_manager.py` | 112 |
| `IcebergTableManager` | Class | `packages/floe-iceberg/src/floe_iceberg/manager.py` | 66 |
| `PluginRegistry` | Class | `packages/floe-core/src/floe_core/plugin_registry.py` | 117 |
| `PluginConfigurationError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 121 |
| `ComputeRegistry` | Class | `packages/floe-core/src/floe_core/compute_registry.py` | 45 |
| `ComputeError` | Class | `packages/floe-core/src/floe_core/compute_errors.py` | 30 |
| `ComputeConnectionError` | Class | `packages/floe-core/src/floe_core/compute_errors.py` | 62 |
| `ComputeTimeoutError` | Class | `packages/floe-core/src/floe_core/compute_errors.py` | 100 |
| `ComputeConfigurationError` | Class | `packages/floe-core/src/floe_core/compute_errors.py` | 138 |
| `PluginError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 45 |
| `PluginNotFoundError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 61 |
| `PluginIncompatibleError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 87 |
| `DuplicatePluginError` | Class | `packages/floe-core/src/floe_core/plugin_errors.py` | 189 |
| `QualityError` | Class | `packages/floe-core/src/floe_core/quality_errors.py` | 28 |
| `QualityProviderNotFoundError` | Class | `packages/floe-core/src/floe_core/quality_errors.py` | 43 |
| `QualityCheckFailedError` | Class | `packages/floe-core/src/floe_core/quality_errors.py` | 72 |
| `QualityColumnReferenceError` | Class | `packages/floe-core/src/floe_core/quality_errors.py` | 176 |
| `EnvironmentParityError` | Class | `packages/floe-core/src/floe_core/compiler.py` | 49 |
| `QualityMissingTestsError` | Class | `packages/floe-core/src/floe_core/quality_errors.py` | 144 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Generate_dbt_profiles → PluginRegistry` | cross_community | 4 |
| `Generate_dbt_profiles → Discover_all` | cross_community | 4 |
| `Generate_dbt_profiles → Info` | cross_community | 4 |
| `Delete_namespace → PluginConfigurationError` | cross_community | 3 |
| `Vend_credentials → PluginConfigurationError` | cross_community | 3 |
| `Connect → PluginConfigurationError` | cross_community | 3 |
| `Health_check → PluginConfigurationError` | cross_community | 3 |
| `Wrapper → Keys` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Floe_catalog_polaris | 3 calls |
| Schemas | 3 calls |
| Network | 2 calls |
| Base_classes | 1 calls |
| Oci | 1 calls |
| Lineage | 1 calls |
| Validation | 1 calls |
| Compilation | 1 calls |

## How to Explore

1. `gitnexus_context({name: "create_iceberg_io_manager"})` — see callers and callees
2. `gitnexus_query({query: "floe_core"})` — find related execution flows
3. Read key files listed above for implementation details
