# dlt Ingestion Composition Uplift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move dlt ingestion off duplicated ingestion-owned catalog fallback config and onto secret-free storage/catalog/ingestion deployment bindings.

**Architecture:** `floe-core` owns the compiled contract and composition validation. `floe-ingestion-dlt` owns translation from typed storage/catalog bindings into dlt filesystem destination kwargs and PyIceberg environment. Dagster consumes `CompiledArtifacts.deployment.ingestion` and passes the dlt binding to source construction and pipeline execution without reconstructing storage or catalog config.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, dlt filesystem source/destination, PyIceberg REST catalog configuration, Dagster assets/resources, MinIO/S3-compatible storage, Polaris REST catalog.

---

## File Structure

Core contract and resolver:

- Modify `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
  - Add `DltIngestionBinding`, `IngestionDeploymentBinding`, and `DeploymentConfig.ingestion`.
  - Add logical Polaris `warehouse` to `PolarisCatalogDeploymentBinding` so dlt does not infer it from storage paths.
  - Add secret-free validators for dlt runtime fragments.
- Modify `packages/floe-core/src/floe_core/composition/models.py`
  - Add catalog/table-format requirement fields needed by ingestion.
- Modify `packages/floe-core/src/floe_core/composition/resolver.py`
  - Validate ingestion requirements against selected storage and catalog capabilities.
- Modify `packages/floe-core/src/floe_core/plugins/ingestion.py`
  - Add optional composition/deployment-binding hooks and add `runtime_binding` to `IngestionConfig`.
- Modify `packages/floe-core/src/floe_core/compilation/resolver.py`
  - Stop requiring dlt `catalog_config` during source resolution.
- Modify `packages/floe-core/src/floe_core/compilation/stages.py`
  - Build `DeploymentConfig.ingestion` after storage/catalog composition.

dlt plugin:

- Modify `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/config.py`
  - Make `catalog_config` optional compatibility surface only, then remove it in the cleanup task.
- Modify `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
  - Add requirement declaration.
  - Add `build_deployment_binding(storage, catalog)`.
  - Prefer runtime binding in `create_pipeline()` and `run()`.
  - Remove `catalog_config` fallback in the final cleanup task.
- Modify `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
  - Populate logical Polaris warehouse in catalog deployment binding.

Dagster runtime:

- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`
  - Pass `deployment.ingestion.dlt` to ingestion resources/assets.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`
  - Accept a dlt runtime binding and use it for source filesystem config.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/ingestion.py`
  - Keep plugin config source-only; do not inject storage/catalog config into plugin config.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/__init__.py`
  - Keep the public source builder API stable while accepting binding-derived filesystem config.
- Modify `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/filesystem_sources.py`
  - Accept binding-derived source filesystem config with the same endpoint/region/path-style fields.

Demo and E2E:

- Modify `demo/manifest.yaml`
  - Remove the ingestion-owned catalog fallback config.
- Modify `tests/e2e/test_customer360_dlt_ingestion.py`
  - Use compiled `deployment.ingestion.dlt`.
- Modify `tests/e2e/test_dlt_ingestion_format_matrix.py`
  - Use compiled/binding-shaped dlt config instead of ad hoc `catalog_config`.

Tests:

- Modify `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
- Modify `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`
- Modify `packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py`
- Modify `tests/contract/test_core_to_ingestion_contract.py`
- Modify `plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py`
- Modify `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py`
- Modify `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`

## Task 1: Add Ingestion Deployment Binding Schema

