# Alpha Spine Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the alpha runtime spine deterministic from manifest-driven configuration through Dagster, dbt, Iceberg, OpenLineage, Marquez, and DevPod/Hetzner validation.

**Architecture:** Classify stale Iceberg catalog pointers at the `floe-iceberg` lifecycle boundary, expose explicit strict/repair/reset behavior to validation helpers, model runtime resource presets in the platform manifest contract, and make lineage/DevPod validation derive identity from emitted/runtime state instead of hardcoded assumptions.

**Tech Stack:** Python 3.10+, Pydantic v2, PyIceberg, Polaris REST catalog, MinIO/S3, Dagster, OpenLineage, Marquez, Helm, Flux, Kind, DevPod + Hetzner.

---

## File Structure

- Modify `packages/floe-iceberg/src/floe_iceberg/errors.py`: add a structured stale metadata exception.
- Modify `packages/floe-iceberg/src/floe_iceberg/models.py`: add `StaleTableRecoveryMode` and recovery config fields.
- Modify `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py`: detect stale metadata on table load/create/drop paths and apply strict/repair mode.
- Modify `packages/floe-iceberg/src/floe_iceberg/manager.py`: pass manager config into `_IcebergTableLifecycle`.
- Modify `packages/floe-iceberg/tests/unit/test_errors.py`: cover the new exception details.
- Modify `packages/floe-iceberg/tests/unit/test_lifecycle.py`: cover strict and repair behavior with a mock stale metadata failure.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`: expose validation/reset/repair mode flags and structured diagnostics.
- Modify `tests/e2e/test_demo_iceberg_outputs.py`: run validation in the configured mode and assert the expected table set after materialization.
- Modify `packages/floe-core/src/floe_core/schemas/manifest.py`: add typed `resource_presets` manifest config.
- Modify `packages/floe-core/src/floe_core/helm/schemas.py`: add conversion from manifest resource preset shape to `HelmValuesConfig`.
- Modify `packages/floe-core/tests/unit/schemas/test_manifest.py`: prove `demo/manifest.yaml` no longer leaves `resource_presets` in `model_extra`.
- Modify `packages/floe-core/tests/unit/helm/test_schemas.py`: prove manifest-defined resource presets render into Helm values.
- Modify `tests/e2e/test_observability.py`: query Marquez using emitted/runtime namespace and job identity.
- Modify `testing/k8s/setup-cluster.sh`: make Flux source branch explicit and verifiable.
- Add `tests/unit/test_flux_source_selection.py`: cover branch/source mismatch failure.
- Modify `docs/validation/2026-04-25-alpha-reliability-validation.md`: append closure evidence after implementation and validation.

## Task 1: Classify Stale Iceberg Metadata

**Files:**
- Modify: `packages/floe-iceberg/src/floe_iceberg/errors.py`
- Modify: `packages/floe-iceberg/src/floe_iceberg/models.py`
- Modify: `packages/floe-iceberg/tests/unit/test_errors.py`
- Modify: `packages/floe-iceberg/tests/unit/test_models.py`

- [ ] **Step 1: Write failing exception tests**

Add to `packages/floe-iceberg/tests/unit/test_errors.py`:

```python
def test_stale_table_metadata_error_includes_repair_context() -> None:
    """Stale table metadata errors expose table, metadata location, and mode."""
    from floe_iceberg.errors import StaleTableMetadataError
    from floe_iceberg.models import StaleTableRecoveryMode

    error = StaleTableMetadataError(
        "Catalog table metadata points at a missing object-store file",
        table_identifier="customer_360.int_customer_orders",
        metadata_location="s3://floe-iceberg/customer_360/int_customer_orders/metadata/00001.metadata.json",
        recovery_mode=StaleTableRecoveryMode.STRICT,
        original_error=RuntimeError("NotFoundException: Location does not exist"),
    )

    assert error.table_identifier == "customer_360.int_customer_orders"
    assert error.metadata_location.endswith("00001.metadata.json")
    assert error.recovery_mode is StaleTableRecoveryMode.STRICT
    assert error.details["original_error_type"] == "RuntimeError"
    assert "stale_table_metadata" in error.details["reason"]
```

- [ ] **Step 2: Write failing model tests**

Add to `packages/floe-iceberg/tests/unit/test_models.py`:

```python
def test_iceberg_manager_config_defaults_to_strict_stale_metadata_recovery() -> None:
    """Production-safe default is strict failure, not automatic repair."""
    from floe_iceberg.models import IcebergTableManagerConfig, StaleTableRecoveryMode

    config = IcebergTableManagerConfig()

    assert config.stale_table_recovery_mode is StaleTableRecoveryMode.STRICT


