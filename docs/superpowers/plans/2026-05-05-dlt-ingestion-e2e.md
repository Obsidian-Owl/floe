# dlt Ingestion E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Superseded cleanup note (2026-05-08): this historical plan predated the dlt
> ingestion API cleanup. Do not use this document to reintroduce
> ingestion-owned catalog config, destination config APIs, or direct native
> Iceberg shortcut paths. Current implementation uses deployment runtime
> bindings plus dlt's filesystem destination with Iceberg table format/catalog
> settings.

**Goal:** Make dlt ingestion a real compiled, orchestrated, and E2E-tested path for Customer 360 and common landed-file ingestion formats.

**Architecture:** `manifest.yaml` stays the platform engineer contract for plugin selection and environment wiring; `floe.yaml` gains a small environment-agnostic ingestion block owned by data engineers. Compilation merges those sources into `CompiledArtifacts.plugins.ingestion.config`, Dagster constructs runnable filesystem dlt sources from that JSON-safe contract, and E2E tests prove the path against MinIO and Polaris.

**Tech Stack:** Python 3.10+, Pydantic v2, floe-core compilation, floe-orchestrator-dagster, floe-ingestion-dlt, dlt filesystem/Iceberg, MinIO, Polaris, PyIceberg, pyarrow, pytest.

---

### Task 1: Add Product-Level Ingestion Schema

**Files:**
- Modify: `packages/floe-core/src/floe_core/schemas/floe_spec.py`
- Add: `packages/floe-core/tests/unit/schemas/test_floe_spec_ingestion.py`

- [ ] **Step 1: Write schema tests for the data engineer contract**

Create `packages/floe-core/tests/unit/schemas/test_floe_spec_ingestion.py` with these test functions:
- `test_floe_spec_accepts_filesystem_ingestion_sources`
- `test_floe_spec_rejects_duplicate_ingestion_source_names`
- `test_floe_spec_rejects_environment_specific_ingestion_fields`
- `test_floe_spec_rejects_merge_without_primary_key`

Use this accepted shape:

```yaml
ingestion:
  sources:
    - name: raw-customers
      sourceType: filesystem
      format: csv
      path: ./data/customers.csv
      destinationTable: bronze.raw_customers
      writeMode: replace
      schemaContract: evolve
```

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_floe_spec_ingestion.py -q
```

Expected: tests fail because `FloeSpec` has no `ingestion` field.

- [ ] **Step 2: Implement typed ingestion models in `floe_spec.py`**

Add models before `PlatformRef`:

```python
class IngestionSourceSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    name: Annotated[str, Field(min_length=1, max_length=100)]
    source_type: Annotated[
        Literal["filesystem"],
        Field(alias="sourceType", description="Declarative source type"),
    ]
    format: Literal["csv", "jsonl", "parquet"]
    path: Annotated[str, Field(min_length=1)]
    destination_table: Annotated[
        str,
        Field(alias="destinationTable", min_length=1),
    ]
    write_mode: Annotated[
        Literal["append", "replace", "merge"],
        Field(default="append", alias="writeMode"),
    ]
    schema_contract: Annotated[
        Literal["evolve", "freeze"],
        Field(default="evolve", alias="schemaContract"),
    ]
    cursor_field: Annotated[str | None, Field(default=None, alias="cursorField")]
    primary_key: Annotated[str | list[str] | None, Field(default=None, alias="primaryKey")]
```

Add `ProductIngestionSpec` with `sources: list[IngestionSourceSpec]` and a unique-name validator. Add `ingestion: ProductIngestionSpec | None = Field(default=None, description="Optional ingestion sources")` to `FloeSpec`.

Keep environment-specific fields out of the schema. Do not add keys such as `endpoint`, `access_key`, `secret_key`, `token`, `database`, or `credentials` to the product contract.

- [ ] **Step 3: Add source-level validators**

Implement validators for:
- `name`: alphanumeric, underscore, and hyphen only.
- `destination_table`: exactly `namespace.table` with non-empty parts.
- `write_mode == "merge"` requires `primary_key`.
- `path`: non-empty local relative path or object-store URI beginning with `s3://`, `gs://`, or `az://`; no embedded credentials.

