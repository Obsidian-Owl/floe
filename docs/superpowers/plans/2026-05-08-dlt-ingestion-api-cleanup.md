# dlt Ingestion API Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the stale ingestion `catalog_config` API, make dlt runtime binding the only ingestion destination contract, and promote dlt-created Iceberg tables into Floe's shared platform state for dbt, contracts, catalog validation, observability, lineage, quality, freshness, and demo evidence.

**Architecture:** `floe.yaml` ingestion sources compile into explicit `IngestionOutputTable` state plus a secret-free `CompiledArtifacts.deployment.ingestion.dlt` runtime binding. dlt writes raw Iceberg tables through that binding; downstream platform consumers read the compiled ingestion table state instead of rediscovering dlt configuration. Storage and catalog remain the owners of infrastructure facts, while compute/dbt, validation, lineage, and observability translate those facts for their own domains.

**Tech Stack:** Python 3.10+, Pydantic v2, dlt filesystem + Iceberg-formatted filesystem destination, PyIceberg, DuckDB/dbt-duckdb, Dagster, OpenTelemetry, OpenLineage, Polaris, MinIO/S3.

---

## File Structure

### Contract and Schema

- Modify `packages/floe-core/src/floe_core/plugins/ingestion.py`
  - Remove `get_destination_config(catalog_config)` from the public ABC.
  - Update docstrings to describe deployment bindings and runtime binding handoff.
- Modify `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
  - Add `IngestionOutputTable`.
  - Add `ingestion_outputs: list[IngestionOutputTable]` to `CompiledArtifacts`.
  - Keep the field optional-by-default for artifact backward compatibility.
- Modify `packages/floe-core/src/floe_core/compilation/builder.py`
  - Build `IngestionOutputTable` entries from `FloeSpec.ingestion.sources`.
- Modify `packages/floe-core/src/floe_core/compilation/stages.py`
  - Pass the generated ingestion output state into `build_artifacts`.

### dlt Runtime

- Modify `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
  - Delete `get_destination_config()`.
  - Delete `_bucket_url()` if no remaining runtime code uses it.
  - Keep `_destination_config_from_binding()` as the only destination config path.
- Modify `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py`
  - Remove the stale `get_destination_config` docstring reference.
  - Ensure run spans can carry source, destination, schema contract, result, and failure category.
- Modify dlt unit and integration tests under `plugins/floe-ingestion-dlt/tests/`.

### Dagster, Validation, and Platform State

- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`
  - Keep runtime-binding source construction.
  - Enrich ingestion run metadata with stable compiled source/destination fields.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`
  - Allow expected table derivation from compiled ingestion outputs as well as transform outputs.
- Add or modify tests under `plugins/floe-orchestrator-dagster/tests/unit/`.

### dbt/DuckDB Pickup

- Modify `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py`
  - Allow DuckDB Iceberg REST attach options needed by dbt-duckdb profiles.
- Modify `packages/floe-core/src/floe_core/compilation/dbt_profiles.py`
  - Merge storage/catalog deployment state into generated dbt profile output for Iceberg access.
- Modify `packages/floe-core/src/floe_core/compilation/stages.py`
  - Pass `deployment` into `generate_dbt_profiles`.
- Add tests in `packages/floe-core/tests/unit/compilation/test_dbt_profiles.py`.

### Tests, Docs, and Golden Fixtures

- Modify `tests/contract/test_ingestion_plugin_abc.py`.
- Modify `tests/contract/test_golden_regression.py`.
- Modify the plugin interface golden fixture used by `test_golden_regression.py`.
- Modify `tests/contract/test_core_to_ingestion_contract.py`.
- Modify `tests/e2e/test_customer360_dlt_ingestion.py`.
- Modify `tests/e2e/test_dlt_ingestion_format_matrix.py`.
- Modify `docs/architecture/interfaces/ingestion-plugin.md`.
- Modify `docs/architecture/plugin-system/interfaces.md`.
- Modify `docs/architecture/adr/0020-ingestion-plugins.md`.
- Modify `demo/customer-360/validation.yaml` only if the validation evidence commands need raw ingestion table checks.

---

## Task 1: Remove the stale ingestion destination API contract

**Files:**
- Modify: `packages/floe-core/src/floe_core/plugins/ingestion.py`
- Modify: `tests/contract/test_ingestion_plugin_abc.py`
- Modify: `tests/contract/test_golden_regression.py`
- Modify: plugin interface golden fixture returned by `rg -n "get_destination_config" tests/contract fixtures packages -g '*.json'`
- Modify: `docs/architecture/interfaces/ingestion-plugin.md`
- Modify: `docs/architecture/plugin-system/interfaces.md`
- Modify: `docs/architecture/adr/0020-ingestion-plugins.md`

- [ ] **Step 1: Find the golden fixture path**

Run:

```bash
rg -n '"get_destination_config"|get_destination_config' tests packages docs -g '*.json' -g '*.py' -g '*.md'
```

Expected: output includes `tests/contract/test_golden_regression.py`, the ingestion ABC tests, docs, dlt tests, and one JSON golden fixture. Record the JSON fixture path and use that path in this task's later edit step.

- [ ] **Step 2: Write the failing ABC contract test**

In `tests/contract/test_ingestion_plugin_abc.py`, replace `test_get_destination_config_is_abstract` with:

```python
@pytest.mark.requirement("4F-FR-001")
def test_ingestion_plugin_uses_runtime_binding_contract() -> None:
    """Verify IngestionPlugin no longer exposes catalog_config destination mapping."""
    from floe_core.plugins.ingestion import IngestionPlugin

    assert hasattr(IngestionPlugin, "create_pipeline")
    assert hasattr(IngestionPlugin, "run")
    assert hasattr(IngestionPlugin, "build_deployment_binding")
    assert hasattr(IngestionPlugin, "get_composition_requirements")
    assert not hasattr(IngestionPlugin, "get_destination_config")
```