def test_iceberg_manager_config_accepts_repair_stale_metadata_recovery() -> None:
    """Demo/test callers can opt into repair mode explicitly."""
    from floe_iceberg.models import IcebergTableManagerConfig, StaleTableRecoveryMode

    config = IcebergTableManagerConfig(stale_table_recovery_mode="repair")

    assert config.stale_table_recovery_mode is StaleTableRecoveryMode.REPAIR
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_errors.py::test_stale_table_metadata_error_includes_repair_context packages/floe-iceberg/tests/unit/test_models.py::test_iceberg_manager_config_defaults_to_strict_stale_metadata_recovery packages/floe-iceberg/tests/unit/test_models.py::test_iceberg_manager_config_accepts_repair_stale_metadata_recovery -q
```

Expected: fail because `StaleTableMetadataError` and `stale_table_recovery_mode` do not exist.

- [ ] **Step 4: Add enum and config field**

In `packages/floe-iceberg/src/floe_iceberg/models.py`, add near the other enums:

```python
class StaleTableRecoveryMode(str, Enum):
    """How to handle catalog tables whose metadata files are missing."""

    STRICT = "strict"
    REPAIR = "repair"
```

Add to `IcebergTableManagerConfig`:

```python
stale_table_recovery_mode: StaleTableRecoveryMode = Field(
    default=StaleTableRecoveryMode.STRICT,
    description=(
        "How to handle catalog table registrations that point at missing "
        "Iceberg metadata files. strict fails; repair drops and recreates "
        "the broken registration when creating with if_not_exists=True."
    ),
)
```

- [ ] **Step 5: Add structured exception**

In `packages/floe-iceberg/src/floe_iceberg/errors.py`, add after `NoSuchTableError`:

```python
class StaleTableMetadataError(TableError):
    """Catalog table registration points at missing Iceberg metadata."""

    def __init__(
        self,
        message: str,
        table_identifier: str,
        metadata_location: str | None,
        recovery_mode: Any,
        original_error: BaseException,
    ) -> None:
        details = {
            "reason": "stale_table_metadata",
            "metadata_location": metadata_location or "unknown",
            "recovery_mode": str(getattr(recovery_mode, "value", recovery_mode)),
            "original_error_type": type(original_error).__name__,
            "original_error": str(original_error),
        }
        super().__init__(message, table_identifier=table_identifier, details=details)
        self.metadata_location = metadata_location
        self.recovery_mode = recovery_mode
        self.original_error = original_error
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_errors.py::test_stale_table_metadata_error_includes_repair_context packages/floe-iceberg/tests/unit/test_models.py::test_iceberg_manager_config_defaults_to_strict_stale_metadata_recovery packages/floe-iceberg/tests/unit/test_models.py::test_iceberg_manager_config_accepts_repair_stale_metadata_recovery -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add packages/floe-iceberg/src/floe_iceberg/errors.py packages/floe-iceberg/src/floe_iceberg/models.py packages/floe-iceberg/tests/unit/test_errors.py packages/floe-iceberg/tests/unit/test_models.py
git commit -m "feat: classify stale iceberg table metadata"
```

## Task 2: Repair Stale Table Registrations During Idempotent Create

**Files:**
- Modify: `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py`
- Modify: `packages/floe-iceberg/src/floe_iceberg/manager.py`
- Modify: `packages/floe-iceberg/tests/unit/test_lifecycle.py`

- [ ] **Step 1: Write failing strict-mode lifecycle test**

Add to `packages/floe-iceberg/tests/unit/test_lifecycle.py`:

```python
class _StaleLoadCatalog:
    """Catalog that reports table existence but fails metadata load."""

    def __init__(self) -> None:
        self.drop_calls: list[tuple[str, bool]] = []

    def load_table(self, identifier: str) -> object:
        raise RuntimeError(
            "NotFoundException: Location does not exist: "
            "s3://floe-iceberg/customer_360/int_customer_orders/metadata/00001.metadata.json"
        )


def test_create_table_if_not_exists_strict_raises_stale_metadata(
    mock_catalog_plugin: MockCatalogPlugin,
    mock_storage_plugin: MockStoragePlugin,
    sample_table_config: Any,
) -> None:
    """Strict mode fails clearly when an existing registration is stale."""
    from floe_iceberg import IcebergTableManager
    from floe_iceberg.errors import StaleTableMetadataError
    from floe_iceberg.models import IcebergTableManagerConfig

    mock_catalog_plugin.create_namespace("bronze", {})
    mock_catalog_plugin._tables["bronze.customers"] = {"schema": {}, "properties": {}}
    manager = IcebergTableManager(
        catalog_plugin=mock_catalog_plugin,
        storage_plugin=mock_storage_plugin,
        config=IcebergTableManagerConfig(stale_table_recovery_mode="strict"),
    )
    manager._catalog = _StaleLoadCatalog()
    manager._lifecycle._catalog = manager._catalog

    with pytest.raises(StaleTableMetadataError) as exc_info:
        manager.create_table(sample_table_config, if_not_exists=True)

    assert exc_info.value.table_identifier == "bronze.customers"
    assert exc_info.value.details["recovery_mode"] == "strict"