- [ ] **Step 4: Verify focused schema tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_floe_spec_ingestion.py -q
```

Expected: all new schema tests pass.

### Task 2: Merge Product Sources Into Compiled Artifacts

**Files:**
- Modify: `packages/floe-core/src/floe_core/compilation/resolver.py`
- Modify: `packages/floe-core/src/floe_core/compilation/stages.py`
- Add: `packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py`
- Modify: `tests/contract/test_core_to_ingestion_contract.py`

- [ ] **Step 1: Write failing resolver and contract tests**

Add tests proving:
- A manifest-selected `plugins.ingestion.type: dlt` receives product `ingestion.sources`.
- Compilation fails when `floe.yaml` declares ingestion sources but the manifest does not select an ingestion plugin.
- Existing manifest-level ingestion config keys such as `retry_config` are preserved, while stale ingestion-owned catalog config is rejected.
- Serialized `CompiledArtifacts.plugins.ingestion.config.sources` is plain JSON and uses snake_case keys expected by `DltIngestionConfig`.

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py tests/contract/test_core_to_ingestion_contract.py -q
```

Expected: new tests fail because product ingestion is not resolved.

- [ ] **Step 2: Implement `resolve_ingestion_config()`**

In `resolver.py`, add a function with this behavior:

```python
def resolve_ingestion_config(spec: FloeSpec, plugins: ResolvedPlugins) -> ResolvedPlugins:
    if spec.ingestion is None:
        return plugins
    if plugins.ingestion is None:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code="E202",
                message="Product declares ingestion sources but no ingestion plugin is selected",
                suggestion="Add plugins.ingestion to the platform manifest",
                context={"product": spec.metadata.name},
            )
        )
    existing_config = dict(plugins.ingestion.config or {})
    existing_config["sources"] = [
        source.model_dump(by_alias=False, exclude_none=True)
        for source in spec.ingestion.sources
    ]
    return plugins.model_copy(
        update={
            "ingestion": plugins.ingestion.model_copy(update={"config": existing_config})
        }
    )
```

Do not mutate `ResolvedPlugins` or `PluginRef`; both are frozen Pydantic models.

- [ ] **Step 3: Wire the resolver into Stage 3**

In `compile_pipeline()`, import `resolve_ingestion_config()` and call it immediately after `resolve_plugins()`:

```python
plugins = resolve_plugins(resolved_manifest)
plugins = resolve_ingestion_config(spec, plugins)
```

Add span/log attributes for `compile.ingestion_source_count` when ingestion is present.

- [ ] **Step 4: Verify resolver and contract tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py tests/contract/test_core_to_ingestion_contract.py -q
```

Expected: all tests pass.

### Task 3: Add JSON-Safe Filesystem Source Construction

**Files:**
- Add: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/__init__.py`
- Add: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/filesystem_sources.py`
- Add: `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py`

- [ ] **Step 1: Write failing source-construction tests**

Test that `build_filesystem_source()`:
- Imports `dlt.sources.filesystem` lazily.
- Builds a runnable dlt source/resource for `csv`, `jsonl`, and `parquet`.
- Normalizes local paths relative to a supplied `project_dir`.
- Leaves object-store paths such as `s3://floe-test/landing/customers.csv` unchanged.
- Rejects unsupported source types and formats with source names in the error.
- Rejects missing paths and unsafe destination table names before dlt runs.

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py -q
```

Expected: tests fail because the module does not exist.

- [ ] **Step 2: Implement the source-construction module**

Create a small adapter that accepts a source config dict and returns an executable dlt source/resource. Keep all platform secrets out of the product config; credentials come from the runtime environment and dlt/PyIceberg configuration.

Implement this public function:

```python
def build_filesystem_source(
    source_config: Mapping[str, Any],
    *,
    project_dir: Path,
) -> Any:
    """Build a dlt filesystem source or resource from compiled ingestion config."""
```

Use dlt filesystem verified-source APIs in the adapter. Start with the supported formats from the design:
- `csv`
- `jsonl`
- `parquet`

Use `source_config["source_config"]` only for safe reader options. Permit `include_glob`, `file_glob`, and `reader_options`; reject connection-like keys named `endpoint`, `access_key`, `secret_key`, `token`, `database`, `host`, `port`, `username`, `password`, or `credentials`.

- [ ] **Step 3: Add a small dispatcher**

Expose:

```python
def build_dlt_source(source_config: Mapping[str, Any], *, project_dir: Path) -> Any:
    if source_config.get("source_type") == "filesystem":
        return build_filesystem_source(source_config, project_dir=project_dir)
    source_name = source_config.get("name", "unnamed")
    source_type = source_config.get("source_type", "missing")
    raise ValueError(f"Unsupported ingestion source_type {source_type!r} for {source_name!r}")