Also update any mock `IngestionPlugin` classes in this file by deleting their `get_destination_config()` method.

- [ ] **Step 3: Run the ABC test and confirm failure**

Run:

```bash
uv run pytest tests/contract/test_ingestion_plugin_abc.py::test_ingestion_plugin_uses_runtime_binding_contract -q
```

Expected: FAIL because `IngestionPlugin` still has `get_destination_config`.

- [ ] **Step 4: Remove the method from the ABC**

In `packages/floe-core/src/floe_core/plugins/ingestion.py`, remove this abstract method entirely:

```python
@abstractmethod
def get_destination_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
    ...
```

Update the class docstring section that lists concrete plugin requirements to:

```python
Concrete plugins must implement:
    - All abstract properties from PluginMetadata (name, version, floe_api_version)
    - is_external property
    - create_pipeline() method
    - run() method

Plugins that participate in platform composition should also implement:
    - get_composition_requirements()
    - build_deployment_binding()
```

- [ ] **Step 5: Update golden regression expectations**

In `tests/contract/test_golden_regression.py`, update `test_ingestion_plugin_methods_stable` so the required method list is:

```python
required_methods = [
    "is_external",
    "create_pipeline",
    "run",
    "get_composition_requirements",
    "build_deployment_binding",
]
```

In the JSON golden fixture from Step 1, remove `"get_destination_config"` from `IngestionPlugin.methods`. Add `"get_composition_requirements"` and `"build_deployment_binding"` if the fixture does not already contain them.

- [ ] **Step 6: Update docs snippets**

In `docs/architecture/interfaces/ingestion-plugin.md`, replace the interface method block with:

```python
class IngestionPlugin(ABC):
    """Interface for data ingestion/EL plugins (dlt, Airbyte)."""

    name: str
    version: str
    is_external: bool

    @abstractmethod
    def create_pipeline(self, config: IngestionConfig) -> Any:
        """Create ingestion pipeline from data-product source configuration."""
        pass

    @abstractmethod
    def run(self, pipeline: Any, **kwargs) -> IngestionResult:
        """Execute the ingestion pipeline."""
        pass

    def get_composition_requirements(self) -> Any:
        """Declare storage/catalog requirements for platform composition."""
        return None

    def build_deployment_binding(self, *, storage: Any, catalog: Any) -> Any:
        """Build a secret-free deployment binding from composed platform state."""
        raise NotImplementedError
```

In `docs/architecture/plugin-system/interfaces.md` and `docs/architecture/adr/0020-ingestion-plugins.md`, replace any `get_destination_config(catalog_config)` examples with a short note:

```markdown
Ingestion destination wiring is provided by `CompiledArtifacts.deployment.ingestion`.
Ingestion plugins consume composed runtime bindings rather than accepting raw
catalog/storage dictionaries.
```

- [ ] **Step 7: Run contract tests**

Run:

```bash
uv run pytest tests/contract/test_ingestion_plugin_abc.py tests/contract/test_golden_regression.py -q
```

Expected: PASS for the edited contract and golden tests. Failures in mock plugin classes should be fixed by removing mock `get_destination_config()` implementations.

- [ ] **Step 8: Commit**

```bash
git add packages/floe-core/src/floe_core/plugins/ingestion.py \
  tests/contract/test_ingestion_plugin_abc.py \
  tests/contract/test_golden_regression.py \
  docs/architecture/interfaces/ingestion-plugin.md \
  docs/architecture/plugin-system/interfaces.md \
  docs/architecture/adr/0020-ingestion-plugins.md
git add "$(rg -l 'IngestionPlugin|get_destination_config' tests packages -g '*.json')"
git commit -m "Remove ingestion destination config API"
```

Expected: commit succeeds with normal hooks.

---

## Task 2: Add compiled ingestion output table state

**Files:**
- Modify: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Modify: `packages/floe-core/src/floe_core/compilation/builder.py`
- Modify: `packages/floe-core/src/floe_core/compilation/stages.py`
- Modify: `tests/contract/test_core_to_ingestion_contract.py`
- Modify: `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
- Modify: `packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py`

- [ ] **Step 1: Write failing schema tests**

Add to `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`:

```python
class TestIngestionOutputTable:
    """Compiled ingestion table state for platform consumers."""

    def test_ingestion_output_table_serializes_secret_free_state(self) -> None:
        from floe_core.schemas.compiled_artifacts import IngestionOutputTable

        table = IngestionOutputTable(
            source_name="raw-transactions",
            source_type="filesystem",
            table_format="iceberg",
            logical_table="bronze.raw_transactions",
            physical_table="bronze.raw_transactions",
            file_format="csv",
            source_path="./seeds/raw_transactions.csv",
            write_mode="replace",
            schema_contract="evolve",
            freshness_field="_loaded_at",
            quality_tier="bronze",
        )

        payload = table.model_dump(mode="json")

        assert payload["source_name"] == "raw-transactions"
        assert payload["logical_table"] == "bronze.raw_transactions"
        assert payload["physical_table"] == "bronze.raw_transactions"
        assert payload["quality_tier"] == "bronze"

    def test_ingestion_output_table_rejects_secret_like_path(self) -> None:
        from pydantic import ValidationError
        from floe_core.schemas.compiled_artifacts import IngestionOutputTable

        with pytest.raises(ValidationError, match="source_path"):
            IngestionOutputTable(
                source_name="raw-transactions",
                source_type="filesystem",
                table_format="iceberg",
                logical_table="bronze.raw_transactions",
                physical_table="bronze.raw_transactions",
                file_format="csv",
                source_path="s3://example/raw.csv?signature=example",
                write_mode="replace",
                schema_contract="evolve",
            )