```

- [ ] **Step 2: Write failing repair-mode lifecycle test**

Add to `packages/floe-iceberg/tests/unit/test_lifecycle.py`:

```python
def test_create_table_if_not_exists_repair_drops_and_recreates_stale_registration(
    mock_catalog_plugin: MockCatalogPlugin,
    mock_storage_plugin: MockStoragePlugin,
    sample_table_config: Any,
) -> None:
    """Repair mode drops stale catalog registration before recreating."""
    from floe_iceberg import IcebergTableManager
    from floe_iceberg.models import IcebergTableManagerConfig

    mock_catalog_plugin.create_namespace("bronze", {})
    mock_catalog_plugin._tables["bronze.customers"] = {"schema": {}, "properties": {}}
    manager = IcebergTableManager(
        catalog_plugin=mock_catalog_plugin,
        storage_plugin=mock_storage_plugin,
        config=IcebergTableManagerConfig(stale_table_recovery_mode="repair"),
    )
    manager._catalog = _StaleLoadCatalog()
    manager._lifecycle._catalog = manager._catalog

    recreated = manager.create_table(sample_table_config, if_not_exists=True)

    assert recreated.identifier == "bronze.customers"
    assert "bronze.customers" in mock_catalog_plugin._tables
```

- [ ] **Step 3: Run lifecycle tests to verify failure**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_lifecycle.py::test_create_table_if_not_exists_strict_raises_stale_metadata packages/floe-iceberg/tests/unit/test_lifecycle.py::test_create_table_if_not_exists_repair_drops_and_recreates_stale_registration -q
```

Expected: fail because lifecycle does not classify stale metadata or repair.

- [ ] **Step 4: Pass manager config into lifecycle**

In `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py`, update the initializer:

```python
def __init__(
    self,
    catalog: Catalog,
    catalog_plugin: CatalogPlugin,
    config: IcebergTableManagerConfig | None = None,
) -> None:
    self._catalog = catalog
    self._catalog_plugin = catalog_plugin
    self._config = config or IcebergTableManagerConfig()
    self._log = structlog.get_logger(__name__)
```

Add `IcebergTableManagerConfig` and `StaleTableRecoveryMode` to imports from `floe_iceberg.models`.

In `packages/floe-iceberg/src/floe_iceberg/manager.py`, change:

```python
self._lifecycle = _IcebergTableLifecycle(self._catalog, self._catalog_plugin)
```

to:

```python
self._lifecycle = _IcebergTableLifecycle(
    self._catalog,
    self._catalog_plugin,
    self._config,
)
```

- [ ] **Step 5: Add stale metadata detection helpers**

In `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py`, add:

```python
def _is_stale_metadata_error(self, exc: BaseException) -> bool:
    message = str(exc)
    return (
        "NotFoundException" in message
        and "Location does not exist" in message
        and "/metadata/" in message
        and ".metadata.json" in message
    )


def _metadata_location_from_error(self, exc: BaseException) -> str | None:
    for token in str(exc).replace(",", " ").split():
        if token.startswith("s3://") and ".metadata.json" in token:
            return token.rstrip(".")
    return None


def _stale_metadata_error(self, identifier: str, exc: BaseException) -> StaleTableMetadataError:
    return StaleTableMetadataError(
        "Catalog table metadata points at a missing object-store file",
        table_identifier=identifier,
        metadata_location=self._metadata_location_from_error(exc),
        recovery_mode=self._config.stale_table_recovery_mode,
        original_error=exc,
    )
```

- [ ] **Step 6: Apply strict/repair behavior in create path**

In `_IcebergTableLifecycle.create_table`, replace the `if_not_exists` branch:

```python
if if_not_exists:
    self._log.info(
        "table_already_exists_returning_existing",
        identifier=identifier,
    )
    return self.load_table(identifier)
```

with:

```python
if if_not_exists:
    self._log.info(
        "table_already_exists_returning_existing",
        identifier=identifier,
    )
    try:
        return self.load_table(identifier)
    except Exception as exc:
        if not self._is_stale_metadata_error(exc):
            raise
        stale_error = self._stale_metadata_error(identifier, exc)
        if self._config.stale_table_recovery_mode is StaleTableRecoveryMode.STRICT:
            raise stale_error from exc
        self._log.warning(
            "stale_table_metadata_repairing",
            identifier=identifier,
            metadata_location=stale_error.metadata_location,
        )
        self._catalog_plugin.drop_table(identifier, purge=False)
```

After this block, the existing create logic should continue and recreate the table.

- [ ] **Step 7: Run focused lifecycle tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_lifecycle.py::test_create_table_if_not_exists_strict_raises_stale_metadata packages/floe-iceberg/tests/unit/test_lifecycle.py::test_create_table_if_not_exists_repair_drops_and_recreates_stale_registration -q
```

Expected: both selected tests pass.

- [ ] **Step 8: Run package unit tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit -q
```

Expected: package unit tests pass.

- [ ] **Step 9: Commit**

```bash
git add packages/floe-iceberg/src/floe_iceberg/_lifecycle.py packages/floe-iceberg/src/floe_iceberg/manager.py packages/floe-iceberg/tests/unit/test_lifecycle.py
git commit -m "feat: repair stale iceberg table registrations"
```

## Task 3: Add Explicit Iceberg Output Reset And Validation Modes

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`
- Modify: `tests/e2e/test_demo_iceberg_outputs.py`
- Add: `plugins/floe-orchestrator-dagster/tests/unit/validation/test_iceberg_outputs.py`

- [ ] **Step 1: Write unit tests for reset mode parsing**

Create `plugins/floe-orchestrator-dagster/tests/unit/validation/test_iceberg_outputs.py`:

```python
"""Tests for deployed Iceberg output validation helpers."""

from __future__ import annotations

import pytest

from floe_orchestrator_dagster.validation.iceberg_outputs import _parse_recovery_mode


def test_parse_recovery_mode_defaults_to_strict() -> None:
    """Validation is strict unless caller opts into repair or reset."""
    assert _parse_recovery_mode(None) == "strict"


@pytest.mark.parametrize("value", ["strict", "repair", "reset"])
def test_parse_recovery_mode_accepts_supported_modes(value: str) -> None:
    """Supported modes are explicit and stable."""
    assert _parse_recovery_mode(value) == value


def test_parse_recovery_mode_rejects_unknown_value() -> None:
    """Unknown recovery modes fail before catalog mutation."""
    with pytest.raises(ValueError, match="Unsupported Iceberg validation recovery mode"):
        _parse_recovery_mode("retry")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/validation/test_iceberg_outputs.py -q
```

Expected: fail because `_parse_recovery_mode` does not exist.

- [ ] **Step 3: Add recovery mode parsing**

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`, add:

```python
RecoveryMode = Literal["strict", "repair", "reset"]


def _parse_recovery_mode(value: str | None) -> RecoveryMode:
    """Parse Iceberg validation recovery mode."""
    if value is None or value == "":
        return "strict"
    if value in {"strict", "repair", "reset"}:
        return cast(RecoveryMode, value)
    msg = f"Unsupported Iceberg validation recovery mode: {value}"
    raise ValueError(msg)
```

Update imports to include `Literal`.

- [ ] **Step 4: Add reset helper**

In the same file, add:

```python
def reset_iceberg_outputs(
    artifacts: CompiledArtifacts,
    expected_tables: Sequence[str] | None = None,
) -> list[str]:
    """Drop expected Iceberg output table registrations before validation runs."""
    expected_table_names = expected_iceberg_tables(artifacts, expected_tables)
    catalog = _connect_catalog_from_artifacts(artifacts)
    dropped: list[str] = []
    for table_name in expected_table_names:
        try:
            catalog.drop_table(table_name, purge_requested=False)  # type: ignore[call-arg]
        except Exception as exc:  # noqa: BLE001 - reset should tolerate missing tables.
            if "NoSuchTable" not in type(exc).__name__ and "not found" not in str(exc).lower():
                raise RuntimeError(f"Failed to reset Iceberg table {table_name}: {exc}") from exc
        else:
            dropped.append(table_name)
    return dropped
```

- [ ] **Step 5: Add CLI flag and result field**

In `_main`, add:

```python
parser.add_argument(
    "--recovery-mode",
    choices=["strict", "repair", "reset"],
    default="strict",
    help="How to handle existing Iceberg output state before validation.",
)
```

Before `validate_iceberg_outputs_from_file`, add:

```python
artifacts = CompiledArtifacts.model_validate_json(args.artifacts_path.read_text())
recovery_mode = _parse_recovery_mode(args.recovery_mode)
dropped_tables: list[str] = []
if recovery_mode == "reset":
    dropped_tables = reset_iceberg_outputs(
        artifacts=artifacts,
        expected_tables=_parse_expected_tables(args.expected_table),
    )
result = validate_iceberg_outputs(
    artifacts=artifacts,
    expected_tables=_parse_expected_tables(args.expected_table),
)
```

Print `recovery_mode` and `dropped_tables` in the JSON payload:

```python
"recovery_mode": recovery_mode,
"dropped_tables": dropped_tables,
```

- [ ] **Step 6: Pass mode from E2E test**

In `tests/e2e/test_demo_iceberg_outputs.py`, add:

```python
_DEFAULT_RECOVERY_MODE = "strict"
```

Read the environment variable:

```python
recovery_mode = os.environ.get("FLOE_E2E_ICEBERG_RECOVERY_MODE", _DEFAULT_RECOVERY_MODE)
```

Add the CLI args:

```python
"--recovery-mode",
recovery_mode,
```

Assert it round-tripped:

```python
assert validation["recovery_mode"] == recovery_mode
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/validation/test_iceberg_outputs.py tests/e2e/test_demo_iceberg_outputs.py::test_parse_validation_stdout_reads_last_json_line -q
```

Expected: selected tests pass.

- [ ] **Step 8: Commit**

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py plugins/floe-orchestrator-dagster/tests/unit/validation/test_iceberg_outputs.py tests/e2e/test_demo_iceberg_outputs.py
git commit -m "test: add iceberg output recovery validation modes"
```

## Task 4: Model Manifest Resource Presets And Feed Helm Values

**Files:**
- Modify: `packages/floe-core/src/floe_core/schemas/manifest.py`
- Modify: `packages/floe-core/src/floe_core/helm/schemas.py`
- Modify: `packages/floe-core/tests/unit/schemas/test_manifest.py`
- Modify: `packages/floe-core/tests/unit/helm/test_schemas.py`

- [ ] **Step 1: Write failing manifest tests**

Add to `packages/floe-core/tests/unit/schemas/test_manifest.py` near the demo manifest tests:

```python
@pytest.mark.requirement("AC-RESOURCE-PRESETS")
def test_demo_manifest_resource_presets_are_typed(self) -> None:
    """resource_presets is platform configuration, not ignored model_extra."""
    manifest = self._load_demo_manifest()

    assert manifest.resource_presets is not None
    assert manifest.resource_presets["large"].limits.memory == "4Gi"


@pytest.mark.requirement("AC-RESOURCE-PRESETS")
def test_demo_manifest_resource_presets_not_in_model_extra(self) -> None:
    """Runtime resource sizing must not be silently ignored."""
    manifest = self._load_demo_manifest()
    extra_keys = set(manifest.model_extra.keys()) if manifest.model_extra else set()

    assert "resource_presets" not in extra_keys
```

- [ ] **Step 2: Write failing Helm conversion test**

Add to `packages/floe-core/tests/unit/helm/test_schemas.py`:

```python
def test_helm_values_config_uses_manifest_resource_presets() -> None:
    """Manifest resource presets can become Helm resourcePresets values."""
    from floe_core.schemas.manifest import ManifestResourcePreset, ManifestResourceSpec

    config = HelmValuesConfig.with_defaults(environment="dev").with_resource_presets(
        {
            "alpha": ManifestResourcePreset(
                requests=ManifestResourceSpec(cpu="750m", memory="1536Mi"),
                limits=ManifestResourceSpec(cpu="2", memory="4Gi"),
            )
        }
    )

    values = config.to_values_dict()

    assert values["resourcePresets"]["alpha"]["requests"]["memory"] == "1536Mi"
    assert values["resourcePresets"]["alpha"]["limits"]["memory"] == "4Gi"
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_manifest.py::TestDemoManifestObservability::test_demo_manifest_resource_presets_are_typed packages/floe-core/tests/unit/schemas/test_manifest.py::TestDemoManifestObservability::test_demo_manifest_resource_presets_not_in_model_extra packages/floe-core/tests/unit/helm/test_schemas.py::test_helm_values_config_uses_manifest_resource_presets -q
```

Expected: fail because manifest resource preset models and Helm conversion do not exist.

- [ ] **Step 4: Add manifest resource preset models**

In `packages/floe-core/src/floe_core/schemas/manifest.py`, add before `PlatformManifest`:

```python
class ManifestResourceSpec(BaseModel):
    """CPU and memory resource quantities from platform manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cpu: str = Field(description="Kubernetes CPU quantity, e.g. 500m or 2")
    memory: str = Field(description="Kubernetes memory quantity, e.g. 512Mi or 4Gi")


class ManifestResourcePreset(BaseModel):
    """Resource preset available to platform runtime components."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requests: ManifestResourceSpec = Field(description="Requested CPU and memory")
    limits: ManifestResourceSpec = Field(description="CPU and memory limits")