```

This keeps REST API and SQL database source construction intentionally unsupported until they have their own tested adapters.

- [ ] **Step 4: Verify source-construction tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py -q
```

Expected: all tests pass.

### Task 4: Enable Dagster Ingestion Assets From Compiled JSON

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py`

- [ ] **Step 1: Replace failing expectations with runnable JSON expectations**

Update tests that currently expect JSON ingestion config to fail:
- `test_factory_rejects_normal_json_sources_without_executable_source`
- `test_source_asset_rejects_missing_dlt_source_object`

New expected behavior:
- Filesystem JSON config creates an asset without an embedded Python object.
- Materializing the asset calls the source-construction layer.
- REST API and SQL database JSON configs still fail clearly because no adapter exists.

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py -q
```

Expected: updated tests fail against the current executable-source requirement.

- [ ] **Step 2: Thread `project_dir` into `create_ingestion_assets()`**

Change the factory signature to:

```python
def create_ingestion_assets(
    ingestion_ref: PluginRef,
    *,
    project_dir: Path,
) -> list[AssetsDefinition]:
```

Keep a compatibility branch only for tests or internal callers that still pass `source_config.source`; the compiled JSON path must be the primary path.

- [ ] **Step 3: Replace `_validate_executable_source()` with source construction**

Inside the generated asset function:
- Build `IngestionConfig` from the source config.
- If `source_config.source` exists and is source-like, use it.
- Otherwise call `build_dlt_source(source_config, project_dir=project_dir)`.
- Pass the constructed source into `ingestion_plugin.run(pipeline, write_disposition=write_mode, table_name=table_name, schema_contract=schema_contract, cursor_field=cursor_field, primary_key=primary_key, source=dlt_source)`.

Preserve existing behavior for:
- asset naming
- resource key requirement
- metadata
- `write_disposition`
- `table_name`
- `schema_contract`
- `cursor_field`
- `primary_key`
- raising on unsuccessful `IngestionResult`

- [ ] **Step 4: Verify ingestion asset tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py -q
```

Expected: all tests pass.

### Task 5: Wire Ingestion Into The Runtime Builder

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/integration/test_ingestion_wiring.py`

- [ ] **Step 1: Update runtime tests from blocked to enabled**

Replace assertions that expect `_INGESTION_RUNTIME_DISABLED_MESSAGE` with assertions that:
- `load_product_definitions()` succeeds for valid filesystem ingestion sources.
- returned `Definitions.resources` includes `"ingestion"`.
- returned asset keys include names such as `run_ingestion_raw_customers`.
- selected ingestion with no sources remains non-blocking.
- malformed `sources` still fails loudly.

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_loader.py plugins/floe-orchestrator-dagster/tests/integration/test_ingestion_wiring.py -q
```

Expected: updated tests fail because runtime still raises the disabled message.

- [ ] **Step 2: Remove the runtime blocker**

Delete `_INGESTION_RUNTIME_DISABLED_MESSAGE` and the early `raise ValueError(_INGESTION_RUNTIME_DISABLED_MESSAGE)` in `build_product_definitions()`.

- [ ] **Step 3: Create ingestion resources and assets when workloads exist**

In `build_product_definitions()`:

```python
if _has_ingestion_workloads(plugins):
    from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets
    from floe_orchestrator_dagster.resources.ingestion import create_ingestion_resources

    resources.update(create_ingestion_resources(plugins.ingestion))
    assets.extend(create_ingestion_assets(plugins.ingestion, project_dir=project_dir))
```

Keep ingestion assets as first-class assets in the same `Definitions` as dbt assets. Do not add a fake dbt dependency until dbt source declarations are migrated; the E2E flow will run ingestion before transforms explicitly.

- [ ] **Step 4: Verify runtime tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_loader.py plugins/floe-orchestrator-dagster/tests/integration/test_ingestion_wiring.py -q
```

Expected: all tests pass.

### Task 6: Align dlt Destination Configuration With Iceberg/Polaris