```

Add to `tests/contract/test_core_to_ingestion_contract.py`:

```python
def test_demo_compile_emits_ingestion_output_tables() -> None:
    """Compiled artifacts expose dlt raw tables as platform state."""
    from pathlib import Path
    from floe_core.compilation.stages import compile_pipeline

    project_root = Path(__file__).resolve().parents[2]
    artifacts = compile_pipeline(
        project_root / "demo" / "customer-360" / "floe.yaml",
        project_root / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    outputs = {table.logical_table: table for table in artifacts.ingestion_outputs}

    assert set(outputs) == {
        "bronze.raw_customers",
        "bronze.raw_transactions",
        "bronze.raw_support_tickets",
    }
    assert outputs["bronze.raw_transactions"].source_name == "raw-transactions"
    assert outputs["bronze.raw_transactions"].file_format == "csv"
    assert outputs["bronze.raw_transactions"].quality_tier == "bronze"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestIngestionOutputTable \
  tests/contract/test_core_to_ingestion_contract.py::test_demo_compile_emits_ingestion_output_tables \
  -q
```

Expected: FAIL because `IngestionOutputTable` and `CompiledArtifacts.ingestion_outputs` do not exist.

- [ ] **Step 3: Add schema model**

In `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`, add this class immediately before `DeploymentConfig`:

```python
class IngestionOutputTable(BaseModel):
    """Platform-visible state for one ingestion-created Iceberg table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_name: NonEmptyString
    source_type: Literal["filesystem"]
    table_format: Literal["iceberg"] = "iceberg"
    logical_table: NonEmptyString
    physical_table: NonEmptyString
    file_format: Literal["csv", "jsonl", "parquet"]
    source_path: NonEmptyString
    write_mode: Literal["append", "replace", "merge"]
    schema_contract: Literal["evolve", "freeze"]
    freshness_field: NonEmptyString | None = None
    primary_key: NonEmptyString | list[NonEmptyString] | None = None
    cursor_field: NonEmptyString | None = None
    quality_tier: Literal["bronze", "silver", "gold"] = "bronze"

    @field_validator("logical_table", "physical_table")
    @classmethod
    def validate_table_identifier(cls, value: str) -> str:
        """Require namespace.table identifiers for ingestion outputs."""
        parts = value.split(".")
        if len(parts) != 2 or any(part.strip() != part or not part for part in parts):
            msg = "ingestion output tables must use namespace.table identifiers"
            raise ValueError(msg)
        return value

    @field_validator("source_path")
    @classmethod
    def validate_secret_free_source_path(cls, value: str) -> str:
        """Reject source path values that embed credentials."""
        lowered = value.lower()
        if "@" in value or any(
            marker in lowered
            for marker in ("access_key", "secret_key", "password", "token", "signature")
        ):
            msg = "source_path must not contain credential material"
            raise ValueError(msg)
        return value
```

Add this field to `CompiledArtifacts` after `deployment`:

```python
ingestion_outputs: list[IngestionOutputTable] = Field(
    default_factory=list,
    description="Platform-visible Iceberg tables created by ingestion sources",
)
```

- [ ] **Step 4: Build ingestion output state**

In `packages/floe-core/src/floe_core/compilation/builder.py`, import `IngestionOutputTable` and add this helper near `build_artifacts`:

```python
def build_ingestion_outputs(spec: FloeSpec) -> list[IngestionOutputTable]:
    """Build platform state for product-level ingestion outputs."""
    if spec.ingestion is None:
        return []

    outputs: list[IngestionOutputTable] = []
    for source in spec.ingestion.sources:
        outputs.append(
            IngestionOutputTable(
                source_name=source.name,
                source_type=source.source_type,
                logical_table=source.destination_table,
                physical_table=source.destination_table,
                file_format=source.format,
                source_path=source.path,
                write_mode=source.write_mode,
                schema_contract=source.schema_contract,
                freshness_field=source.cursor_field or "_loaded_at",
                primary_key=source.primary_key,
                cursor_field=source.cursor_field,
                quality_tier="bronze",
            )
        )
    return outputs
```

In `build_artifacts()`, pass:

```python
ingestion_outputs=build_ingestion_outputs(spec),
```

inside the `CompiledArtifacts(...)` constructor.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestIngestionOutputTable \
  tests/contract/test_core_to_ingestion_contract.py::test_demo_compile_emits_ingestion_output_tables \
  packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/floe-core/src/floe_core/schemas/compiled_artifacts.py \
  packages/floe-core/src/floe_core/compilation/builder.py \
  packages/floe-core/src/floe_core/compilation/stages.py \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py \
  packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py \
  tests/contract/test_core_to_ingestion_contract.py
git commit -m "Expose ingestion output table state"
```

Expected: commit succeeds.

---

## Task 3: Make platform validation consume ingestion output state

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py`
- Modify: `tests/contract/test_core_to_ingestion_contract.py`

- [ ] **Step 1: Write failing validation tests**

Add to `plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py`:

```python
def test_expected_iceberg_tables_includes_ingestion_outputs_when_requested() -> None:
    from datetime import datetime, timezone
    from floe_core.schemas.compiled_artifacts import (
        CompiledArtifacts,
        CompilationMetadata,
        IngestionOutputTable,
        ObservabilityConfig,
        ProductIdentity,
        ResolvedTransforms,
    )
    from floe_core.schemas.telemetry import TelemetryConfig
    from floe_orchestrator_dagster.validation.iceberg_outputs import expected_iceberg_tables

    artifacts = CompiledArtifacts(
        metadata=CompilationMetadata(
            compiled_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
            floe_version="0.1.0",
            source_hash="sha256:test",
            product_name="customer-360",
            product_version="1.0.0",
        ),
        identity=ProductIdentity(product_id="default.customer_360", domain="default"),
        observability=ObservabilityConfig(telemetry=TelemetryConfig()),
        transforms=ResolvedTransforms(models=[], default_compute="duckdb"),
        ingestion_outputs=[
            IngestionOutputTable(
                source_name="raw-transactions",
                source_type="filesystem",
                logical_table="bronze.raw_transactions",
                physical_table="bronze.raw_transactions",
                file_format="csv",
                source_path="./seeds/raw_transactions.csv",
                write_mode="replace",
                schema_contract="evolve",
            )
        ],
    )

    assert expected_iceberg_tables(artifacts, include_ingestion=True) == [
        "bronze.raw_transactions"
    ]
```

- [ ] **Step 2: Run the test and confirm failure**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py::test_expected_iceberg_tables_includes_ingestion_outputs_when_requested -q
```

Expected: FAIL because `expected_iceberg_tables()` does not accept `include_ingestion`.

- [ ] **Step 3: Implement ingestion-aware expected table derivation**

Change the function signature in `iceberg_outputs.py`:

```python
def expected_iceberg_tables(
    artifacts: CompiledArtifacts,
    expected_tables: Sequence[str] | None = None,
    *,
    include_ingestion: bool = False,
) -> list[str]:
```

Replace the body with:

```python
    namespace = _product_namespace(artifacts)
    if expected_tables is None:
        tables: list[str] = []
        if artifacts.transforms is not None:
            tables.extend(model.name for model in artifacts.transforms.models)
        if include_ingestion:
            tables.extend(table.physical_table for table in artifacts.ingestion_outputs)
        if not tables:
            raise RuntimeError("No expected Iceberg tables were derived from CompiledArtifacts")
        expected_tables = tables
    return [_qualify_table(namespace, table_name) for table_name in expected_tables]
```

Update `validate_iceberg_outputs()`, `reset_iceberg_outputs()`, and `validate_iceberg_outputs_from_file()` to accept and pass `include_ingestion: bool = False`.

Add a CLI flag:

```python
parser.add_argument(
    "--include-ingestion",
    action="store_true",
    help="Include compiled ingestion output tables in expected Iceberg validation.",
)
```

Pass `include_ingestion=args.include_ingestion` to reset and validate calls.

- [ ] **Step 4: Run validation tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py \
  tests/contract/test_core_to_ingestion_contract.py
git commit -m "Validate ingestion output tables as platform state"
```

Expected: commit succeeds.

---

## Task 4: Remove dlt plugin `catalog_config` helpers

**Files:**
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py`
- Modify: `plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py`
- Modify: `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py`
- Modify: `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_connector.py`
- Modify: `plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py`

- [ ] **Step 1: Find remaining dlt destination config references**

Run:

```bash
rg -n "get_destination_config|_bucket_url|catalog_config" \
  plugins/floe-ingestion-dlt/src \
  plugins/floe-ingestion-dlt/tests \
  tests/e2e
```

Expected: references include dlt plugin method/tests, sink connector tests, integration fixture helpers, and E2E fixture helpers.

- [ ] **Step 2: Write failing dlt cleanup tests**

In `plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py`, add:

```python
def test_dlt_plugin_does_not_expose_destination_config_api() -> None:
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    assert not hasattr(DltIngestionPlugin, "get_destination_config")
```

Keep or add this runtime-binding requirement test if not already present:

```python
def test_configured_create_pipeline_requires_runtime_binding() -> None:
    from floe_core.plugins.ingestion import IngestionConfig
    from floe_ingestion_dlt.config import DltIngestionConfig, IngestionSourceConfig
    from floe_ingestion_dlt.errors import PipelineConfigurationError
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    plugin = DltIngestionPlugin()
    plugin.configure(
        DltIngestionConfig(
            sources=[
                IngestionSourceConfig(
                    name="orders",
                    source_type="filesystem",
                    source_config={"format": "csv", "path": "./orders.csv"},
                    destination_table="bronze.orders",
                )
            ]
        )
    )
    plugin.startup()

    with pytest.raises(PipelineConfigurationError, match="runtime binding is required"):
        plugin.create_pipeline(
            IngestionConfig(
                source_type="filesystem",
                source_config={"format": "csv", "path": "./orders.csv"},
                destination_table="bronze.orders",
            )
        )
```

- [ ] **Step 3: Run the dlt cleanup test and confirm failure**

Run:

```bash
uv run pytest plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py::test_dlt_plugin_does_not_expose_destination_config_api -q
```

Expected: FAIL because `DltIngestionPlugin` still exposes `get_destination_config`.

- [ ] **Step 4: Delete the stale dlt API**

In `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`:

- Delete `def get_destination_config(...)`.
- Delete `_bucket_url()` if `rg -n "_bucket_url" plugins/floe-ingestion-dlt/src` shows no other production caller.
- Keep `_destination_config_from_binding()` unchanged.
- Keep `_pipeline_runtime_binding()` unchanged.
- Keep `_temporary_runtime_binding_environment()` unchanged.

In `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py`, change:

```python
Operations like create_pipeline, run, and get_destination_config emit spans for observability.
```

to:

```python
Operations like create_pipeline and run emit spans for observability.
```

- [ ] **Step 5: Rewrite tests to runtime binding**

Delete tests whose only assertion is `get_destination_config()` mapping. Keep `SinkConnector.get_source_config()` tests because reverse ETL is out of scope.

In `plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py`, replace:

```python
"destination_filesystem": DltIngestionPlugin().get_destination_config(catalog_config),
```

with:

```python
"destination_filesystem": {
    "bucket_url": f"s3://{catalog_config['bucket']}",
    "credentials": {
        "endpoint_url": catalog_config["s3_endpoint"],
        "region_name": catalog_config["s3_region"],
        "s3_url_style": "path" if catalog_config["s3_path_style_access"] else "virtual",
    },
},
```

This integration helper may keep a local `_catalog_config()` name if it describes live test infrastructure. It must not call dlt production compatibility APIs.

- [ ] **Step 6: Run dlt unit suite**

Run:

```bash
uv run pytest plugins/floe-ingestion-dlt/tests/unit -q
```

Expected: PASS.

- [ ] **Step 7: Re-run reference search**

Run:

```bash
rg -n "get_destination_config|_bucket_url" \
  packages/floe-core/src \
  packages/floe-core/tests \
  plugins/floe-ingestion-dlt/src \
  plugins/floe-ingestion-dlt/tests \
  plugins/floe-orchestrator-dagster/src \
  plugins/floe-orchestrator-dagster/tests \
  tests/contract \
  tests/e2e \
  docs/architecture
```

Expected: no active ingestion API references. Remaining `get_source_config(catalog_config)` references for `SinkConnector` are acceptable.

- [ ] **Step 8: Commit**

```bash
git add plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py \
  plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py \
  plugins/floe-ingestion-dlt/tests/unit \
  plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py
git commit -m "Remove dlt catalog destination compatibility path"
```

Expected: commit succeeds.

---

## Task 5: Add dbt/DuckDB pickup through generated profile state

**Files:**
- Modify: `packages/floe-core/src/floe_core/compilation/dbt_profiles.py`
- Modify: `packages/floe-core/src/floe_core/compilation/stages.py`
- Modify: `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py`
- Modify: `packages/floe-core/tests/unit/compilation/test_dbt_profiles.py`
- Modify: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`
- Modify: `tests/contract/test_core_to_ingestion_contract.py`

- [ ] **Step 1: Write failing abstraction tests**

Add tests covering the contract boundaries:

- `floe-core` delegates deployment profile augmentation to `ComputePlugin.augment_dbt_profile`.
- `floe-catalog-polaris` emits a neutral `IcebergRestCatalogBinding` using Polaris `config.uri`, not storage endpoints.
- `floe-compute-duckdb` translates that neutral binding into dbt-duckdb `attach` entries.
- `floe-ingestion-dlt` consumes `CatalogDeploymentBinding.iceberg_rest`, not Polaris internals.

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/compilation/test_dbt_profiles.py::TestGenerateDBTProfiles::test_generate_dbt_profiles_delegates_deployment_profile_augmentation \
  plugins/floe-compute-duckdb/tests/unit/test_plugin.py::TestAugmentDBTProfile::test_augment_dbt_profile_can_use_generic_catalog_projection \
  plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py::test_build_deployment_binding_uses_catalog_iceberg_rest_projection \
  -q
```

Expected: FAIL before the abstraction is wired.

- [ ] **Step 3: Add catalog projection and compute-owned profile augmentation**

Do not translate Polaris deployment internals in `floe-core`. Catalog plugins expose an
`IcebergRestCatalogBinding` on `CatalogDeploymentBinding`; compute plugins translate that
neutral projection into adapter-specific profile fragments.

Add `ComputePlugin.augment_dbt_profile(profile, deployment)` as the extension point, have
`generate_dbt_profiles()` call it after applying storage fragments, and implement the
DuckDB-specific Iceberg `attach` shape in `floe-compute-duckdb`.

Change the `generate_dbt_profiles()` signature to:

```python
def generate_dbt_profiles(
    plugins: ResolvedPlugins,
    product_name: str,
    environments: list[str] | None = None,
    storage_binding: DbtStorageBinding | None = None,
    deployment: DeploymentConfig | None = None,
) -> dict[str, Any]:
```

After storage binding merge, delegate to the compute plugin:

```python
profile_output = plugin.augment_dbt_profile(profile_output, deployment)
```

- [ ] **Step 4: Pass deployment from compilation**

In `packages/floe-core/src/floe_core/compilation/stages.py`, update the `generate_dbt_profiles()` call:

```python
dbt_profiles = generate_dbt_profiles(
    plugins=plugins,
    product_name=spec.metadata.name,
    storage_binding=storage_dbt_binding,
    deployment=deployment,
)
```

- [ ] **Step 5: Allow DuckDB profile attach options**

In `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py`, extend `_ALLOWED_ATTACH_OPTION_KEYS`:

```python
_ALLOWED_ATTACH_OPTION_KEYS = frozenset(
    {
        "catalog_uri",
        "endpoint",
        "read_only",
        "schema",
        "secret",
        "access_mode",
        "type",
    }
)
```

- [ ] **Step 6: Run focused dbt profile tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/compilation/test_dbt_profiles.py \
  packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py \
  plugins/floe-compute-duckdb/tests/unit/test_plugin.py::TestAugmentDBTProfile \
  -q
```

Expected: PASS. If DuckDB profile tests assert an exact allowlist, update expected keys to include `endpoint` and `secret`.

- [ ] **Step 7: Add contract proof for demo compile**

Add to `tests/contract/test_core_to_ingestion_contract.py`:

```python
def test_demo_compile_generates_dbt_iceberg_attach_for_raw_tables() -> None:
    """Floe-generated dbt profile can discover dlt-written Iceberg raw tables."""
    from pathlib import Path
    from floe_core.compilation.stages import compile_pipeline

    project_root = Path(__file__).resolve().parents[2]
    artifacts = compile_pipeline(
        project_root / "demo" / "customer-360" / "floe.yaml",
        project_root / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.dbt_profiles is not None
    dev_output = artifacts.dbt_profiles["customer-360"]["outputs"]["dev"]

    assert "iceberg" in dev_output["extensions"]
    assert any(
        attach.get("alias") == "iceberg"
        and attach.get("type") == "iceberg"
        and attach.get("options", {}).get("endpoint")
        == "http://floe-platform-polaris:8181/api/catalog"
        for attach in dev_output["attach"]
    )
```

- [ ] **Step 8: Run contract proof**

Run:

```bash
uv run pytest tests/contract/test_core_to_ingestion_contract.py::test_demo_compile_generates_dbt_iceberg_attach_for_raw_tables -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add packages/floe-core/src/floe_core/compilation/dbt_profiles.py \
  packages/floe-core/src/floe_core/compilation/stages.py \
  plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py \
  packages/floe-core/tests/unit/compilation/test_dbt_profiles.py \
  packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py \
  tests/contract/test_core_to_ingestion_contract.py
git commit -m "Generate dbt Iceberg pickup config"
```

Expected: commit succeeds.

---

## Task 6: Wire observability and lineage to ingestion output state

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`
- Modify: `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py`
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Modify: `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py`

- [ ] **Step 1: Write failing Dagster metadata test**

Add to `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py`:

```python
def test_ingestion_asset_metadata_includes_platform_table_state() -> None:
    from pathlib import Path
    from floe_core.schemas.compiled_artifacts import PluginRef
    from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

    ref = PluginRef(
        type="dlt",
        version="0.1.0",
        config={
            "sources": [
                {
                    "name": "raw-transactions",
                    "source_type": "filesystem",
                    "source_config": {
                        "format": "csv",
                        "path": "./seeds/raw_transactions.csv",
                    },
                    "destination_table": "bronze.raw_transactions",
                    "write_mode": "replace",
                    "schema_contract": "evolve",
                }
            ]
        },
    )

    assets = create_ingestion_assets(
        ref,
        project_dir=Path("."),
        runtime_binding={"source_filesystem": {}},
    )

    metadata = assets[0].metadata_by_key[next(iter(assets[0].keys))]
    assert metadata["source_name"] == "raw-transactions"
    assert metadata["destination_table"] == "bronze.raw_transactions"
    assert metadata["floe.table_kind"] == "ingestion_output"
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py::test_ingestion_asset_metadata_includes_platform_table_state -q
```

Expected: FAIL because `floe.table_kind` is missing.

- [ ] **Step 3: Add metadata to ingestion asset definitions**

In `_create_ingestion_asset()` in `assets/ingestion.py`, update the `metadata={...}` block to include:

```python
"floe.table_kind": "ingestion_output",
"floe.source_name": source_name,
"floe.source_path": _source_path(source_config.get("source_config") or {}) or "",
"floe.schema_contract": source_config.get("schema_contract", "evolve"),
"floe.write_mode": source_config.get("write_mode", "append"),
```

- [ ] **Step 4: Add dlt current-run result attributes test**

In `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py`, add:

```python
def test_run_records_source_destination_context_on_failure() -> None:
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    plugin = DltIngestionPlugin()
    message = plugin._with_source_error_context(
        "boom",
        source_name="raw-transactions",
        source_path="./seeds/raw_transactions.csv",
    )

    assert "source=raw-transactions" in message
    assert "path=./seeds/raw_transactions.csv" in message
    assert "boom" in message
```

This test keeps the current error-context behavior pinned while metadata wiring changes.

- [ ] **Step 5: Run focused observability tests**

Run:

```bash
uv run pytest \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py::test_ingestion_asset_metadata_includes_platform_table_state \
  plugins/floe-ingestion-dlt/tests/unit/test_plugin.py::test_run_records_source_destination_context_on_failure \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py \
  plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py \
  plugins/floe-ingestion-dlt/tests/unit/test_plugin.py
git commit -m "Expose ingestion table state in runtime metadata"
```

Expected: commit succeeds.

---

## Task 7: Add data contract, quality, and freshness validation coverage for raw tables

**Files:**
- Modify: `tests/contract/test_core_to_ingestion_contract.py`
- Modify: `demo/datacontract.yaml` only if adding a raw table contract entry is needed for the test.
- Modify: `docs/architecture/ARCHITECTURE-SUMMARY.md`

- [ ] **Step 1: Add raw table state contract test**

Add to `tests/contract/test_core_to_ingestion_contract.py`:

```python
def test_ingestion_outputs_provide_contract_quality_and_freshness_hooks() -> None:
    """Raw dlt tables carry enough state for governance consumers."""
    from pathlib import Path
    from floe_core.compilation.stages import compile_pipeline

    project_root = Path(__file__).resolve().parents[2]
    artifacts = compile_pipeline(
        project_root / "demo" / "customer-360" / "floe.yaml",
        project_root / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    raw_transactions = next(
        table
        for table in artifacts.ingestion_outputs
        if table.logical_table == "bronze.raw_transactions"
    )

    assert raw_transactions.quality_tier == "bronze"
    assert raw_transactions.freshness_field == "_loaded_at"
    assert raw_transactions.schema_contract == "evolve"
    assert raw_transactions.file_format == "csv"
```

- [ ] **Step 2: Run test**

Run:

```bash
uv run pytest tests/contract/test_core_to_ingestion_contract.py::test_ingestion_outputs_provide_contract_quality_and_freshness_hooks -q
```

Expected: PASS after Task 2. If it fails, fix `build_ingestion_outputs()` so `quality_tier` defaults to `bronze` and `freshness_field` defaults to `_loaded_at`.

- [ ] **Step 3: Document platform state consumption**

In `docs/architecture/ARCHITECTURE-SUMMARY.md`, under the ingestion boundary section, add:

```markdown
Compiled ingestion outputs are platform-visible state. Floe derives raw table
identity, source format/path metadata, schema contract mode, quality tier, and
freshness hooks from `floe.yaml` ingestion declarations. Data contracts, catalog
validation, lineage, observability, quality checks, freshness checks, and dbt
source consumption should read that compiled state rather than requiring data
engineers to duplicate raw-table metadata in separate integration files.
```

- [ ] **Step 4: Run docs/contract checks**

Run:

```bash
uv run pytest tests/contract/test_core_to_ingestion_contract.py::test_ingestion_outputs_provide_contract_quality_and_freshness_hooks -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/contract/test_core_to_ingestion_contract.py \
  docs/architecture/ARCHITECTURE-SUMMARY.md \
  demo/datacontract.yaml
git commit -m "Document ingestion outputs as platform state"
```

Expected: commit succeeds. If `demo/datacontract.yaml` is unchanged, `git add` will ignore it and the commit should include only the changed files.

---

## Task 8: Rewrite E2E fixtures and edge cases around runtime bindings

**Files:**
- Modify: `tests/e2e/test_customer360_dlt_ingestion.py`
- Modify: `tests/e2e/test_dlt_ingestion_format_matrix.py`
- Modify: `plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py`

- [ ] **Step 1: Remove production API use from E2E fixtures**

Run:

```bash
rg -n "get_destination_config|catalog_config" tests/e2e plugins/floe-ingestion-dlt/tests/integration
```

Expected: any `get_destination_config` output must be removed in this task. `_catalog_config()` helpers may remain only as test infrastructure helpers for live Polaris/MinIO endpoints.

- [ ] **Step 2: Add binding helper in format matrix**

In `tests/e2e/test_dlt_ingestion_format_matrix.py`, replace `_runtime_binding(catalog_config)` with a helper that returns a binding-shaped payload directly:

```python
def _runtime_binding(catalog_config: dict[str, Any]) -> dict[str, Any]:
    """Build binding-shaped runtime config for host-reachable E2E services."""
    catalog_name = str(catalog_config.get("catalog_name", "polaris"))
    env_catalog = catalog_name.upper().replace("-", "_")
    prefix = f"PYICEBERG_CATALOG__{env_catalog}__"
    return {
        "plugin_name": "dlt",
        "destination": "filesystem",
        "table_format": "iceberg",
        "destination_filesystem": {
            "bucket_url": f"s3://{catalog_config['bucket']}",
            "credentials": {
                "endpoint_url": catalog_config["s3_endpoint"],
                "region_name": catalog_config["s3_region"],
                "s3_url_style": "path"
                if catalog_config["s3_path_style_access"]
                else "virtual",
            },
        },
        "source_filesystem": {
            "endpoint_url": catalog_config["s3_endpoint"],
            "region_name": catalog_config["s3_region"],
            "s3_url_style": "path"
            if catalog_config["s3_path_style_access"]
            else "virtual",
        },
        "iceberg_catalog_env": {
            "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": catalog_name,
            "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
            f"{prefix}TYPE": "rest",
            f"{prefix}URI": str(catalog_config["uri"]),
            f"{prefix}WAREHOUSE": str(catalog_config["warehouse"]),
            f"{prefix}S3__ENDPOINT": str(catalog_config["s3_endpoint"]),
            f"{prefix}S3__REGION": str(catalog_config["s3_region"]),
            f"{prefix}S3__PATH_STYLE_ACCESS": "true",
        },
        "env_refs": {},
    }
```

- [ ] **Step 3: Ensure missing object path fails**

In `tests/e2e/test_dlt_ingestion_format_matrix.py`, adjust `test_missing_object_path_returns_failed_ingestion_result` so the source path uses a glob that dlt attempts to resolve and assert failure by table absence:

```python
assert not result.success, "Expected ingestion to fail"
_assert_failed_ingestion_did_not_commit_rows(catalog, table_identifier)
```

If dlt treats an empty glob as a successful zero-row load, change the expected behavior to validate no table commit and add a separate source-construction validation that rejects non-existent local file paths. Do not mark an empty object-store prefix as a product failure if dlt documents it as a zero-row source.

- [ ] **Step 4: Add dbt pickup smoke to Customer 360 E2E**

In `tests/e2e/test_customer360_dlt_ingestion.py`, add a helper:

```python
def _assert_raw_table_queryable_for_dbt(catalog: Any, table_identifier: str) -> None:
    """Prove a dlt raw Iceberg table is queryable as platform table state."""
    table = catalog.load_table(table_identifier)
    arrow_table = table.scan(limit=1).to_arrow()
    assert arrow_table.num_rows >= 1
```

Call it after each raw Customer 360 source is ingested:

```python
_assert_raw_table_queryable_for_dbt(catalog, table_identifier)
```

This is the E2E table-state proof. Task 5 covers generated dbt profile shape.

- [ ] **Step 5: Run E2E collection**

Run:

```bash
uv run pytest tests/e2e/test_customer360_dlt_ingestion.py tests/e2e/test_dlt_ingestion_format_matrix.py --collect-only -q
```

Expected: collection passes.

- [ ] **Step 6: Run local E2E if services are available**

Run:

```bash
uv run pytest tests/e2e/test_customer360_dlt_ingestion.py tests/e2e/test_dlt_ingestion_format_matrix.py -q
```

Expected: PASS when Polaris, MinIO, and required ports are available. If local services are unavailable, record the infrastructure error exactly and continue to remote validation in Task 10.

- [ ] **Step 7: Commit**

```bash
git add tests/e2e/test_customer360_dlt_ingestion.py \
  tests/e2e/test_dlt_ingestion_format_matrix.py \
  plugins/floe-ingestion-dlt/tests/integration/test_dlt_iceberg_destination.py
git commit -m "Exercise dlt runtime bindings in E2E fixtures"
```

Expected: commit succeeds.

---

## Task 9: Final local validation and stale reference audit

**Files:**
- Modify only files needed to fix failures found by this task.

- [ ] **Step 1: Run stale reference audit**

Run:

```bash
rg -n "get_destination_config|plugins\\.ingestion\\.config\\.catalog_config|_bucket_url|dlt product ingestion requires an Iceberg-formatted filesystem destination catalog_config" \
  packages/floe-core/src \
  packages/floe-core/tests \
  plugins/floe-ingestion-dlt/src \
  plugins/floe-ingestion-dlt/tests \
  plugins/floe-orchestrator-dagster/src \
  plugins/floe-orchestrator-dagster/tests \
  tests/contract \
  tests/e2e \
  docs/architecture \
  demo
```

Expected: no active ingestion compatibility references. `SinkConnector.get_source_config(catalog_config)` is acceptable when the output is from `packages/floe-core/src/floe_core/plugins/sink.py` or sink tests.

- [ ] **Step 2: Run focused test suite**

Run:

```bash
uv run pytest \
  tests/contract/test_ingestion_plugin_abc.py \
  tests/contract/test_golden_regression.py \
  tests/contract/test_core_to_ingestion_contract.py \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestIngestionOutputTable \
  packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py \
  packages/floe-core/tests/unit/compilation/test_dbt_profiles.py \
  plugins/floe-ingestion-dlt/tests/unit \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run linters and type checks for touched packages**

Run:

```bash
uv run ruff check \
  packages/floe-core/src \
  packages/floe-core/tests/unit/compilation/test_dbt_profiles.py \
  tests/contract/test_core_to_ingestion_contract.py \
  plugins/floe-ingestion-dlt/src \
  plugins/floe-ingestion-dlt/tests \
  plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py \
  plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py
uv run mypy packages/floe-core/src plugins/floe-ingestion-dlt/src plugins/floe-orchestrator-dagster/src
```

Expected: both commands pass.

- [ ] **Step 4: Run E2E collection**

Run:

```bash
uv run pytest tests/e2e/test_customer360_dlt_ingestion.py tests/e2e/test_dlt_ingestion_format_matrix.py --collect-only -q
```

Expected: collection passes.

- [ ] **Step 5: Commit validation fixes**

If any files changed:

```bash
git add packages/floe-core plugins/floe-ingestion-dlt plugins/floe-orchestrator-dagster tests docs demo
git commit -m "Validate dlt ingestion API cleanup"
```

Expected: commit succeeds. If no files changed, do not create an empty commit.

---

## Task 10: Remote DevPod + Hetzner validation and cleanup

**Files:**
- Modify only failure fixes found by the remote lane.

- [ ] **Step 1: Push branch**

Run:

```bash
git push origin feat/e2e-dlt-ingestion
```

Expected: branch pushes successfully.

- [ ] **Step 2: Run remote validation lane**

Run the repo-native DevPod lane used by this branch:

```bash
make devpod-test
```

Expected: DevPod provisions the remote Hetzner-backed workspace, runs bootstrap/platform/developer/destructive lanes, and writes artifacts under `test-artifacts/devpod-run-*`.

- [ ] **Step 3: Summarize product versus infra failures**

Inspect the latest artifact directory:

```bash
latest_artifact="$(ls -td test-artifacts/devpod-run-* | head -1)"
printf '%s\n' "$latest_artifact"
rg -n "FAILED|ERROR|resource_unavailable|URI missing|LoadClientJobRetry|schema contract|tables_validated|lineage|trace" "$latest_artifact"
```

Expected: produce a lane-by-lane summary:

- bootstrap
- platform
- developer
- destructive
- dlt ingestion
- dbt pickup
- platform state validation
- observability/lineage

Classify each failure as product, test harness, or infrastructure.

- [ ] **Step 4: Fix product failures**

For each product failure, write a focused regression test before changing production code. Use the task above that owns the failing area:

- API/golden failure: Task 1
- compiled state failure: Task 2
- validation failure: Task 3
- dlt runtime failure: Task 4
- dbt pickup failure: Task 5
- observability/lineage failure: Task 6
- E2E fixture failure: Task 8

Run the smallest failing test locally, fix it, then push again.

- [ ] **Step 5: Verify Hetzner cleanup**

Run:

```bash
devpod list
hcloud server list
hcloud volume list
hcloud load-balancer list
hcloud floating-ip list
hcloud ssh-key list
```

Expected: `devpod list` shows no active workspaces for this run, and Hetzner inventory shows no orphaned servers, volumes, load balancers, floating IPs, or temporary SSH keys from the validation lane.

- [ ] **Step 6: Commit remote fixes**

If remote validation required fixes:

```bash
git add packages/floe-core plugins/floe-ingestion-dlt plugins/floe-orchestrator-dagster tests docs demo
git commit -m "Fix remote dlt ingestion cleanup validation"
git push origin feat/e2e-dlt-ingestion
```

Expected: commit and push succeed.

---

## Final Verification Checklist

- [ ] `IngestionPlugin` has no `get_destination_config` method.
- [ ] `DltIngestionPlugin` has no `get_destination_config` method.
- [ ] Golden interface regression reflects the new ingestion API.
- [ ] No active dlt ingestion runtime path reads `plugins.ingestion.config.catalog_config`.
- [ ] `CompiledArtifacts.ingestion_outputs` contains Customer 360 raw tables.
- [ ] Catalog validation can include ingestion outputs.
- [ ] Generated dbt profiles include DuckDB Iceberg REST attach state.
- [ ] dlt unit suite passes.
- [ ] focused contract suite passes.
- [ ] E2E collection passes.
- [ ] Remote DevPod + Hetzner validation completed or has clearly classified infra failures.
- [ ] Hetzner resources are confirmed clean after remote validation.
