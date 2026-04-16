# Spec Compliance Matrix: Runtime Loader

Gate: `gate-spec` | Generated: 2026-04-06

## Summary

| Result | Count |
|--------|-------|
| PASS   | 8     |
| WARN   | 0     |
| FAIL   | 0     |

**Overall: PASS**

---

## Compliance Matrix

| # | Criterion | Implementation | Test | Status |
|---|-----------|---------------|------|--------|
| AC-1 | `load_product_definitions()` returns valid Dagster Definitions with @dbt_assets, DbtCliResource, lineage, and conditional Iceberg resources | `loader.py:29-142` -- `load_product_definitions()` reads `compiled_artifacts.json`, creates `@dbt_assets` from `manifest.json` (L58-112), wires `DbtCliResource` via `ResourceDefinition` (L117-124), adds lineage resource (L125-126), conditionally adds iceberg resource (L131-137), returns `Definitions` (L139-142) | `test_loader.py:215` `test_returns_definitions_object`, `test_loader.py:225` `test_definitions_has_dbt_resource`, `test_loader.py:237` `test_definitions_has_lineage_resource`, `test_loader.py:249` `test_definitions_has_at_least_one_asset`, `test_loader.py:265` `test_definitions_has_iceberg_when_configured`, `test_loader.py:396` `test_fails_fast_when_artifacts_missing`, `test_loader.py:406` `test_fails_fast_when_artifacts_invalid`; `test_loader_integration.py:58` `test_returns_definitions_from_real_artifacts`, `test_loader_integration.py:66` `test_has_dbt_resource`, `test_loader_integration.py:75` `test_has_lineage_resource`, `test_loader_integration.py:84` `test_has_at_least_one_asset`; `test_runtime_loader_e2e.py:56` `test_dagster_discovers_code_location`, `test_runtime_loader_e2e.py:98` `test_dagster_discovers_assets` | PASS |
| AC-2 | No module-load-time connections -- importing/calling does not eagerly connect to Polaris, MinIO, or Marquez; resources are `ResourceDefinition` (deferred) | `loader.py:117-137` -- `DbtCliResource` wrapped in `ResourceDefinition(resource_fn=...)` (L117-124), iceberg resource wrapped in `ResourceDefinition(resource_fn=...)` (L133-137), lineage via `try_create_lineage_resource` returns `ResourceDefinition`-wrapped values (L125-126). No direct service construction at load time. | `test_loader.py:334` `test_no_connections_during_import`, `test_loader.py:367` `test_resources_are_deferred_not_eager`; `test_loader_integration.py:91` `test_resources_are_deferred`, `test_loader_integration.py:109` `test_no_exception_during_load` | PASS |
| AC-3 | Iceberg ResourceDefinition absent when unconfigured; exception propagated when factory raises (fail-fast) | `loader.py:131-137` -- Iceberg resource only added when `_plugins and _plugins.catalog` (L131). Factory call inside `ResourceDefinition` generator (L134) propagates exceptions from `try_create_iceberg_resources`. | `test_loader.py:279` `test_definitions_no_iceberg_when_unconfigured`, `test_loader.py:290` `test_iceberg_resource_propagates_exception` | PASS |
| AC-4 | Iceberg export extracted and parameterized -- accepts `context`, `product_name`, `project_dir`, `artifacts`; derives `duckdb_path` and `product_namespace` from `product_name`; does NOT re-read `compiled_artifacts.json` | `export/iceberg.py:28-33` -- Function signature `export_dbt_to_iceberg(context, product_name, project_dir, artifacts)`. L45: `safe_name = product_name.replace("-", "_")`. L46: `duckdb_path = f"/tmp/{safe_name}.duckdb"`. L76: `product_namespace = safe_name`. No `Path.read_text()` or `model_validate_json` calls on compiled_artifacts. | `test_export_iceberg.py:167` `test_export_derives_duckdb_path_from_product_name`, `test_export_iceberg.py:219` `test_export_derives_namespace_from_product_name`, `test_export_iceberg.py:285` `test_export_does_not_read_artifacts_from_disk`, `test_export_iceberg.py:338` `test_export_skips_when_duckdb_missing`, `test_export_iceberg.py:370` `test_export_skips_when_no_catalog_configured`, `test_export_iceberg.py:394` `test_export_creates_namespace`, `test_export_iceberg.py:431` `test_export_writes_to_iceberg`, `test_export_iceberg.py:498` `test_export_overwrites_existing_iceberg_table`, `test_export_iceberg.py:549` `test_export_skips_unsafe_identifiers`, `test_export_iceberg.py:611` `test_export_skips_empty_tables`, `test_export_iceberg.py:655` `test_export_uses_catalog_config_from_artifacts_not_from_disk`, `test_export_iceberg.py:714` `test_export_closes_duckdb_connection_on_success`, `test_export_iceberg.py:750` `test_export_closes_duckdb_connection_on_error`, `test_export_iceberg.py:787` `test_export_reads_duckdb_in_readonly_mode` | PASS |
| AC-5 | Lineage emission with error handling in @dbt_assets body -- emit_start before dbt, emit_fail on exception (re-raises), emit_complete on success, TraceCorrelationFacetBuilder | `loader.py:82-112` -- `TraceCorrelationFacetBuilder.from_otel_context()` called (L84-86), `lineage.emit_start()` with `run_facets` (L90), `dbt.cli(["build"]).stream()` in try/except (L96), `lineage.emit_fail()` on exception then re-raise (L98-102), `export_dbt_to_iceberg` after dbt (L105-106), `lineage.emit_complete()` on success (L110). | `test_loader.py:477` `test_dbt_assets_calls_emit_start_before_build`, `test_loader.py:519` `test_dbt_assets_calls_emit_complete_on_success`, `test_loader.py:539` `test_dbt_assets_calls_emit_fail_on_exception`, `test_loader.py:559` `test_dbt_assets_reraises_exceptions`, `test_loader.py:574` `test_dbt_assets_emit_complete_not_called_on_failure`, `test_loader.py:593` `test_dbt_assets_calls_iceberg_export_after_dbt`, `test_loader.py:613` `test_dbt_assets_iceberg_export_not_called_on_failure`, `test_loader.py:632` `test_dbt_assets_uses_trace_correlation_facet`, `test_loader.py:671` `test_dbt_assets_emit_start_uses_fallback_uuid_on_failure`, `test_loader.py:707` `test_dbt_assets_emit_fail_exception_does_not_swallow_dbt_error` | PASS |
| AC-6 | Demo definitions.py simplified to ~15 lines -- imports `load_product_definitions`, calls it, no inline logic | `demo/customer-360/definitions.py` (17 lines), `demo/financial-risk/definitions.py` (17 lines), `demo/iot-telemetry/definitions.py` (17 lines). All three: import `load_product_definitions` from `floe_orchestrator_dagster.loader`, define `PROJECT_DIR = Path(__file__).parent`, call `defs = load_product_definitions(name, PROJECT_DIR)`. None contain `_export_dbt_to_iceberg`, `_load_iceberg_resources`, `get_registry`, or `CompiledArtifacts`. | `test_runtime_loader_e2e.py:130` `test_thin_definitions_are_deployed` (reads all 3 demo files, asserts <=20 lines, asserts `load_product_definitions` present, asserts forbidden patterns absent); `test_runtime_loader_e2e.py:56` `test_dagster_discovers_code_location`; `test_runtime_loader_e2e.py:98` `test_dagster_discovers_assets` | PASS |
| AC-7 | `generate_entry_point_code()` emits thin loader pattern, not 187-line template | `plugin.py:1100-1117` -- `generate_entry_point_code()` generates thin shim delegating to `load_product_definitions()`. `lineage_enabled` and `iceberg_enabled` accepted for backward compat but have no effect on output. | `test_code_generator_iceberg.py:87` `test_imports_load_product_definitions`, `test_code_generator_iceberg.py:125` `test_defs_assignment_with_product_name`, `test_code_generator_iceberg.py:138` `test_project_dir_defined`, `test_code_generator_iceberg.py:226-285` `TestOldPatternsAbsent` (15 forbidden symbols x 4 flag combos = 60 parametrized tests), `test_code_generator_iceberg.py:295` `test_line_count_default_flags` (<=20 lines), `test_code_generator_iceberg.py:348-393` `TestFlagIndependence` (flag combos produce identical code), `test_code_generator_iceberg.py:500` `test_exact_functional_lines` (exact match of 5 functional lines) | PASS |
| AC-8 | Existing unit tests updated to assert new generated output format | `test_code_generator_iceberg.py` replaces old `test_code_generator_lineage.py` (confirmed: `.py` source removed, only stale `.pyc` remains). New tests assert thin loader pattern: `TestProductNameInterpolation` (AC-8 markers at L152-219), `TestGeneratedCodeStructure` (AC-8 markers at L432-464), `test_generated_file_is_valid_python` (L432), `test_defs_is_module_level_variable` (L446). All tests verify new format, not old 187-line template. | `test_code_generator_iceberg.py:152` `test_simple_product_name_interpolated`, `test_code_generator_iceberg.py:166` `test_product_name_with_underscores`, `test_code_generator_iceberg.py:178` `test_product_name_in_docstring`, `test_code_generator_iceberg.py:190` `test_product_name_with_dots`, `test_code_generator_iceberg.py:203` `test_different_product_names_produce_different_code`, `test_code_generator_iceberg.py:432` `test_generated_file_is_valid_python`, `test_code_generator_iceberg.py:446` `test_defs_is_module_level_variable` | PASS |