**Files:**
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Add: `plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py`
- Add or modify: `plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py`

- [ ] **Step 1: Write focused runtime-binding destination tests**

Superseded: do not add public destination config API tests. Add unit tests that
prove dlt pipeline creation consumes deployment runtime bindings and passes the
expected filesystem destination settings to dlt. The expected shape must reflect
dlt's current filesystem destination behavior: Iceberg support is backed by
PyIceberg catalog runtime binding and object storage, not a product-level secret
block.

Add an integration test that:
- starts `DltIngestionPlugin`
- creates a tiny in-memory dlt source with two rows
- uses MinIO and Polaris catalog config from test fixtures
- writes to an isolated namespace/table
- reads the resulting Iceberg table with PyIceberg

Run:

```bash
uv run pytest plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py -q
uv run pytest plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py -q
```

Expected: at least the integration test fails until destination configuration is truly wired.

- [ ] **Step 2: Pass destination configuration into pipeline creation**

Update `create_pipeline()` so catalog configuration from `IngestionConfig.source_config` or plugin config is applied when constructing the dlt pipeline. Prefer environment variables and dlt/PyIceberg-supported keys over raw credential passthrough.

Retain the existing pipeline naming behavior:

```python
pipeline_name = f"ingest_{table_name}"
dataset_name = namespace
```

- [ ] **Step 3: Tighten health check semantics**

Keep `health_check()` fast by default, but add an optional catalog-aware path only when catalog config is available to the plugin. The health result should distinguish:
- plugin not started
- dlt not importable
- catalog unreachable
- object storage unreachable

Do not make local unit tests depend on live Polaris or MinIO.

- [ ] **Step 4: Verify dlt plugin tests**

Run:

```bash
uv run pytest plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py plugins/floe-ingestion-dlt/tests/unit -q
uv run pytest plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py -q
```

Expected: unit tests pass; integration test passes when Polaris and MinIO test services are running.

### Task 7: Update Customer 360 Demo Configuration

**Files:**
- Modify: `demo/manifest.yaml`
- Modify: `demo/customer-360/floe.yaml`
- Modify if generated artifacts are tracked: `demo/customer-360/target/compiled_artifacts.json`

- [ ] **Step 1: Add failing demo compilation test**

Add or update an existing demo compile test to assert:
- `demo/manifest.yaml` selects `plugins.ingestion.type: dlt`
- `demo/customer-360/floe.yaml` declares three CSV ingestion sources
- compiled artifacts contain the three source configs
- the demo remains CSV-only

Run:

```bash
uv run pytest tests/contract/test_core_to_ingestion_contract.py -q
```

Expected: the new demo-specific assertion fails until config is updated.

- [ ] **Step 2: Add platform-level ingestion plugin selection**

In `demo/manifest.yaml`, add:

```yaml
plugins:
  ingestion:
    type: dlt
    version: 0.1.0
    config:
      retry_config:
        max_retries: 3
        initial_delay_seconds: 1.0
```

Use the existing manifest plugin structure if the file already has a `plugins` block; do not duplicate it.

- [ ] **Step 3: Add data-engineer-owned Customer 360 sources**

In `demo/customer-360/floe.yaml`, add:

```yaml
ingestion:
  sources:
    - name: raw-customers
      sourceType: filesystem
      format: csv
      path: ./data/customers.csv
      destinationTable: bronze.raw_customers
      writeMode: replace
      schemaContract: evolve
    - name: raw-transactions
      sourceType: filesystem
      format: csv
      path: ./data/transactions.csv
      destinationTable: bronze.raw_transactions
      writeMode: replace
      schemaContract: evolve
    - name: raw-support-tickets
      sourceType: filesystem
      format: csv
      path: ./data/support_tickets.csv
      destinationTable: bronze.raw_support_tickets
      writeMode: replace
      schemaContract: evolve
```

This keeps the demo simple: data engineers name files and target tables; platform engineers own Polaris, MinIO, and dlt destination behavior.

- [ ] **Step 4: Compile the demo**

Run:

```bash
uv run floe compile demo/customer-360/floe.yaml --manifest demo/manifest.yaml --output demo/customer-360/target/compiled_artifacts.json
```

If the CLI command differs in this checkout, use the existing demo compile command from `make help` or `rg -n "compile.*demo|customer-360" Makefile scripts packages -g '*'`.

