# Context: Runtime Loader Work Unit

baselineCommit: f1f1e25c00fe64845da9166b06c9b4654670bd8d

## Background

This work unit implements **Option B** from the E2E permanent fixes design pivot. It replaces the 187-line code-generated `definitions.py` files with a thin runtime loader that consolidates all boilerplate into a single module.

## Key Files

### Source (to create/modify)

- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py` — NEW runtime loader
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/__init__.py` — NEW package
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py` — NEW extracted export
- `demo/customer-360/definitions.py` — SIMPLIFY (187 → ~15 lines)
- `demo/iot-telemetry/definitions.py` — SIMPLIFY
- `demo/financial-risk/definitions.py` — SIMPLIFY
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` — MODIFY template section (lines 1100-1406)

### Reference (read, don't modify)

- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py` — `try_create_iceberg_resources()` (lines 151-198)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py` — `try_create_lineage_resource()` (lines 387-419), generator pattern (lines 377-382)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/ingestion.py` — `try_create_ingestion_resources()`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/semantic.py` — `try_create_semantic_resources()`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` — `create_definitions()` (lines 183-287, per-model @asset path — NOT what loader uses), `_asset_fn` (lines 537-578, lineage emission pattern to adopt)
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` — `CompiledArtifacts` schema

### Tests (to create/modify)

- `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py` — NEW
- `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py` — NEW
- `plugins/floe-orchestrator-dagster/tests/unit/test_code_generator_lineage.py` — MODIFY (existing tests assert old generated output)

## Critical Architecture Notes

### Two dbt-to-Dagster Paths

| Path | API | Use Case |
|---|---|---|
| `create_definitions()` → `@asset` | Per-model assets, `dbt.run_models(select=name)` | SDK/programmatic |
| Generated `definitions.py` → `@dbt_assets` | Single multi-asset, `dbt.cli(["build"]).stream()` | Dagster workspace |

The loader implements the `@dbt_assets` path. It does NOT delegate to `create_definitions()`.

### Resource Lifecycle Timing

- **Module import** → `load_product_definitions()` runs → reads `compiled_artifacts.json` → defines `@dbt_assets` function → creates `Definitions` with `ResourceDefinition` objects (no connections yet)
- **Dagster startup** → calls each `ResourceDefinition._resource_fn` → connections happen here

### Critic WARNs (address during implementation)

1. ResourceDefinition wrapper must raise (fail-fast), not yield `None`, if Iceberg creation fails
2. Add `try/except` around `yield from dbt.cli().stream()` + Iceberg export to enable `emit_fail`
3. Lineage transport init is partially eager (acceptable — NoOp default). Document in comments.
4. Pass parsed `CompiledArtifacts` object to export function instead of re-reading file (INFO simplification)

## Gotchas

- `DbtProject.__init__` runs at module scope (same as current generated code — not a regression)
- `floe_orchestrator_dagster` is already pip-installed in Docker image (Stage 2)
- Product namespace derived from product_name: `customer-360` → `customer_360`
- DuckDB path: `/tmp/{safe_name}.duckdb`
- Manifest path: `{project_dir}/target/manifest.json`
- Artifacts path: `{project_dir}/compiled_artifacts.json`