```

Add to `PlatformManifest`:

```python
resource_presets: dict[str, ManifestResourcePreset] | None = Field(
    default=None,
    description="Named runtime resource presets for generated platform deployment values",
)
```

Add both model names to `__all__`.

- [ ] **Step 5: Add HelmValuesConfig conversion helper**

In `packages/floe-core/src/floe_core/helm/schemas.py`, add:

```python
def with_resource_presets(
    self,
    resource_presets: Mapping[str, Any],
) -> HelmValuesConfig:
    """Return a copy using resource presets from platform manifest config."""
    converted: dict[str, ResourcePreset] = {}
    for name, preset in resource_presets.items():
        requests = getattr(preset, "requests")
        limits = getattr(preset, "limits")
        converted[name] = ResourcePreset(
            name=name,
            resources=ResourceRequirements(
                requests=ResourceSpec(cpu=requests.cpu, memory=requests.memory),
                limits=ResourceSpec(cpu=limits.cpu, memory=limits.memory),
            ),
        )
    return self.model_copy(update={"resource_presets": converted})
```

Add `Mapping` to imports from `collections.abc`.

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_manifest.py::TestDemoManifestObservability::test_demo_manifest_resource_presets_are_typed packages/floe-core/tests/unit/schemas/test_manifest.py::TestDemoManifestObservability::test_demo_manifest_resource_presets_not_in_model_extra packages/floe-core/tests/unit/helm/test_schemas.py::test_helm_values_config_uses_manifest_resource_presets -q
```

Expected: selected tests pass.

- [ ] **Step 7: Run schema and Helm unit tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_manifest.py packages/floe-core/tests/unit/helm -q
```

Expected: selected suites pass.

- [ ] **Step 8: Commit**

```bash
git add packages/floe-core/src/floe_core/schemas/manifest.py packages/floe-core/src/floe_core/helm/schemas.py packages/floe-core/tests/unit/schemas/test_manifest.py packages/floe-core/tests/unit/helm/test_schemas.py
git commit -m "feat: model manifest runtime resource presets"
```

## Task 5: Use Emitted Lineage Identity For Marquez Validation

**Files:**
- Modify: `tests/e2e/test_observability.py`

- [ ] **Step 1: Write failing helper test**

Add near the existing Marquez helper tests in `tests/e2e/test_observability.py`:

```python
@pytest.mark.developer_workflow
def test_runtime_lineage_identity_prefers_fresh_event_job() -> None:
    """Marquez validation should query the identity emitted by OpenLineage."""
    event = {
        "event": {
            "job": {
                "namespace": "customer-360",
                "name": "dbt.customer_360.mart_customer_360",
            }
        }
    }

    assert _runtime_lineage_identity_from_events([event]) == (
        "customer-360",
        "dbt.customer_360.mart_customer_360",
    )
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/e2e/test_observability.py::test_runtime_lineage_identity_prefers_fresh_event_job -q
```

Expected: fail because `_runtime_lineage_identity_from_events` does not exist.

- [ ] **Step 3: Add identity helper**

In `tests/e2e/test_observability.py`, add near `_lineage_event_job`:

```python
def _runtime_lineage_identity_from_events(
    events: list[dict[str, Any]],
) -> tuple[str, str] | None:
    """Return the first namespace/job identity emitted by fresh lineage events."""
    for event in events:
        namespace, job_name = _lineage_event_job(event)
        if namespace and job_name:
            return namespace, job_name
    return None
```

- [ ] **Step 4: Update runtime Marquez assertion**

In `test_openlineage_events_in_marquez`, after fresh lineage events are collected, derive the query identity:

```python
event_identity = _runtime_lineage_identity_from_events(fresh_lineage_events)
assert event_identity is not None, (
    "Runtime OpenLineage events were received but no job namespace/name could be extracted. "
    f"events={fresh_lineage_events[:3]}"
)
event_namespace, event_job_name = event_identity
runtime_runs = _marquez_job_runs(
    marquez_client,
    namespace=event_namespace,
    job_name=event_job_name,
)
```

Use `event_namespace` and `event_job_name` in failure messages instead of hardcoded `customer-360/customer-360` expectations.

- [ ] **Step 5: Run focused observability tests**

Run:

```bash
uv run pytest tests/e2e/test_observability.py::test_runtime_lineage_identity_prefers_fresh_event_job -q
```

Expected: selected helper test passes.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/test_observability.py
git commit -m "test: validate marquez using emitted lineage identity"
```