Expected: compiled artifacts include `plugins.ingestion.config.sources`.

### Task 8: Add Customer 360 Ingestion E2E

**Files:**
- Add: `tests/e2e/test_customer360_dlt_ingestion.py`
- Modify if needed: `tests/e2e/conftest.py`

- [ ] **Step 1: Write the failing Customer 360 E2E test**

The test should:
- require `polaris` and `minio`
- compile or load the Customer 360 artifacts
- run the three configured ingestion assets or the same ingestion execution path used by the assets
- assert three Iceberg tables exist:
  - `bronze.raw_customers`
  - `bronze.raw_transactions`
  - `bronze.raw_support_tickets`
- assert each table has non-zero rows through PyIceberg

Run:

```bash
uv run pytest tests/e2e/test_customer360_dlt_ingestion.py -q
```

Expected: test fails until runtime/source/destination wiring is complete.

- [ ] **Step 2: Reuse existing E2E fixtures**

Use existing fixtures from `tests/e2e/conftest.py` and `testing/fixtures`:
- `polaris_client`
- `polaris_with_write_grants`
- `e2e_namespace`
- MinIO credentials helpers
- `rewrite_table_io_for_host_access`

Do not introduce Docker Compose or a second local service stack.

- [ ] **Step 3: Make cleanup deterministic**

Use an isolated namespace/table prefix for the E2E run and purge it in fixture teardown. The test must leave MinIO and Polaris reusable for the next E2E test.

- [ ] **Step 4: Verify Customer 360 E2E**

Run:

```bash
uv run pytest tests/e2e/test_customer360_dlt_ingestion.py -q
```

Expected: the Customer 360 CSV ingestion path passes against real MinIO and Polaris.

### Task 9: Add CSV, JSONL, And Parquet Platform Matrix E2E

**Files:**
- Add: `tests/e2e/test_dlt_ingestion_format_matrix.py`
- Modify if needed: `tests/e2e/conftest.py`

- [ ] **Step 1: Write matrix fixtures**

Create fixtures that upload landed files into MinIO under a unique prefix:
- CSV with header and two rows.
- JSONL with two objects and one optional field present in only one row.
- Parquet generated with `pyarrow`.

Use `boto3` and credentials from `testing.fixtures.credentials`. Use `pyarrow` for Parquet because it is already present in the lockfile.

- [ ] **Step 2: Write happy-path matrix tests**

Parametrize over:

```python
@pytest.mark.parametrize(
    ("format_name", "object_name", "expected_rows"),
    [
        ("csv", "customers.csv", 2),
        ("jsonl", "events.jsonl", 2),
        ("parquet", "orders.parquet", 2),
    ],
)
```

For each case:
- build a compiled-style ingestion source config with `source_type: filesystem`
- run through the same Dagster source-construction and `DltIngestionPlugin` path
- assert the Iceberg table exists
- assert row count and representative columns

Run:

```bash
uv run pytest tests/e2e/test_dlt_ingestion_format_matrix.py -q
```

Expected: tests fail until filesystem source construction and dlt destination config work end to end.

- [ ] **Step 3: Add realistic edge-case tests**

Add E2E or narrow integration tests for the common user issues:
- missing object path returns a clear failed ingestion result
- malformed JSONL fails with source name and path in the error
- schema freeze rejects an added column on the second load
- unsupported format fails at source construction before creating an empty table

Keep discard-value schema behavior out of this slice; the initial user-facing contract supports `evolve` and `freeze`.

- [ ] **Step 4: Verify matrix E2E**

Run:

```bash
uv run pytest tests/e2e/test_dlt_ingestion_format_matrix.py -q
```

Expected: CSV, JSONL, Parquet, and edge-case tests pass against real MinIO and Polaris.

### Task 10: Validate The Full Affected Surface

**Files:**
- Validate all modified files.

- [ ] **Step 1: Run focused unit and contract tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/schemas/test_floe_spec_ingestion.py \
  packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py \
  tests/contract/test_core_to_ingestion_contract.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_loader.py \
  plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py \
  -q
```

Expected: all focused unit and contract tests pass.

- [ ] **Step 2: Run integration tests around runtime and destination wiring**

Run:

```bash
uv run pytest \
  plugins/floe-orchestrator-dagster/tests/integration/test_ingestion_wiring.py \
  plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py \
  -q
