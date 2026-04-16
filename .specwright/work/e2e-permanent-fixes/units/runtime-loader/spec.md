# Spec: Runtime Loader (Option B)

## Acceptance Criteria

### AC-1: `load_product_definitions()` returns valid Dagster Definitions

`loader.py` MUST export a `load_product_definitions(product_name, project_dir)` function that returns a `dagster.Definitions` object containing:
- A single `@dbt_assets` asset created from `project_dir/target/manifest.json`
- A `DbtCliResource` keyed as `"dbt"`
- Lineage resource (real or NoOp) keyed as `"lineage"`
- Iceberg resources if catalog+storage configured in `compiled_artifacts.json`

**How to verify:** Call `load_product_definitions("test-product", tmp_dir)` with a valid `compiled_artifacts.json` and `target/manifest.json`. Assert returned object is `Definitions` with expected resources and assets.

### AC-2: No module-load-time connections

When `definitions.py` is imported by Python (simulating Dagster module discovery), NO network connections to Polaris, MinIO, or Marquez MUST occur. Resource connections MUST be deferred to `ResourceDefinition` generator invocation.

**How to verify:** Import `definitions` module with Polaris/MinIO unreachable. Assert no `ConnectionError` or `TimeoutError` raised during import. Assert `ResourceDefinition` objects are present in `Definitions.resources` (not eagerly resolved values).

### AC-3: Iceberg ResourceDefinition fails fast on creation error

When `try_create_iceberg_resources()` returns `{}` (no catalog/storage configured), the Iceberg resource MUST be absent from `Definitions.resources`. When the function raises an exception, the `ResourceDefinition` generator MUST propagate the exception (fail-fast), NOT yield `None`. **The factory functions themselves are NOT modified in this unit** — their error semantics are addressed in unit 6 (loud-failures).

**How to verify:** Test with `plugins.catalog = None` → assert `"iceberg"` not in resources. Test with catalog configured but plugin load raises → assert exception propagates through ResourceDefinition.

### AC-4: Iceberg export extracted and parameterized

`export.iceberg.export_dbt_to_iceberg()` MUST accept `context`, `product_name`, `project_dir`, and `artifacts` (parsed CompiledArtifacts object). It MUST derive `duckdb_path` from `product_name` and `product_namespace` from `product_name`. It MUST NOT re-read `compiled_artifacts.json` from disk.

**How to verify:** Call with mocked context and valid artifacts object. Assert DuckDB path is `/tmp/{safe_name}.duckdb`. Assert namespace is `{safe_name}`. Assert no file I/O on `compiled_artifacts.json`.

### AC-5: Lineage emission with error handling in @dbt_assets body

The `@dbt_assets` function MUST:
- Call `lineage.emit_start()` before `dbt.cli(["build"])` with `TraceCorrelationFacetBuilder`
- Wrap `yield from dbt.cli().stream()` and Iceberg export in `try/except`
- Call `lineage.emit_fail()` on exception before re-raising
- Call `lineage.emit_complete()` on success

**How to verify:** Assert `emit_start` is called before dbt execution. Assert `emit_fail` is called when dbt raises. Assert `emit_complete` is called on success. Assert exceptions from dbt are re-raised (not swallowed).

### AC-6: Demo definitions.py simplified to ~15 lines

Each demo product's `definitions.py` MUST import `load_product_definitions` from `floe_orchestrator_dagster.loader` and call it with the product name and project directory. No inline Iceberg export logic, no inline resource wiring, no `get_registry` or `CompiledArtifacts` imports.

**How to verify:** Each `definitions.py` is ≤20 lines. Contains `from floe_orchestrator_dagster.loader import load_product_definitions`. Contains `defs = load_product_definitions(...)`. Does NOT contain `_export_dbt_to_iceberg`, `_load_iceberg_resources`, `get_registry`, or `CompiledArtifacts`.

### AC-7: `generate_entry_point_code()` emits thin loader pattern

When called, the method MUST generate the simplified definitions.py (AC-6 pattern), not the 187-line template. The generated file MUST be functionally equivalent to the manually simplified files.

**How to verify:** Call `generate_entry_point_code(product_name="test-product", output_dir=tmp)`. Read generated file. Assert it matches the thin loader pattern. Assert it does NOT contain `_export_dbt_to_iceberg` or `_load_iceberg_resources`.

### AC-8: Existing unit tests updated

`test_code_generator_lineage.py` MUST be updated to assert the new generated output format. Tests that assert presence of `emit_start`/`emit_complete` in generated code MUST be updated since lineage is now in the loader, not the generated file.

**How to verify:** All tests in `test_code_generator_lineage.py` pass. Tests assert the thin loader pattern.