## Task 6: Fail Early On DevPod/Flux Source Drift

**Files:**
- Modify: `testing/k8s/setup-cluster.sh`
- Add: `tests/unit/test_flux_source_selection.py`

- [ ] **Step 1: Write shell-level unit tests**

Create `tests/unit/test_flux_source_selection.py`:

```python
"""Tests for Flux source branch selection in the Kind setup script."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "testing" / "k8s" / "setup-cluster.sh"


def _run_function(function_body: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    command = f"source {SCRIPT}; {function_body}"
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=ROOT,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def test_resolve_flux_git_branch_uses_required_branch_override() -> None:
    """FLOE_REQUIRED_FLUX_GIT_BRANCH pins the branch used by Flux."""
    result = _run_function(
        "resolve_flux_git_branch",
        {"FLOE_REQUIRED_FLUX_GIT_BRANCH": "feat/alpha-reliability-closure"},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "feat/alpha-reliability-closure"


def test_assert_flux_git_branch_rejects_drift() -> None:
    """Remote validation must fail before deploy when Flux branch drifts."""
    result = _run_function(
        "assert_flux_git_branch_matches feat/other",
        {"FLOE_REQUIRED_FLUX_GIT_BRANCH": "feat/alpha-reliability-closure"},
    )

    assert result.returncode != 0
    assert "Flux branch mismatch" in result.stderr
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/unit/test_flux_source_selection.py -q
```

Expected: fail because `FLOE_REQUIRED_FLUX_GIT_BRANCH` and `assert_flux_git_branch_matches` do not exist.

- [ ] **Step 3: Add required branch selection**

In `testing/k8s/setup-cluster.sh`, update `resolve_flux_git_branch`:

```bash
resolve_flux_git_branch() {
    if [[ -n "${FLOE_REQUIRED_FLUX_GIT_BRANCH:-}" ]]; then
        printf '%s\n' "${FLOE_REQUIRED_FLUX_GIT_BRANCH}"
        return 0
    fi
    if [[ -n "${FLOE_FLUX_GIT_BRANCH:-}" ]]; then
        printf '%s\n' "${FLOE_FLUX_GIT_BRANCH}"
        return 0
    fi
    ...
}
```

Add:

```bash
assert_flux_git_branch_matches() {
    local actual_branch="$1"
    if [[ -z "${FLOE_REQUIRED_FLUX_GIT_BRANCH:-}" ]]; then
        return 0
    fi
    if [[ "${actual_branch}" != "${FLOE_REQUIRED_FLUX_GIT_BRANCH}" ]]; then
        log_error "Flux branch mismatch: expected ${FLOE_REQUIRED_FLUX_GIT_BRANCH}, got ${actual_branch}"
        return 1
    fi
}
```

- [ ] **Step 4: Call assertion before apply**

In `deploy_via_flux`, after:

```bash
flux_git_branch=$(resolve_flux_git_branch)
```

add:

```bash
assert_flux_git_branch_matches "${flux_git_branch}"
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/unit/test_flux_source_selection.py -q
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add testing/k8s/setup-cluster.sh tests/unit/test_flux_source_selection.py
git commit -m "fix: require explicit flux source for remote validation"
```

## Task 7: Run Local Spine Validation

**Files:**
- Modify: `docs/validation/2026-04-25-alpha-reliability-validation.md`

- [ ] **Step 1: Run local quality checks**

Run:

```bash
make lint
make typecheck
uv run pytest packages/floe-iceberg/tests/unit packages/floe-core/tests/unit/schemas/test_manifest.py packages/floe-core/tests/unit/helm plugins/floe-orchestrator-dagster/tests/unit/validation tests/unit/test_flux_source_selection.py -q
```

Expected: all selected checks pass.

- [ ] **Step 2: Rebuild and deploy local test platform**

Run:

```bash
KIND_CLUSTER_NAME=floe-test make build-demo-image
FLOE_NO_FLUX=1 make kind-up
```

Expected: demo image builds, Kind platform deploys, core platform pods reach Ready.

- [ ] **Step 3: Validate Iceberg outputs in strict mode**

Run:

```bash
FLOE_E2E_ICEBERG_RECOVERY_MODE=strict uv run pytest tests/e2e/test_demo_iceberg_outputs.py -q
```

Expected: pass if no stale state exists; fail with `stale_table_metadata` or explicit missing table details if stale state remains.

- [ ] **Step 4: Validate reset/repair mode**

Run:

```bash
FLOE_E2E_ICEBERG_RECOVERY_MODE=reset uv run pytest tests/e2e/test_demo_iceberg_outputs.py -q
```