```

Expected: integration tests pass when the local K8s service stack is running.

- [ ] **Step 3: Run E2E ingestion tests**

Run:

```bash
uv run pytest \
  tests/e2e/test_customer360_dlt_ingestion.py \
  tests/e2e/test_dlt_ingestion_format_matrix.py \
  -q
```

Expected: Customer 360 CSV, CSV matrix, JSONL matrix, Parquet matrix, and ingestion edge cases pass against MinIO and Polaris.

- [ ] **Step 4: Run repository quality gates**

Run:

```bash
make lint
make typecheck
make test-unit
```

Expected: linting, strict typing, and unit tests pass.

- [ ] **Step 5: Run full E2E gate when services are available**

Run:

```bash
make test-e2e
```

Expected: all E2E tests pass. If infrastructure is unavailable, capture the exact missing service or readiness failure and keep product failures separate from environment failures.

### Task 11: Update Docs And Evidence

**Files:**
- Modify: `docs/superpowers/specs/2026-05-05-dlt-ingestion-e2e-design.md`
- Modify if present: `TESTING.md`
- Modify if present: `docs/architecture/ARCHITECTURE-SUMMARY.md`

- [ ] **Step 1: Add implementation evidence to the design doc**

Append a concise evidence section listing:
- compiled artifact ingestion schema
- Customer 360 source list
- CSV/JSONL/Parquet E2E coverage
- realistic edge cases covered
- commands run

- [ ] **Step 2: Update testing documentation**

Document the new E2E coverage and when to run it:
- Customer 360 demo ingestion: visible user workflow.
- Format matrix: platform capability and regression guard.
- Edge cases: common ingestion failures.

- [ ] **Step 3: Verify docs have no stale blocker language**

Run:

```bash
rg -n "ingestion runtime is not enabled|compiled JSON config cannot yet|executable dlt source object" docs plugins/floe-orchestrator-dagster tests
```

Expected: no stale blocker language remains except in historical plan/design context where it is explicitly described as prior state.

### Task 12: Final Review And Commit

**Files:**
- Validate the final diff.

- [ ] **Step 1: Inspect working tree**

Run:

```bash
git status --short
git diff --stat
git diff --check
```

Expected: only intentional files are modified; no whitespace errors.

- [ ] **Step 2: Run the final focused verification set**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/schemas/test_floe_spec_ingestion.py \
  packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py \
  tests/contract/test_core_to_ingestion_contract.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_loader.py \
  plugins/floe-orchestrator-dagster/tests/integration/test_ingestion_wiring.py \
  plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py \
  tests/e2e/test_customer360_dlt_ingestion.py \
  tests/e2e/test_dlt_ingestion_format_matrix.py \
  -q
```

Expected: all focused tests pass when K8s services are available; otherwise the final report separates skipped or blocked service-backed tests from passing host tests.

- [ ] **Step 3: Commit the implementation**

Run:

```bash
git add \
  packages/floe-core/src/floe_core/schemas/floe_spec.py \
  packages/floe-core/src/floe_core/compilation/resolver.py \
  packages/floe-core/src/floe_core/compilation/stages.py \
  packages/floe-core/tests/unit/schemas/test_floe_spec_ingestion.py \
  packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py \
  tests/contract/test_core_to_ingestion_contract.py \
  plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion \
  plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py \
  plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_loader.py \
  plugins/floe-orchestrator-dagster/tests/integration/test_ingestion_wiring.py \
  plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py \
  plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py \
  plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py \
  demo/manifest.yaml \
  demo/customer-360/floe.yaml \
  tests/e2e/test_customer360_dlt_ingestion.py \
  tests/e2e/test_dlt_ingestion_format_matrix.py \
  docs/superpowers/specs/2026-05-05-dlt-ingestion-e2e-design.md \
  TESTING.md \
  docs/architecture/ARCHITECTURE-SUMMARY.md
git commit -m "Enable dlt ingestion E2E coverage"
```

Omit any doc path that is not changed. Do not add untracked `PROMPT.md` unless the user explicitly requests it.

- [ ] **Step 4: Report verification evidence**

Final report must include:
- files changed by category
- test commands and results
- whether live MinIO/Polaris E2E ran or was blocked by infrastructure
- any remaining operational follow-up