**Files:**
- Modify: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Modify: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- Test: `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
- Test: `tests/contract/test_core_to_ingestion_contract.py`

- [ ] **Step 1: Write failing schema tests**

Add tests near the existing storage deployment binding tests in `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`:

```python
class TestIngestionDeploymentBinding:
    """Contract tests for secret-free dlt ingestion deployment bindings."""

    def test_dlt_binding_accepts_secret_free_runtime_fragments(self) -> None:
        from floe_core.schemas.compiled_artifacts import (
            CatalogDeploymentBinding,
            CredentialRef,
            DeploymentConfig,
            DltIngestionBinding,
            IngestionDeploymentBinding,
            PolarisCatalogDeploymentBinding,
        )

        catalog = CatalogDeploymentBinding(
            provider="polaris",
            polaris=PolarisCatalogDeploymentBinding(
                storage_type="S3",
                warehouse="floe-demo",
                default_base_location="s3://floe-iceberg",
                allowed_locations=["s3://floe-iceberg"],
                endpoint="http://localhost:8181/api/catalog",
                endpoint_internal="http://polaris:8181/api/catalog",
                path_style_access=True,
                sts_unavailable=True,
                credential_refs={
                    "accessKeyId": CredentialRef(source="none", name="none"),
                    "secretAccessKey": CredentialRef(source="none", name="none"),
                },
            ),
        )
        binding = DltIngestionBinding(
            plugin_name="dlt",
            destination="filesystem",
            table_format="iceberg",
            source_filesystem={
                "endpoint_url": "http://floe-platform-minio:9000",
                "region_name": "us-east-1",
                "s3_url_style": "path",
            },
            destination_filesystem={
                "bucket_url": "s3://floe-iceberg",
                "credentials": {
                    "endpoint_url": "http://floe-platform-minio:9000",
                    "region_name": "us-east-1",
                    "s3_url_style": "path",
                },
            },
            iceberg_catalog_env={
                "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": "polaris",
                "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
                "PYICEBERG_CATALOG__POLARIS__TYPE": "rest",
                "PYICEBERG_CATALOG__POLARIS__URI": "http://polaris:8181/api/catalog",
                "PYICEBERG_CATALOG__POLARIS__WAREHOUSE": "floe-demo",
            },
            env_refs={
                "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
            },
        )

        deployment = DeploymentConfig(
            catalog=catalog,
            ingestion=IngestionDeploymentBinding(provider="dlt", dlt=binding)
        )

        assert deployment.catalog is not None
        assert deployment.catalog.polaris.warehouse == "floe-demo"
        assert deployment.ingestion is not None
        assert deployment.ingestion.dlt.destination == "filesystem"
        assert deployment.ingestion.dlt.table_format == "iceberg"
        assert deployment.ingestion.dlt.destination_filesystem["bucket_url"] == "s3://floe-iceberg"

    def test_dlt_binding_rejects_raw_secret_material(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import DltIngestionBinding

        with pytest.raises(ValidationError, match="raw credential material"):
            DltIngestionBinding(
                plugin_name="dlt",
                destination="filesystem",
                table_format="iceberg",
                source_filesystem={},
                destination_filesystem={
                    "credentials": {
                        "aws_secret_access_key": "raw-secret-value",  # pragma: allowlist secret
                    }
                },
                iceberg_catalog_env={},
                env_refs={},
            )
```

Add this contract test to `tests/contract/test_core_to_ingestion_contract.py`:

```python
def test_compiled_artifacts_contract_includes_ingestion_deployment_binding() -> None:
    from floe_core.schemas.compiled_artifacts import (
        DeploymentConfig,
        DltIngestionBinding,
        IngestionDeploymentBinding,
    )

    deployment = DeploymentConfig(
        ingestion=IngestionDeploymentBinding(
            provider="dlt",
            dlt=DltIngestionBinding(
                plugin_name="dlt",
                destination="filesystem",
                table_format="iceberg",
                source_filesystem={"endpoint_url": "http://minio:9000"},
                destination_filesystem={"bucket_url": "s3://warehouse"},
                iceberg_catalog_env={"PYICEBERG_CATALOG__POLARIS__TYPE": "rest"},
                env_refs={"AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID"},
            ),
        )
    )

    payload = deployment.model_dump(mode="json")
    assert payload["ingestion"]["provider"] == "dlt"
    assert payload["ingestion"]["dlt"]["destination"] == "filesystem"
    assert payload["ingestion"]["dlt"]["table_format"] == "iceberg"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestIngestionDeploymentBinding tests/contract/test_core_to_ingestion_contract.py::test_compiled_artifacts_contract_includes_ingestion_deployment_binding -q
```

Expected: FAIL with import errors for `DltIngestionBinding` and `IngestionDeploymentBinding`.

- [ ] **Step 3: Add schema models**

In `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`, add these models after `CatalogDeploymentBinding` and before `DeploymentConfig`:

```python
class DltIngestionBinding(BaseModel):
    """Secret-free dlt runtime binding derived from composed platform plugins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_name: NonEmptyString
    destination: Literal["filesystem"]
    table_format: Literal["iceberg"]
    source_filesystem: dict[str, Any] = Field(default_factory=dict)
    destination_filesystem: dict[str, Any] = Field(default_factory=dict)
    iceberg_catalog_env: dict[str, str] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)

    @field_validator("source_filesystem", "destination_filesystem")
    @classmethod
    def validate_secret_free_runtime_maps(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Ensure dlt runtime maps carry config only, not credential values."""
        _assert_no_secret_material(value, "ingestion.dlt.runtime")
        return value

    @field_validator("iceberg_catalog_env")
    @classmethod
    def validate_secret_free_catalog_env(cls, value: dict[str, str]) -> dict[str, str]:
        """Ensure dlt catalog env carries only non-secret PyIceberg properties."""
        _assert_no_secret_material(value, "ingestion.dlt.iceberg_catalog_env")
        return value


class IngestionDeploymentBinding(BaseModel):
    """Secret-free ingestion deployment binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Literal["dlt"]
    dlt: DltIngestionBinding
```

Then update `DeploymentConfig`:

```python
class DeploymentConfig(BaseModel):
    """Deployment bindings derived during compilation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    storage: StorageDeploymentBinding | None = None
    catalog: CatalogDeploymentBinding | None = None
    ingestion: IngestionDeploymentBinding | None = None
```

Update `__all__` at the bottom of the file with:

```python
"DltIngestionBinding",
"IngestionDeploymentBinding",
```

- [ ] **Step 4: Add Polaris warehouse to catalog binding**

In `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`, update `PolarisCatalogDeploymentBinding`:

```python
class PolarisCatalogDeploymentBinding(BaseModel):
    """Polaris catalog-owned storage configuration for deployment renderers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    storage_type: Literal["S3"]
    warehouse: NonEmptyString
    default_base_location: NonEmptyString
    allowed_locations: list[NonEmptyString]
    endpoint: NonEmptyString
    endpoint_internal: NonEmptyString
    path_style_access: bool
    sts_unavailable: bool
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)
```

In `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`, update `build_catalog_deployment()`:

```python
config = self._require_config()
return CatalogDeploymentBinding(
    provider="polaris",
    polaris=PolarisCatalogDeploymentBinding(
        storage_type="S3",
        warehouse=config.warehouse,
        default_base_location=storage.warehouse.uri,
        allowed_locations=storage.allowed_locations,
        endpoint=storage.endpoint.external_url,
        endpoint_internal=storage.endpoint.internal_url,
        path_style_access=storage.endpoint.path_style_access,
        sts_unavailable=not storage.capabilities.sts_supported,
        credential_refs={
            "accessKeyId": access_ref,
            "secretAccessKey": secret_ref,
        },
    ),
)
```

Update existing tests that construct `PolarisCatalogDeploymentBinding` with `warehouse="floe-demo"` or another explicit logical warehouse.

- [ ] **Step 5: Run schema and contract tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestIngestionDeploymentBinding tests/contract/test_core_to_ingestion_contract.py::test_compiled_artifacts_contract_includes_ingestion_deployment_binding -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/floe-core/src/floe_core/schemas/compiled_artifacts.py plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py tests/contract/test_core_to_ingestion_contract.py plugins/floe-catalog-polaris/tests
git commit -m "Add dlt ingestion deployment binding schema"
```

## Task 2: Extend Composition Requirements for Ingestion

**Files:**
- Modify: `packages/floe-core/src/floe_core/composition/models.py`
- Modify: `packages/floe-core/src/floe_core/composition/resolver.py`
- Test: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`

- [ ] **Step 1: Write failing resolver tests**

Append these tests to `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`:

```python
def test_composition_resolver_accepts_dlt_with_minio_and_polaris() -> None:
    from floe_core.composition.models import CapabilitySet, PluginCapabilities
    from floe_core.composition.resolver import CompositionResolver

    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            path_style_access=True,
        ),
    )
    catalog = PluginCapabilities(
        plugin_type="catalog",
        plugin_name="polaris",
        capabilities=CapabilitySet(catalog_providers=["iceberg-rest"]),
    )
    ingestion = PluginRequirements(
        plugin_type="ingestion",
        plugin_name="dlt",
        requirements=RequirementSet(
            protocols=["s3-compatible", "s3"],
            credential_modes=["kubernetes-secret", "environment", "workload-identity"],
            catalog_providers=["iceberg-rest"],
            table_formats=["iceberg"],
        ),
    )

    result = CompositionResolver().validate([storage, catalog], [ingestion])

    assert result.valid
    assert result.issues == []


def test_composition_resolver_rejects_dlt_without_catalog() -> None:
    from floe_core.composition.models import CapabilitySet, PluginCapabilities
    from floe_core.composition.resolver import CompositionResolver

    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
        ),
    )
    ingestion = PluginRequirements(
        plugin_type="ingestion",
        plugin_name="dlt",
        requirements=RequirementSet(catalog_providers=["iceberg-rest"]),
    )

    result = CompositionResolver().validate([storage], [ingestion])

    assert not result.valid
    assert result.issues[0].code == "COMPOSITION_CATALOG_MISSING"
    assert result.issues[0].plugins == ["ingestion:dlt"]
```

- [ ] **Step 2: Run resolver tests to verify they fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_composition_resolver_accepts_dlt_with_minio_and_polaris packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_composition_resolver_rejects_dlt_without_catalog -q
```

Expected: FAIL because `CapabilitySet` and `RequirementSet` do not have `catalog_providers` or `table_formats`.

- [ ] **Step 3: Add requirement fields**

In `packages/floe-core/src/floe_core/composition/models.py`, update both sets:

```python
class CapabilitySet(BaseModel):
    """Structured capabilities emitted by a plugin for composition checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[str] = Field(default_factory=list)
    catalog_providers: list[str] = Field(default_factory=list)
    table_formats: list[str] = Field(default_factory=list)
    path_style_access: bool | None = None
    sts: bool | None = None


class RequirementSet(BaseModel):
    """Structured peer requirements consumed by the composition resolver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[str] = Field(default_factory=list)
    catalog_providers: list[str] = Field(default_factory=list)
    table_formats: list[str] = Field(default_factory=list)
    requires_server_side_storage_access: bool | None = None
    supports_no_sts: bool | None = None
    supports_path_style_access: bool | None = None
```

- [ ] **Step 4: Validate ingestion requirements in the resolver**

In `packages/floe-core/src/floe_core/composition/resolver.py`, update `validate()`:

```python
storage = next((item for item in capabilities if item.plugin_type == "storage"), None)
catalog = next((item for item in capabilities if item.plugin_type == "catalog"), None)

for requirement in requirements:
    if requirement.plugin_type == "catalog":
        if storage is None:
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_STORAGE_MISSING",
                    message=(
                        f"catalog {requirement.plugin_name} requires storage "
                        "capabilities but no storage plugin was selected"
                    ),
                    plugins=[requirement.ref],
                )
            )
            continue
        issues.extend(self._validate_storage_for_catalog(storage, requirement))
        continue

    if requirement.plugin_type == "ingestion":
        issues.extend(self._validate_ingestion(requirement, storage, catalog))
```

Add this helper:

```python
def _validate_ingestion(
    self,
    ingestion: PluginRequirements,
    storage: PluginCapabilities | None,
    catalog: PluginCapabilities | None,
) -> list[CompositionIssue]:
    """Validate ingestion requirements against selected storage and catalog."""
    issues: list[CompositionIssue] = []
    if storage is None:
        issues.append(
            CompositionIssue(
                severity="error",
                code="COMPOSITION_STORAGE_MISSING",
                message=(
                    f"ingestion {ingestion.plugin_name} requires storage "
                    "capabilities but no storage plugin was selected"
                ),
                plugins=[ingestion.ref],
            )
        )
    else:
        issues.extend(self._validate_storage_for_catalog(storage, ingestion))

    required_catalogs = list(ingestion.requirements.catalog_providers)
    if required_catalogs and catalog is None:
        issues.append(
            CompositionIssue(
                severity="error",
                code="COMPOSITION_CATALOG_MISSING",
                message=(
                    f"ingestion {ingestion.plugin_name} requires one of catalog providers "
                    f"{required_catalogs}; no catalog plugin was selected"
                ),
                plugins=[ingestion.ref],
            )
        )
    elif required_catalogs and catalog is not None:
        provided_catalogs = list(catalog.capabilities.catalog_providers)
        if not set(provided_catalogs).intersection(required_catalogs):
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_CATALOG_UNSUPPORTED",
                    message=(
                        f"ingestion {ingestion.plugin_name} requires one of catalog providers "
                        f"{required_catalogs}; catalog {catalog.plugin_name} provides "
                        f"{provided_catalogs}"
                    ),
                    plugins=[catalog.ref, ingestion.ref],
                )
            )

    return issues
```

- [ ] **Step 5: Run resolver tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_composition_resolver_accepts_dlt_with_minio_and_polaris packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_composition_resolver_rejects_dlt_without_catalog -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/floe-core/src/floe_core/composition/models.py packages/floe-core/src/floe_core/composition/resolver.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py
git commit -m "Validate ingestion composition requirements"
```

## Task 3: Add Ingestion Plugin Binding Hooks and Compile dlt Binding

**Files:**
- Modify: `packages/floe-core/src/floe_core/plugins/ingestion.py`
- Modify: `packages/floe-core/src/floe_core/compilation/resolver.py`
- Modify: `packages/floe-core/src/floe_core/compilation/stages.py`
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Test: `packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py`
- Test: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`

- [ ] **Step 1: Write failing compilation tests**

Update `_plugins_with_ingestion_config()` in `packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py` so dlt has no `catalog_config`:

```python
def _plugins_with_ingestion_config() -> ResolvedPlugins:
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0", config={}),
        orchestrator=PluginRef(type="dagster", version="1.5.0", config={}),
        ingestion=PluginRef(
            type="dlt",
            version="0.1.0",
            config={"retry_config": {"max_retries": 5, "initial_delay_seconds": 2.0}},
        ),
    )
```

Replace `test_resolve_ingestion_config_preserves_manifest_config()` with:

```python
def test_resolve_ingestion_config_preserves_retry_config_without_catalog_config() -> None:
    """Product sources merge without requiring duplicated dlt catalog config."""
    from floe_core.compilation.resolver import resolve_ingestion_config

    resolved = resolve_ingestion_config(_spec_with_ingestion(), _plugins_with_ingestion_config())

    assert resolved.ingestion is not None
    assert resolved.ingestion.config is not None
    assert "catalog_config" not in resolved.ingestion.config
    assert resolved.ingestion.config["retry_config"] == {
        "max_retries": 5,
        "initial_delay_seconds": 2.0,
    }
```

Replace `test_resolve_ingestion_config_fails_without_dlt_destination_catalog_config()` with:

```python
def test_resolve_ingestion_config_does_not_validate_destination_catalog_config() -> None:
    """Destination compatibility is handled by deployment composition."""
    from floe_core.compilation.resolver import resolve_ingestion_config

    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0", config={}),
        orchestrator=PluginRef(type="dagster", version="1.5.0", config={}),
        ingestion=PluginRef(type="dlt", version="0.1.0", config={}),
    )

    resolved = resolve_ingestion_config(_spec_with_ingestion(), plugins)

    assert resolved.ingestion is not None
    assert resolved.ingestion.config is not None
    assert resolved.ingestion.config["sources"][0]["source_type"] == "filesystem"
    assert "catalog_config" not in resolved.ingestion.config
```

Append to `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`:

```python
def test_demo_compile_emits_dlt_ingestion_deployment_binding() -> None:
    """Demo compilation derives dlt binding from storage/catalog composition."""
    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        ROOT / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.deployment is not None
    assert artifacts.deployment.ingestion is not None
    dlt = artifacts.deployment.ingestion.dlt
    assert dlt.destination == "filesystem"
    assert dlt.table_format == "iceberg"
    assert dlt.destination_filesystem["bucket_url"] == "s3://floe-iceberg"
    assert dlt.destination_filesystem["credentials"]["endpoint_url"] == (
        "http://floe-platform-minio:9000"
    )
    assert dlt.iceberg_catalog_env["ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE"] == "rest"
    assert dlt.iceberg_catalog_env["PYICEBERG_CATALOG__POLARIS__WAREHOUSE"] == "floe-demo"
    assert artifacts.deployment.catalog is not None
    assert artifacts.deployment.catalog.polaris.warehouse == "floe-demo"
    assert artifacts.plugins.ingestion is not None
    assert artifacts.plugins.ingestion.config is not None
    assert "catalog_config" not in artifacts.plugins.ingestion.config
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_demo_compile_emits_dlt_ingestion_deployment_binding -q
```

Expected: FAIL because `resolve_ingestion_config()` still requires `catalog_config`, and compile does not build `deployment.ingestion`.

- [ ] **Step 3: Add ingestion hooks in core**

In `packages/floe-core/src/floe_core/plugins/ingestion.py`, update imports:

```python
from collections.abc import Mapping
```

Update `IngestionConfig`:

```python
@dataclass
class IngestionConfig:
    """Configuration for an ingestion pipeline."""

    source_type: str
    source_config: dict[str, Any] = field(default_factory=lambda: {})
    destination_table: str = ""
    write_mode: str = "append"
    schema_contract: str = "evolve"
    runtime_binding: Mapping[str, Any] | None = None
```

Add methods to `IngestionPlugin`:

```python
def get_composition_requirements(self) -> Any:
    """Return peer plugin requirements for deployment composition."""
    return None

def build_deployment_binding(
    self,
    *,
    storage: Any,
    catalog: Any,
) -> Any:
    """Build secret-free ingestion deployment binding from composed plugins."""
    raise NotImplementedError(
        f"{self.name} does not implement ingestion deployment binding generation"
    )
```

- [ ] **Step 4: Stop source resolution from requiring destination config**

In `packages/floe-core/src/floe_core/compilation/resolver.py`, remove the dlt destination fallback validation call from `resolve_ingestion_config()`:

```python
existing_config = dict(plugins.ingestion.config or {})
existing_config["sources"] = [
    _resolve_ingestion_source_config(source) for source in spec.ingestion.sources
]
```

Leave the fallback validation helper in the file only until Task 8 removes the fallback tests and dead code.

- [ ] **Step 5: Implement dlt composition hooks**

In `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`, add imports:

```python
from floe_core.composition.models import PluginRequirements, RequirementSet
from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    DltIngestionBinding,
    IngestionDeploymentBinding,
    StorageDeploymentBinding,
)
```

Add methods to `DltIngestionPlugin`:

```python
def get_composition_requirements(self) -> PluginRequirements:
    """Return storage and catalog requirements for dlt Iceberg ingestion."""
    return PluginRequirements(
        plugin_type="ingestion",
        plugin_name=self.name,
        requirements=RequirementSet(
            protocols=["s3-compatible", "s3"],
            credential_modes=["kubernetes-secret", "environment", "workload-identity"],
            catalog_providers=["iceberg-rest"],
            table_formats=["iceberg"],
        ),
    )

def build_deployment_binding(
    self,
    *,
    storage: StorageDeploymentBinding,
    catalog: CatalogDeploymentBinding,
) -> IngestionDeploymentBinding:
    """Translate composed storage/catalog bindings into dlt runtime config."""
    if storage.warehouse is None:
        raise PipelineConfigurationError("dlt ingestion requires storage warehouse binding")
    if catalog.provider != "polaris":
        raise PipelineConfigurationError(
            f"dlt ingestion currently supports polaris catalog bindings, got {catalog.provider!r}"
        )

    source_filesystem = {
        "endpoint_url": storage.endpoint.internal_url,
        "region_name": storage.endpoint.region,
        "s3_url_style": "path" if storage.endpoint.path_style_access else "virtual",
    }
    destination_filesystem = {
        "bucket_url": storage.warehouse.uri,
        "credentials": {
            "endpoint_url": storage.endpoint.internal_url,
            "region_name": storage.endpoint.region,
        },
    }
    if storage.endpoint.path_style_access:
        destination_filesystem["credentials"]["s3_url_style"] = "path"

    iceberg_catalog_env = self._iceberg_environment(
        {
            "catalog_name": "polaris",
            "uri": catalog.polaris.endpoint_internal,
            "warehouse": catalog.polaris.warehouse,
            "s3_endpoint": storage.endpoint.internal_url,
            "s3_region": storage.endpoint.region,
            "s3_path_style_access": storage.endpoint.path_style_access,
        }
    )

    return IngestionDeploymentBinding(
        provider="dlt",
        dlt=DltIngestionBinding(
            plugin_name=self.name,
            destination="filesystem",
            table_format="iceberg",
            source_filesystem=source_filesystem,
            destination_filesystem=destination_filesystem,
            iceberg_catalog_env=iceberg_catalog_env,
            env_refs=dict(storage.runtime.env_refs),
        ),
    )
```

- [ ] **Step 6: Build ingestion binding during compile**

In `packages/floe-core/src/floe_core/compilation/stages.py`, rename `_build_storage_deployment_binding()` to `_build_deployment_bindings()` or keep the existing name and extend it. Add catalog capabilities:

```python
catalog_capabilities = PluginCapabilities(
    plugin_type="catalog",
    plugin_name=catalog_plugin.name,
    capabilities=CapabilitySet(
        catalog_providers=["iceberg-rest"] if catalog_plugin.name == "polaris" else [],
        table_formats=["iceberg"],
    ),
)
```

After catalog binding is built, add ingestion binding:

```python
ingestion_binding = None
if plugins.ingestion is not None:
    try:
        registry.configure(
            PluginType.INGESTION,
            plugins.ingestion.type,
            plugins.ingestion.config or {},
        )
        ingestion_plugin = registry.get(PluginType.INGESTION, plugins.ingestion.type)
    except PluginError as exc:
        raise CompilationException(
            CompilationError(
                stage=CompilationStage.RESOLVE,
                code="E201",
                message=f"Ingestion plugin {plugins.ingestion.type!r} could not be resolved",
                suggestion="Install the ingestion plugin package and verify plugins.ingestion.type",
                context={"ingestion_plugin": plugins.ingestion.type},
            )
        ) from exc

    requirements = getattr(ingestion_plugin, "get_composition_requirements", lambda: None)()
    if requirements is not None:
        composition = CompositionResolver().validate(
            [storage_capabilities, catalog_capabilities],
            [requirements],
        )
        if not composition.valid:
            issues = [issue.model_dump(mode="json") for issue in composition.issues]
            first_issue = composition.issues[0]
            raise CompilationException(
                CompilationError(
                    stage=CompilationStage.RESOLVE,
                    code=first_issue.code,
                    message=first_issue.message,
                    suggestion=(
                        "Choose compatible storage, catalog, and ingestion plugins, "
                        "or update their configuration so ingestion requirements are satisfied."
                    ),
                    context={
                        "composition_issues": issues,
                        "storage_plugin": plugins.storage.type,
                        "catalog_plugin": plugins.catalog.type,
                        "ingestion_plugin": plugins.ingestion.type,
                    },
                )
            )
    if catalog_binding is not None:
        ingestion_binding = ingestion_plugin.build_deployment_binding(
            storage=storage_binding,
            catalog=catalog_binding,
        )

return DeploymentConfig(
    storage=storage_binding,
    catalog=catalog_binding,
    ingestion=ingestion_binding,
)
```

- [ ] **Step 7: Run compilation tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_demo_compile_emits_dlt_ingestion_deployment_binding -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add packages/floe-core/src/floe_core/plugins/ingestion.py packages/floe-core/src/floe_core/compilation/resolver.py packages/floe-core/src/floe_core/compilation/stages.py plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py
git commit -m "Compile dlt ingestion deployment binding"
```

## Task 4: Make dlt Runtime Prefer Deployment Binding

**Files:**
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/config.py`
- Test: `plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py`

- [ ] **Step 1: Write failing dlt binding runtime tests**

Add to `plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py`:

```python
def _runtime_binding() -> dict[str, Any]:
    return {
        "destination": "filesystem",
        "table_format": "iceberg",
        "source_filesystem": {
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
            "s3_url_style": "path",
        },
        "destination_filesystem": {
            "bucket_url": "s3://floe-iceberg",
            "credentials": {
                "endpoint_url": "http://minio:9000",
                "region_name": "us-east-1",
                "s3_url_style": "path",
            },
        },
        "iceberg_catalog_env": {
            "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": "polaris",
            "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
            "PYICEBERG_CATALOG__POLARIS__TYPE": "rest",
            "PYICEBERG_CATALOG__POLARIS__URI": "http://polaris:8181/api/catalog",
            "PYICEBERG_CATALOG__POLARIS__WAREHOUSE": "floe-demo",
        },
        "env_refs": {
            "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
        },
    }


def test_create_pipeline_prefers_runtime_binding_over_catalog_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination_calls: list[dict[str, Any]] = []
    pipeline_calls: list[dict[str, Any]] = []
    fake_destination = object()

    def fake_filesystem(**kwargs: Any) -> object:
        destination_calls.append(kwargs)
        return fake_destination

    def fake_pipeline(**kwargs: Any) -> SimpleNamespace:
        pipeline_calls.append(kwargs)
        return SimpleNamespace(pipeline_name=kwargs["pipeline_name"])

    import dlt
    import dlt.destinations

    monkeypatch.setattr(dlt.destinations, "filesystem", fake_filesystem)
    monkeypatch.setattr(dlt, "pipeline", fake_pipeline)

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"bucket": "legacy-bucket"}))
    plugin.startup()

    pipeline = plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={},
            destination_table="bronze.orders",
            runtime_binding=_runtime_binding(),
        )
    )

    assert pipeline.pipeline_name == "ingest_orders"
    assert destination_calls == [_runtime_binding()["destination_filesystem"]]
    assert pipeline_calls[0]["destination"] is fake_destination
    assert getattr(pipeline, "_floe_dlt_runtime_binding") == _runtime_binding()


def test_run_applies_runtime_binding_catalog_env(monkeypatch: pytest.MonkeyPatch) -> None:
    observations: dict[str, str | None] = {}

    class FakePipeline:
        pipeline_name = "orders"
        _floe_dlt_runtime_binding = _runtime_binding()

        def run(self, _source: object, **_kwargs: Any) -> object:
            observations["catalog"] = os.environ.get("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME")
            observations["uri"] = os.environ.get("PYICEBERG_CATALOG__POLARIS__URI")
            return SimpleNamespace(metrics={})

    plugin = DltIngestionPlugin()
    plugin.startup()

    result = plugin.run(FakePipeline(), source=object(), table_name="orders")

    assert result.success
    assert observations == {
        "catalog": "polaris",
        "uri": "http://polaris:8181/api/catalog",
    }
    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py::test_create_pipeline_prefers_runtime_binding_over_catalog_config plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py::test_run_applies_runtime_binding_catalog_env -q
```

Expected: FAIL because `create_pipeline()` ignores `runtime_binding`.

- [ ] **Step 3: Add runtime binding helpers**

In `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`, add:

```python
def _pipeline_runtime_binding(self, config: IngestionConfig) -> dict[str, Any]:
    binding = config.runtime_binding
    return dict(binding) if isinstance(binding, Mapping) else {}

def _destination_config_from_binding(self, binding: Mapping[str, Any]) -> dict[str, Any]:
    destination = binding.get("destination_filesystem")
    return dict(destination) if isinstance(destination, Mapping) else {}
```

Update `create_pipeline()` to require the runtime deployment binding:

```python
runtime_binding = self._pipeline_runtime_binding(config)
destination_config = self._destination_config_from_binding(runtime_binding)
if not destination_config:
    raise PipelineConfigurationError(
        "dlt runtime binding is required for dlt ingestion pipelines",
        source_type=config.source_type,
        destination_table=config.destination_table,
    )

from dlt.destinations import filesystem

pipeline_kwargs["destination"] = filesystem(**destination_config)
```

After pipeline creation:

```python
if runtime_binding:
    pipeline._floe_dlt_runtime_binding = runtime_binding
```

Update `run()`:

```python
runtime_binding = getattr(pipeline, "_floe_dlt_runtime_binding", None)
if isinstance(runtime_binding, Mapping):
    with self._temporary_runtime_binding_environment(runtime_binding):
        load_info = pipeline.run(source, **run_kwargs)
```

Add the environment helper:

```python
@contextmanager
def _temporary_runtime_binding_environment(self, binding: Mapping[str, Any]) -> Any:
    catalog_env = binding.get("iceberg_catalog_env")
    plugin_env = dict(catalog_env) if isinstance(catalog_env, Mapping) else {}
    if not plugin_env:
        yield
        return

    with self._iceberg_env_lock:
        previous = {str(key): os.environ.get(str(key)) for key in plugin_env}
        try:
            os.environ.update({str(key): str(value) for key, value in plugin_env.items()})
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
```

- [ ] **Step 4: Run dlt unit tests**

Run:

```bash
uv run pytest plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/config.py plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py
git commit -m "Use dlt runtime binding for pipeline execution"
```

## Task 5: Pass Ingestion Binding Through Dagster Runtime

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/__init__.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/filesystem_sources.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`

- [ ] **Step 1: Write failing Dagster source-construction test**

Add to `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py`:

```python
def test_build_filesystem_source_uses_binding_source_filesystem_config(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dagster source construction uses compiled binding-derived filesystem config."""
    from floe_orchestrator_dagster.ingestion import build_dlt_source

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "env-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "env-secret")  # pragma: allowlist secret

    source = build_dlt_source(
        _source_config(path="s3://floe-iceberg/landing/customers/"),
        project_dir=tmp_path,
        filesystem_config={
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
            "s3_url_style": "path",
        },
    )

    assert source.parent is not None
    assert source.parent.kwargs["credentials"] == {
        "aws_access_key_id": "env-access",
        "aws_secret_access_key": "env-secret",  # pragma: allowlist secret
        "endpoint_url": "http://minio:9000",
        "region_name": "us-east-1",
        "s3_url_style": "path",
    }
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py::test_build_filesystem_source_uses_binding_source_filesystem_config -q
```

Expected: FAIL if the source adapter only reads `s3_endpoint` and `s3_region`.

- [ ] **Step 3: Update filesystem source adapter**

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/filesystem_sources.py`, update `_object_store_credentials()`:

```python
endpoint_url = _first_config_value(
    filesystem_config,
    "endpoint_url",
    "s3_endpoint",
    "endpoint",
    "minio_endpoint",
)
if endpoint_url is not None:
    credentials["endpoint_url"] = str(endpoint_url)
region_name = os.environ.get("AWS_REGION") or _first_config_value(
    filesystem_config,
    "region_name",
    "s3_region",
    "region",
)
if region_name is not None:
    credentials["region_name"] = str(region_name)
path_style = filesystem_config.get(
    "s3_path_style_access",
    filesystem_config.get(
        "path_style_access",
        filesystem_config.get("s3_url_style") == "path" or endpoint_url is not None,
    ),
)
if path_style:
    credentials["s3_url_style"] = "path"
```

- [ ] **Step 4: Pass binding through asset creation**

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`, change function signatures:

```python
def create_ingestion_assets(
    ingestion_ref: PluginRef,
    *,
    project_dir: Path,
    runtime_binding: Mapping[str, Any] | None = None,
) -> list[AssetsDefinition]:
```

Replace filesystem config lookup:

```python
filesystem_config = _filesystem_config(ingestion_config, runtime_binding=runtime_binding)
```

Update helper:

```python
def _filesystem_config(
    ingestion_config: Mapping[str, Any],
    *,
    runtime_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return platform-owned filesystem connection settings for dlt sources."""
    if runtime_binding is not None:
        source_filesystem = runtime_binding.get("source_filesystem")
        if isinstance(source_filesystem, Mapping):
            return dict(source_filesystem)
    catalog_config = ingestion_config.get("catalog_config")
    return dict(catalog_config) if isinstance(catalog_config, Mapping) else {}
```

When building `IngestionConfig` inside `_create_ingestion_asset()`, pass runtime binding:

```python
config = IngestionConfig(
    source_type=source_config["source_type"],
    source_config=source_config.get("source_config") or {},
    destination_table=source_config["destination_table"],
    write_mode=source_config.get("write_mode", "append"),
    schema_contract=source_config.get("schema_contract", "evolve"),
    runtime_binding=runtime_binding,
)
```

Add `runtime_binding` to `_create_ingestion_asset()` parameters and pass it from `create_ingestion_assets()`.

- [ ] **Step 5: Pass binding from runtime definitions**

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`, update the ingestion block:

```python
ingestion_runtime_binding = None
deployment = getattr(artifacts, "deployment", None)
if deployment is not None and getattr(deployment, "ingestion", None) is not None:
    ingestion_runtime_binding = deployment.ingestion.dlt.model_dump(mode="python")

resources.update(create_ingestion_resources(plugins.ingestion))
assets.extend(
    create_ingestion_assets(
        plugins.ingestion,
        project_dir=project_dir,
        runtime_binding=ingestion_runtime_binding,
    )
)
```

- [ ] **Step 6: Add loader/runtime unit coverage**

In `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`, add a test that patches `create_ingestion_assets` and asserts the runtime binding is passed:

```python
def test_runtime_passes_compiled_ingestion_binding_to_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    from floe_core.schemas.compiled_artifacts import (
        DeploymentConfig,
        DltIngestionBinding,
        IngestionDeploymentBinding,
    )
    from floe_orchestrator_dagster.runtime import create_definitions_from_artifacts

    captured: dict[str, Any] = {}

    def fake_create_ingestion_assets(ingestion_ref: Any, *, project_dir: Path, runtime_binding: Any) -> list[Any]:
        captured["runtime_binding"] = runtime_binding
        return []

    monkeypatch.setattr(
        "floe_orchestrator_dagster.assets.ingestion.create_ingestion_assets",
        fake_create_ingestion_assets,
    )

    artifacts = _minimal_artifacts_with_ingestion()
    artifacts = artifacts.model_copy(
        update={
            "deployment": DeploymentConfig(
                ingestion=IngestionDeploymentBinding(
                    provider="dlt",
                    dlt=DltIngestionBinding(
                        plugin_name="dlt",
                        destination="filesystem",
                        table_format="iceberg",
                        source_filesystem={"endpoint_url": "http://minio:9000"},
                        destination_filesystem={"bucket_url": "s3://warehouse"},
                        iceberg_catalog_env={},
                        env_refs={},
                    ),
                )
            )
        }
    )

    create_definitions_from_artifacts(artifacts, project_dir=Path("."))

    assert captured["runtime_binding"]["source_filesystem"]["endpoint_url"] == "http://minio:9000"
```

Use the existing test helper in `test_loader.py` if it already builds minimal artifacts; otherwise define `_minimal_artifacts_with_ingestion()` in the test file by following the nearby fixture pattern.

- [ ] **Step 7: Run Dagster tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py plugins/floe-orchestrator-dagster/tests/unit/test_loader.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/__init__.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/ingestion/filesystem_sources.py plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py plugins/floe-orchestrator-dagster/tests/unit/test_loader.py
git commit -m "Pass dlt ingestion binding through Dagster runtime"
```

## Task 6: Remove Demo Manifest Duplication and Update Contract Tests

**Files:**
- Modify: `demo/manifest.yaml`
- Modify: `packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py`
- Modify: `tests/contract/test_core_to_ingestion_contract.py`
- Modify: `tests/e2e/test_customer360_dlt_ingestion.py`
- Modify: `tests/e2e/test_dlt_ingestion_format_matrix.py`

- [ ] **Step 1: Write failing no-duplication assertions**

Add to `tests/contract/test_core_to_ingestion_contract.py`:

```python
def test_demo_compile_has_no_ingestion_catalog_config_duplication() -> None:
    from pathlib import Path

    from floe_core.compilation.stages import compile_pipeline

    root = Path(__file__).resolve().parents[2]
    artifacts = compile_pipeline(
        root / "demo" / "customer-360" / "floe.yaml",
        root / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.plugins.ingestion is not None
    assert artifacts.plugins.ingestion.config is not None
    assert "catalog_config" not in artifacts.plugins.ingestion.config
    assert artifacts.deployment is not None
    assert artifacts.deployment.ingestion is not None
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/contract/test_core_to_ingestion_contract.py::test_demo_compile_has_no_ingestion_catalog_config_duplication -q
```

Expected: FAIL until `demo/manifest.yaml` no longer contains ingestion `catalog_config`.

- [ ] **Step 3: Remove duplicated manifest config**

In `demo/manifest.yaml`, replace the ingestion section with:

```yaml
  # Ingestion: dlt loads data-engineer-owned sources into Iceberg via composed storage/catalog
  ingestion:
    type: dlt
    version: 0.1.0
    config:
      retry_config:
        max_retries: 3
        initial_delay_seconds: 1.0
```

- [ ] **Step 4: Update E2E helpers to read binding**

In `tests/e2e/test_customer360_dlt_ingestion.py`, add:

```python
def _dlt_runtime_binding(artifacts: CompiledArtifacts) -> dict[str, Any]:
    """Return compiled dlt runtime binding with clear test failures."""
    assert artifacts.deployment is not None, "Customer 360 artifacts should include deployment"
    assert artifacts.deployment.ingestion is not None, (
        "Customer 360 artifacts should include dlt deployment binding"
    )
    return artifacts.deployment.ingestion.dlt.model_dump(mode="python")
```

Update helper call sites so plugin/source execution uses:

```python
runtime_binding = _dlt_runtime_binding(artifacts)
```

When creating `IngestionConfig`, pass:

```python
runtime_binding=runtime_binding
```

When building dlt source, pass:

```python
filesystem_config=runtime_binding["source_filesystem"]
```

When selecting the bucket for cleanup, use:

```python
bucket = artifacts.deployment.storage.warehouse.bucket
```

- [ ] **Step 5: Update format matrix helpers to accept binding-shaped config**

In `tests/e2e/test_dlt_ingestion_format_matrix.py`, keep `_catalog_config()` only until Task 8. Add:

```python
def _runtime_binding(catalog_config: dict[str, Any]) -> dict[str, Any]:
    """Build a binding-shaped runtime config for matrix tests."""
    return {
        "destination": "filesystem",
        "table_format": "iceberg",
        "source_filesystem": {
            "endpoint_url": str(catalog_config["s3_endpoint"]),
            "region_name": str(catalog_config["s3_region"]),
            "s3_url_style": "path",
        },
        "destination_filesystem": {
            "bucket_url": f"s3://{catalog_config['bucket']}",
            "credentials": {
                "endpoint_url": str(catalog_config["s3_endpoint"]),
                "region_name": str(catalog_config["s3_region"]),
                "s3_url_style": "path",
            },
        },
        "iceberg_catalog_env": DltIngestionPlugin()._iceberg_environment(catalog_config),
        "env_refs": {
            "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
        },
    }
```

Change `_run_source()` signature:

```python
def _run_source(
    plugin: DltIngestionPlugin,
    source: IngestionSourceConfig,
    *,
    runtime_binding: dict[str, Any],
) -> IngestionResult:
```

Use the binding:

```python
pipeline = plugin.create_pipeline(
    IngestionConfig(
        source_type=source.source_type,
        source_config=source.source_config,
        destination_table=source.destination_table,
        write_mode=source.write_mode,
        schema_contract=source.schema_contract,
        runtime_binding=runtime_binding,
    )
)
dlt_source = build_dlt_source(
    source_dict,
    project_dir=PROJECT_ROOT,
    filesystem_config=runtime_binding["source_filesystem"],
)
```

- [ ] **Step 6: Run contract and focused E2E collect checks**

Run:

```bash
uv run pytest tests/contract/test_core_to_ingestion_contract.py::test_demo_compile_has_no_ingestion_catalog_config_duplication --collect-only -q
uv run pytest tests/e2e/test_customer360_dlt_ingestion.py tests/e2e/test_dlt_ingestion_format_matrix.py --collect-only -q
```

Expected: PASS collection.

- [ ] **Step 7: Commit**

```bash
git add demo/manifest.yaml packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py tests/contract/test_core_to_ingestion_contract.py tests/e2e/test_customer360_dlt_ingestion.py tests/e2e/test_dlt_ingestion_format_matrix.py
git commit -m "Remove duplicated dlt ingestion catalog config"
```

## Task 7: Prove Binding Path with Focused Unit and Contract Suite

**Files:**
- Modify tests only if this task finds failing assertions from previous tasks.

- [ ] **Step 1: Run focused ingestion suite**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/schemas/test_floe_spec_ingestion.py \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestIngestionDeploymentBinding \
  packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py \
  packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py \
  tests/contract/test_core_to_ingestion_contract.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_loader.py \
  plugins/floe-ingestion-dlt/tests/unit/test_config.py \
  plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Fix any focused failures in the smallest owning file**

Use these ownership rules:

- Schema validation failure: fix `compiled_artifacts.py` or the schema test.
- Composition failure: fix `composition/models.py`, `composition/resolver.py`, or `compilation/stages.py`.
- dlt destination failure: fix `floe_ingestion_dlt/plugin.py`.
- Dagster source failure: fix `assets/ingestion.py` or `ingestion/filesystem_sources.py`.
- Demo compile failure: fix `demo/manifest.yaml` or compile binding construction.

Do not change unrelated tests or weaken assertions.

- [ ] **Step 3: Re-run focused suite**

Run the same command from Step 1.

Expected: PASS.

- [ ] **Step 4: Commit focused fixes if any files changed**

If `git status --short` shows changes:

```bash
git add packages/floe-core plugins/floe-ingestion-dlt plugins/floe-orchestrator-dagster tests/contract demo/manifest.yaml
git commit -m "Stabilize dlt ingestion binding tests"
```

If no files changed, do not create an empty commit.

## Task 8: Remove `catalog_config` Compatibility Fallback

**Files:**
- Modify: `packages/floe-core/src/floe_core/compilation/resolver.py`
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/config.py`
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`
- Modify: tests that still mention ingestion-owned `catalog_config`

- [ ] **Step 1: Find remaining fallback references**

Run:

```bash
rg -n "catalog_config|_validate_dlt_destination_config|_pipeline_catalog_config|_configured_catalog_config|_floe_iceberg_catalog_config" \
  packages/floe-core/src packages/floe-core/tests plugins/floe-ingestion-dlt/src plugins/floe-ingestion-dlt/tests plugins/floe-orchestrator-dagster/src plugins/floe-orchestrator-dagster/tests tests/contract tests/e2e demo
```

Expected: output only references that this task removes or keeps for external catalog plugin config. Ingestion-owned catalog fallback references must be removed.

- [ ] **Step 2: Remove core fallback validation**

In `packages/floe-core/src/floe_core/compilation/resolver.py`, delete:

```python
def _validate_dlt_destination_config(spec: FloeSpec, config: dict[str, object]) -> None:
    ...
```

Also delete unused constants used only by that function.

- [ ] **Step 3: Remove dlt config field**

In `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/config.py`, remove `catalog_config` from `DltIngestionConfig`:

```python
class DltIngestionConfig(BaseModel):
    """Top-level configuration for the dlt ingestion plugin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sources: list[IngestionSourceConfig] = Field(
        ...,
        min_length=1,
        description="List of ingestion source configurations",
    )
    retry_config: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry behavior configuration for transient errors",
    )
```

- [ ] **Step 4: Remove dlt plugin catalog fallback**

In `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`, remove these fallback helpers:

```python
def _configured_catalog_config(self) -> dict[str, Any]:
    ...

def _pipeline_catalog_config(self, config: IngestionConfig) -> dict[str, Any]:
    ...
```

Update `create_pipeline()` so configured pipelines require runtime binding:

```python
runtime_binding = self._pipeline_runtime_binding(config)
destination_config = self._destination_config_from_binding(runtime_binding)
if not destination_config:
    raise PipelineConfigurationError(
        "dlt runtime binding is required for dlt ingestion pipelines",
        source_type=config.source_type,
        destination_table=config.destination_table,
    )

from dlt.destinations import filesystem

pipeline_kwargs["destination"] = filesystem(**destination_config)
```

Remove use of the pipeline catalog env fallback in `run()`. The only dlt Iceberg environment path should be `_temporary_runtime_binding_environment()`.

Keep `get_destination_config()` only if a public test still covers it as a pure translator. If kept, document it as legacy utility and do not call it from runtime. If no caller remains, delete it and its tests.

- [ ] **Step 5: Remove Dagster ingestion `catalog_config` fallback**

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`, replace `_filesystem_config()` with:

```python
def _filesystem_config(
    *,
    runtime_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return binding-owned filesystem connection settings for dlt sources."""
    if runtime_binding is None:
        return {}
    source_filesystem = runtime_binding.get("source_filesystem")
    return dict(source_filesystem) if isinstance(source_filesystem, Mapping) else {}
```

Update the call site:

```python
filesystem_config = _filesystem_config(runtime_binding=runtime_binding)
```

- [ ] **Step 6: Delete fallback tests**

Remove or rewrite tests whose only purpose is `catalog_config` fallback:

- `test_destination_config_matches_dlt_filesystem_iceberg_setup`
- `test_destination_config_accepts_explicit_bucket_url`
- `test_configured_create_pipeline_requires_catalog_config`
- `test_run_serializes_pyiceberg_env_for_concurrent_catalog_configs`
- `test_create_pipeline_preserves_plugin_env_when_existing_value_is_present`

Replace with binding equivalents when the behavior still matters:

```python
def test_configured_create_pipeline_requires_runtime_binding() -> None:
    plugin = DltIngestionPlugin()
    plugin.configure(
        DltIngestionConfig(
            sources=[
                IngestionSourceConfig(
                    name="orders",
                    source_type="filesystem",
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
                source_config={},
                destination_table="bronze.orders",
            )
        )
```

- [ ] **Step 7: Re-run reference search**

Run:

```bash
rg -n "plugins\\.ingestion\\.config\\.catalog_config|_validate_dlt_destination_config|_pipeline_catalog_config|_configured_catalog_config|_floe_iceberg_catalog_config" . \
  --glob '!docs/superpowers/plans/2026-05-07-dlt-ingestion-composition-uplift.md'
```

Expected: no output.

- [ ] **Step 8: Run focused suite**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/compilation/test_ingestion_resolution.py \
  tests/contract/test_core_to_ingestion_contract.py \
  plugins/floe-ingestion-dlt/tests/unit/test_config.py \
  plugins/floe-ingestion-dlt/tests/unit/test_destination_config.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_filesystem_sources.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_loader.py \
  -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add packages/floe-core/src/floe_core/compilation/resolver.py plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/config.py plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py packages/floe-core/tests plugins/floe-ingestion-dlt/tests plugins/floe-orchestrator-dagster/tests tests/contract tests/e2e demo/manifest.yaml
git commit -m "Remove dlt catalog_config fallback"
```

## Task 9: E2E Binding Path and Final Verification

**Files:**
- Modify E2E tests only if binding-path assertions need adjustment.

- [ ] **Step 1: Run E2E collection**

Run:

```bash
uv run pytest tests/e2e/test_customer360_dlt_ingestion.py tests/e2e/test_dlt_ingestion_format_matrix.py --collect-only -q
```

Expected: PASS collection.

- [ ] **Step 2: Run E2E when local services are reachable**

Run:

```bash
uv run pytest tests/e2e/test_customer360_dlt_ingestion.py tests/e2e/test_dlt_ingestion_format_matrix.py -q
```

Expected when Dagster/Polaris/MinIO are reachable: PASS.

Expected when local services are not reachable: tests stop with infrastructure-gated messaging like `Infrastructure unreachable: Polaris..., MinIO...`. Report this as infrastructure-gated, not product-failed.

- [ ] **Step 3: Run typecheck and lint**

Run:

```bash
make typecheck
make lint
```

Expected: both PASS.

- [ ] **Step 4: Run unit suite**

Run:

```bash
make test-unit
```

Expected: PASS.

- [ ] **Step 5: Run final reference audit**

Run:

```bash
rg -n "plugins\\.ingestion\\.config\\.catalog_config|catalog_config is required|dlt product ingestion requires an Iceberg destination catalog_config|_floe_iceberg_catalog_config" . \
  --glob '!docs/superpowers/plans/2026-05-07-dlt-ingestion-composition-uplift.md'
```

Expected: no output.

- [ ] **Step 6: Inspect final diff**

Run:

```bash
git status --short
git diff --stat
git diff --check
```

Expected:

- `git diff --check` has no output and exit code 0.
- Only expected source, test, demo, and docs files are modified.
- `PROMPT.md` remains untracked unless the user separately asked to track it.

- [ ] **Step 7: Commit final verification fixes if needed**

If verification required fixes:

```bash
git add packages/floe-core plugins/floe-ingestion-dlt plugins/floe-orchestrator-dagster tests demo
git commit -m "Verify dlt ingestion composition uplift"
```

If no files changed, do not create an empty commit.

## Completion Criteria

- `CompiledArtifacts.deployment.ingestion.dlt` exists and is secret-free.
- Demo compilation emits storage, catalog, and ingestion deployment bindings.
- `demo/manifest.yaml` no longer duplicates catalog/storage config under ingestion.
- dlt runtime cannot execute configured ingestion without a runtime binding.
- Dagster passes the compiled dlt binding into ingestion assets and pipeline creation.
- Focused ingestion unit and contract tests pass.
- `make typecheck`, `make lint`, and `make test-unit` pass.
- E2E collection passes.
- Live E2E either passes against reachable services or reports infrastructure-gated failure clearly.
