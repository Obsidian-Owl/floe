---
name: compilation
description: "Skill for the Compilation area of floe. 56 symbols across 20 files."
---

# Compilation

56 symbols | 20 files | Cohesion: 71%

## When to Use

- Working with code in `packages/`
- Understanding how generate_dbt_profile, resolve_plugins, resolve_transform_compute work
- Modifying compilation-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/compilation/resolver.py` | _to_plugin_ref, resolve_plugins, resolve_transform_compute, get_compute_plugin, validate_compute_credentials (+1) |
| `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | PluginRef, ResolvedPlugins, ResolvedModel, ResolvedTransforms, EnforcementResultSummary |
| `packages/floe-core/src/floe_core/compilation/dbt_test_mapper.py` | infer_dimension, map_dbt_test_to_check, get_check_signature, deduplicate_checks, merge_model_checks |
| `packages/floe-core/src/floe_core/compilation/quality_inheritance.py` | merge_gate_tiers, _tier_differs, resolve_quality_inheritance, _merge_config_level, _check_gate_tier_locks |
| `packages/floe-core/src/floe_core/lineage/emitter.py` | emit_start, emit_complete, emit_fail, close |
| `packages/floe-core/src/floe_core/compilation/stages.py` | _discover_plugins_for_audit, _resolve_governance, _build_lineage_config, compile_pipeline |
| `packages/floe-core/src/floe_core/compilation/loader.py` | _load_yaml, _validate_model, load_floe_spec, load_manifest |
| `packages/floe-core/src/floe_core/compilation/quality_compiler.py` | raise_if_quality_violations, validate_quality_gates_for_models, _validate_single_model |
| `packages/floe-core/src/floe_core/compilation/dbt_profiles.py` | get_compute_plugin, _build_compute_config, generate_dbt_profiles |
| `packages/floe-core/src/floe_core/compute_config.py` | ComputeConfig, DuckDBConfig |

## Entry Points

Start here when exploring this area:

- **`generate_dbt_profile`** (Function) — `packages/floe-core/src/floe_core/plugins/compute.py:144`
- **`resolve_plugins`** (Function) — `packages/floe-core/src/floe_core/compilation/resolver.py:60`
- **`resolve_transform_compute`** (Function) — `packages/floe-core/src/floe_core/compilation/resolver.py:149`
- **`get_compute_plugin`** (Function) — `packages/floe-core/src/floe_core/compilation/resolver.py:221`
- **`validate_compute_credentials`** (Function) — `packages/floe-core/src/floe_core/compilation/resolver.py:255`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ComputeConfig` | Class | `packages/floe-core/src/floe_core/compute_config.py` | 156 |
| `DuckDBConfig` | Class | `packages/floe-core/src/floe_core/compute_config.py` | 223 |
| `PluginRef` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 127 |
| `ResolvedPlugins` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 172 |
| `ResolvedModel` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 232 |
| `ResolvedTransforms` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 297 |
| `CompilationError` | Class | `packages/floe-core/src/floe_core/compilation/errors.py` | 27 |
| `CompilationException` | Class | `packages/floe-core/src/floe_core/compilation/errors.py` | 130 |
| `SinkWhitelistError` | Class | `packages/floe-core/src/floe_core/schemas/plugins.py` | 88 |
| `EnforcementResultSummary` | Class | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | 463 |
| `QualityCheck` | Class | `packages/floe-core/src/floe_core/schemas/quality_score.py` | 28 |
| `QualityOverrideError` | Class | `packages/floe-core/src/floe_core/quality_errors.py` | 245 |
| `QualityGates` | Class | `packages/floe-core/src/floe_core/schemas/quality_config.py` | 210 |
| `QualityCoverageError` | Class | `packages/floe-core/src/floe_core/quality_errors.py` | 110 |
| `QualityConfig` | Class | `packages/floe-core/src/floe_core/schemas/quality_config.py` | 267 |
| `generate_dbt_profile` | Function | `packages/floe-core/src/floe_core/plugins/compute.py` | 144 |
| `resolve_plugins` | Function | `packages/floe-core/src/floe_core/compilation/resolver.py` | 60 |
| `resolve_transform_compute` | Function | `packages/floe-core/src/floe_core/compilation/resolver.py` | 149 |
| `get_compute_plugin` | Function | `packages/floe-core/src/floe_core/compilation/resolver.py` | 221 |
| `validate_compute_credentials` | Function | `packages/floe-core/src/floe_core/compilation/resolver.py` | 255 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Compile_command → Get_tracer` | cross_community | 5 |
| `Compile_command → CompilationException` | cross_community | 5 |
| `Compile_command → CompilationError` | cross_community | 5 |
| `Compile_command → Errors` | cross_community | 5 |
| `Generate_command → CompilationException` | cross_community | 4 |
| `Generate_command → CompilationError` | cross_community | 4 |
| `Generate_command → Errors` | cross_community | 4 |
| `Generate_command → CompilationException` | cross_community | 4 |
| `Generate_command → CompilationError` | cross_community | 4 |
| `Generate_command → Errors` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Floe_core | 8 calls |
| Schemas | 4 calls |
| Oci | 2 calls |
| Floe_catalog_polaris | 2 calls |
| Lineage | 1 calls |
| Enforcement | 1 calls |
| Base_classes | 1 calls |
| Validation | 1 calls |

## How to Explore

1. `gitnexus_context({name: "generate_dbt_profile"})` — see callers and callees
2. `gitnexus_query({query: "compilation"})` — find related execution flows
3. Read key files listed above for implementation details