---

## File Inventory

### Implementation Files

| File | Path |
|------|------|
| loader.py | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py` |
| export/iceberg.py | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py` |
| plugin.py | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` |
| customer-360/definitions.py | `demo/customer-360/definitions.py` |
| financial-risk/definitions.py | `demo/financial-risk/definitions.py` |
| iot-telemetry/definitions.py | `demo/iot-telemetry/definitions.py` |

### Test Files

| File | Path | Tier |
|------|------|------|
| test_loader.py | `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py` | Unit |
| test_loader_integration.py | `plugins/floe-orchestrator-dagster/tests/integration/test_loader_integration.py` | Integration |
| test_export_iceberg.py | `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py` | Unit |
| test_code_generator_iceberg.py | `plugins/floe-orchestrator-dagster/tests/unit/test_code_generator_iceberg.py` | Unit |
| test_runtime_loader_e2e.py | `tests/e2e/test_runtime_loader_e2e.py` | E2E |

## Notes

- **AC-8**: The old `test_code_generator_lineage.py` source file has been removed (only a stale `.pyc` remains in `__pycache__`). Its functionality is fully superseded by `test_code_generator_iceberg.py`, which tests the new thin loader pattern and verifies old lineage symbols (e.g., `emit_start`, `emit_complete`, `try_create_lineage_resource`) are absent from generated code.
- All three demo `definitions.py` files are exactly 17 lines each, well within the <=20 line AC-6 threshold.
- AC-5 has 10 dedicated test functions covering: ordering (start before dbt), success path (complete), failure path (fail + re-raise), mutual exclusion (complete not called on failure), iceberg export after dbt, trace correlation facet, fallback UUID on emit_start failure, and emit_fail failure not swallowing dbt error.