Expected: reset mode reports `recovery_mode=reset` and validates configured expected tables after a fresh materialization path has produced them.

- [ ] **Step 5: Run lineage validation after Iceberg path is stable**

Run:

```bash
uv run pytest tests/e2e/test_observability.py::TestObservability::test_openlineage_events_in_marquez -q
```

Expected: Marquez query uses emitted event namespace/job identity and either passes or fails with exact emitted/query identity.

- [ ] **Step 6: Append validation evidence**

Append a section to `docs/validation/2026-04-25-alpha-reliability-validation.md`:

```markdown
## Alpha Spine Closure Follow-Up - 2026-04-26

| Command | Result | Notes |
| --- | --- | --- |
| `make lint` | PASS | Include the final lint success line. |
| `make typecheck` | PASS | Include the mypy success line and source-file count. |
| focused unit suites | PASS | Include selected suite count and runtime. |
| local Kind deploy | PASS | Include pod readiness and image tag evidence. |
| Iceberg output validation | PASS | Include recovery mode and validated table list. |
| Marquez lineage validation | PASS | Include emitted namespace/job identity and Marquez run result. |
```

If a command fails, write `FAIL` in that command row and include the exact
failure class, failing resource, and next action instead of committing a generic
status.

- [ ] **Step 7: Commit validation update**

```bash
git add docs/validation/2026-04-25-alpha-reliability-validation.md
git commit -m "docs: record alpha spine closure validation"
```

## Task 8: Run DevPod/Hetzner Validation And Final Gates

**Files:**
- Modify: `docs/validation/2026-04-25-alpha-reliability-validation.md`

- [ ] **Step 1: Run DevPod with explicit source branch**

Run:

```bash
FLOE_REQUIRED_FLUX_GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)" make devpod-test
```

Expected: remote logs show `Applying Flux HelmRelease CRDs from ...@feat/alpha-reliability-closure` or the current branch name. If a mismatch is detected, the run fails before applying Flux resources.

- [ ] **Step 2: Capture remote readiness diagnostics**

If DevPod fails, run:

```bash
make devpod-status
```

Expected: status output identifies whether the failure is source mismatch, HelmRelease readiness, pod crash, image load, or network/tunnel availability.

- [ ] **Step 3: Append DevPod evidence**

Append to `docs/validation/2026-04-25-alpha-reliability-validation.md`:

```markdown
### DevPod/Hetzner Revalidation

- Source branch requested: `feat/alpha-reliability-closure`
- Source branch applied by Flux: `feat/alpha-reliability-closure`
- Result: PASS
- Classification: remote validation completed through E2E
- Cleanup status: Hetzner VM/workspace deleted
```

If the branch name differs because the implementation branch changes, use the
output from `git rev-parse --abbrev-ref HEAD` for both source-branch lines. If
the run fails, set `Result` to `FAIL` and classify the failure as source
selection, HelmRelease readiness, pod resources, image load, lineage, catalog
lifecycle, or external transient.

- [ ] **Step 4: Run full pre-push gate**

Run:

```bash
uv run pre-commit run --hook-stage pre-push --all-files
```

Expected: all configured pre-push hooks pass.

- [ ] **Step 5: Commit DevPod evidence if changed**

```bash
git add docs/validation/2026-04-25-alpha-reliability-validation.md
git commit -m "docs: record devpod alpha spine validation"
```

- [ ] **Step 6: Push branch**

Run:

```bash
git push
```

Expected: pre-push hook passes and branch updates on `origin/feat/alpha-reliability-closure`.

## Overall Verification Ladder

Run these before claiming completion:

```bash
make lint
make typecheck
uv run pytest packages/floe-iceberg/tests/unit packages/floe-core/tests/unit/schemas/test_manifest.py packages/floe-core/tests/unit/helm plugins/floe-orchestrator-dagster/tests/unit/validation tests/unit/test_flux_source_selection.py -q
uv run pre-commit run --hook-stage pre-push --all-files
```

Then run runtime validation:

```bash
KIND_CLUSTER_NAME=floe-test make build-demo-image
FLOE_NO_FLUX=1 make kind-up
FLOE_E2E_ICEBERG_RECOVERY_MODE=reset uv run pytest tests/e2e/test_demo_iceberg_outputs.py -q
uv run pytest tests/e2e/test_observability.py::TestObservability::test_openlineage_events_in_marquez -q
FLOE_REQUIRED_FLUX_GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)" make devpod-test
```

Completion requires either passing runtime validation or a validation document that classifies remaining failures with exact command output, namespace/job identity, table identifiers, and DevPod source branch evidence.
