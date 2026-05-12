# AWS Provider Core Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the shared Glue catalog binding, runtime projection, and resolver proof needed before implementing native AWS S3 and Glue plugins.

**Architecture:** The core branch extends typed, secret-free contracts only. S3 and Glue provider packages remain out of scope; tests use schema objects and fake plugin behavior where needed so plugin implementation branches can depend on this contract without editing it.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, PyIceberg config translation, Floe composition resolver.

---

## File Map

- Modify: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
  - Add `GlueCatalogDeploymentBinding`.
  - Extend `CatalogDeploymentBinding` with `glue`.
  - Validate `provider == "glue"` has Glue details.
  - Export the new model in `__all__`.
- Modify: `packages/floe-core/src/floe_core/runtime_catalog_connection.py`
  - Build `RuntimeCatalogConnection` from `CatalogDeploymentBinding.glue`.
- Modify: `packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py`
  - Preserve Glue/PyIceberg properties from the runtime projection without REST-only assumptions.
- Modify: `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
  - Add schema and secret-free tests for Glue binding.
- Modify: `packages/floe-core/tests/unit/test_runtime_catalog_connection.py`
  - Add Glue runtime projection tests.
- Modify: `packages/floe-iceberg/tests/unit/test_runtime_catalog.py`
  - Add PyIceberg Glue config translation test.
- Modify: `packages/floe-core/tests/unit/composition/test_resolver.py`
  - Add AWS S3 plus Glue resolver cases.
- Optional update: `tests/fixtures/golden/compiled_artifacts_v2_schema.json`
  - Regenerate only if schema tests require it.

Do not create `plugins/floe-storage-aws-s3` or `plugins/floe-catalog-glue` in this branch.

---

### Task 1: Add Glue Catalog Binding Schema

**Files:**
- Modify: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Test: `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`

- [ ] **Step 1: Write failing schema tests**

Append these tests near the existing catalog/runtime binding tests in `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`:

```python
class TestGlueCatalogDeploymentBinding:
    """Tests for AWS Glue catalog deployment binding."""

    def test_glue_catalog_binding_serializes_secret_free_fields(self) -> None:
        from floe_core.schemas.compiled_artifacts import (
            CatalogDeploymentBinding,
            CredentialRef,
            GlueCatalogDeploymentBinding,
        )

        binding = CatalogDeploymentBinding(
            provider="glue",
            glue=GlueCatalogDeploymentBinding(
                catalog_name="glue",
                region="ap-southeast-2",
                warehouse="s3://floe-provider-tests/warehouse/",
                catalog_id="278833447053",
                database_prefix="floe_provider_",
                skip_archive=True,
                max_retries=5,
                retry_mode="standard",
                credential_refs={
                    "role": CredentialRef(
                        source="workload-identity",
                        name="floe-provider-tests",
                    )
                },
                properties={"glue.skip-archive": "true"},
            ),
        )

        payload = binding.model_dump(mode="json")

        assert payload["provider"] == "glue"
        assert payload["glue"]["region"] == "ap-southeast-2"
        assert payload["glue"]["warehouse"] == "s3://floe-provider-tests/warehouse/"
        assert payload["glue"]["catalog_id"] == "278833447053"
        assert payload["glue"]["credential_refs"]["role"]["source"] == "workload-identity"
        assert "raw-secret-value" not in binding.model_dump_json()

    def test_glue_provider_requires_glue_details(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import CatalogDeploymentBinding

        with pytest.raises(ValidationError, match="glue catalog deployment binding"):
            CatalogDeploymentBinding(provider="glue")

    def test_glue_binding_rejects_raw_secret_properties(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import GlueCatalogDeploymentBinding

        with pytest.raises(ValidationError, match="raw credential material"):
            GlueCatalogDeploymentBinding(
                region="ap-southeast-2",
                warehouse="s3://floe-provider-tests/warehouse/",
                properties={"glue.secret-access-key": "raw-secret-value"},
            )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestGlueCatalogDeploymentBinding -q
```

Expected: FAIL because `GlueCatalogDeploymentBinding` does not exist.

- [ ] **Step 3: Implement schema model**

In `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`, add the model after `PolarisCatalogDeploymentBinding`:

```python
class GlueCatalogDeploymentBinding(BaseModel):
    """AWS Glue catalog-owned deployment and runtime configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_name: NonEmptyString = "glue"
    region: NonEmptyString
    warehouse: NonEmptyString
    catalog_id: NonEmptyString | None = None
    database_prefix: NonEmptyString | None = None
    endpoint: NonEmptyString | None = None
    skip_archive: bool = True
    max_retries: int | None = Field(default=None, ge=1)
    retry_mode: NonEmptyString | None = None
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)
    properties: dict[str, str] = Field(default_factory=dict)

    @field_validator("properties")
    @classmethod
    def validate_secret_free_properties(cls, value: dict[str, str]) -> dict[str, str]:
        """Ensure Glue catalog properties do not inline credential values."""
        _assert_no_secret_material(value, "catalog.glue.properties")
        return value
```

Then update `CatalogDeploymentBinding`:

```python
class CatalogDeploymentBinding(BaseModel):
    """Secret-free catalog deployment binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: NonEmptyString
    polaris: PolarisCatalogDeploymentBinding | None = None
    glue: GlueCatalogDeploymentBinding | None = None
    iceberg_rest: IcebergRestCatalogBinding | None = None
    dbt: DbtCatalogBinding | None = None

    @model_validator(mode="after")
    def validate_provider_binding(self) -> CatalogDeploymentBinding:
        """Ensure provider-specific catalog binding is present when required."""
        if self.provider == "polaris" and self.polaris is None:
            msg = "polaris catalog deployment binding requires polaris details"
            raise ValueError(msg)
        if self.provider == "glue" and self.glue is None:
            msg = "glue catalog deployment binding requires glue details"
            raise ValueError(msg)
        return self
```

Add `"GlueCatalogDeploymentBinding"` to the module `__all__` list.

- [ ] **Step 4: Run schema tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestGlueCatalogDeploymentBinding -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/floe-core/src/floe_core/schemas/compiled_artifacts.py \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py
git commit -m "feat: add Glue catalog deployment binding"
```

---

### Task 2: Build RuntimeCatalogConnection From Glue Binding

**Files:**
- Modify: `packages/floe-core/src/floe_core/runtime_catalog_connection.py`
- Test: `packages/floe-core/tests/unit/test_runtime_catalog_connection.py`

- [ ] **Step 1: Write failing runtime projection test**

Append to `packages/floe-core/tests/unit/test_runtime_catalog_connection.py`:

```python
def test_build_runtime_catalog_connection_maps_glue_binding() -> None:
    from floe_core.runtime_catalog_connection import build_runtime_catalog_connection
    from floe_core.schemas.compiled_artifacts import (
        CatalogDeploymentBinding,
        GlueCatalogDeploymentBinding,
    )

    catalog = CatalogDeploymentBinding(
        provider="glue",
        glue=GlueCatalogDeploymentBinding(
            catalog_name="glue",
            region="ap-southeast-2",
            warehouse="s3://floe-provider-tests/warehouse/",
            catalog_id="278833447053",
            database_prefix="floe_provider_",
            endpoint="https://glue.ap-southeast-2.amazonaws.com",
            skip_archive=True,
            max_retries=5,
            retry_mode="standard",
        ),
    )

    connection = build_runtime_catalog_connection(storage=None, catalog=catalog)

    assert connection.catalog_name == "glue"
    assert connection.warehouse == "s3://floe-provider-tests/warehouse/"
    assert connection.region == "ap-southeast-2"
    assert connection.properties == {
        "type": "glue",
        "glue.region": "ap-southeast-2",
        "glue.id": "278833447053",
        "glue.endpoint": "https://glue.ap-southeast-2.amazonaws.com",
        "glue.skip-archive": "true",
        "glue.max-retries": "5",
        "glue.retry-mode": "standard",
    }
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_runtime_catalog_connection.py::test_build_runtime_catalog_connection_maps_glue_binding -q
```

Expected: FAIL because Glue binding is not projected.

- [ ] **Step 3: Implement Glue projection**

In `packages/floe-core/src/floe_core/runtime_catalog_connection.py`, add this block after the Polaris block and before storage handling:

```python
    if catalog is not None and catalog.glue is not None:
        glue = catalog.glue
        catalog_name = glue.catalog_name
        warehouse = glue.warehouse
        region = glue.region
        credential_refs.update(glue.credential_refs)
        properties["type"] = "glue"
        properties["glue.region"] = glue.region
        properties["glue.skip-archive"] = str(glue.skip_archive).lower()
        if glue.catalog_id is not None:
            properties["glue.id"] = glue.catalog_id
        if glue.endpoint is not None:
            properties["glue.endpoint"] = glue.endpoint
        if glue.max_retries is not None:
            properties["glue.max-retries"] = str(glue.max_retries)
        if glue.retry_mode is not None:
            properties["glue.retry-mode"] = glue.retry_mode
        properties.update(glue.properties)
```

- [ ] **Step 4: Run runtime projection tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_runtime_catalog_connection.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/floe-core/src/floe_core/runtime_catalog_connection.py \
  packages/floe-core/tests/unit/test_runtime_catalog_connection.py
git commit -m "feat: project Glue catalog runtime connection"
```

---

### Task 3: Prove PyIceberg Glue Config Translation

**Files:**
- Modify: `packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py`
- Test: `packages/floe-iceberg/tests/unit/test_runtime_catalog.py`

- [ ] **Step 1: Write PyIceberg Glue translation test**

Append to `packages/floe-iceberg/tests/unit/test_runtime_catalog.py`:

```python
def test_runtime_catalog_connection_to_pyiceberg_config_preserves_glue_properties() -> None:
    connection = RuntimeCatalogConnection(
        catalog_name="glue",
        warehouse="s3://floe-provider-tests/warehouse/",
        properties={
            "type": "glue",
            "glue.region": "ap-southeast-2",
            "glue.id": "278833447053",
            "glue.skip-archive": "true",
            "glue.max-retries": "5",
            "glue.retry-mode": "standard",
        },
    )

    config = runtime_catalog_connection_to_pyiceberg_config(connection)

    assert config == {
        "warehouse": "s3://floe-provider-tests/warehouse/",
        "type": "glue",
        "glue.region": "ap-southeast-2",
        "glue.id": "278833447053",
        "glue.skip-archive": "true",
        "glue.max-retries": "5",
        "glue.retry-mode": "standard",
    }
```

- [ ] **Step 2: Run test**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_runtime_catalog.py -q
```

Expected: PASS or expose a REST-only assumption. If it already passes, keep the test as regression coverage.

- [ ] **Step 3: Implement only if needed**

If the test fails because `runtime_catalog_connection_to_pyiceberg_config()` drops arbitrary properties, update it to keep `config.update(connection.properties)` last:

```python
    config.update(connection.properties)
    return config
```

Do not add Glue-specific branches in `floe-iceberg`; the typed runtime projection owns those properties.

- [ ] **Step 4: Run PyIceberg translator tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_runtime_catalog.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py \
  packages/floe-iceberg/tests/unit/test_runtime_catalog.py
git commit -m "test: prove Glue runtime catalog translation"
```

---

### Task 4: Add AWS S3 Plus Glue Resolver Proof

**Files:**
- Modify: `packages/floe-core/tests/unit/composition/test_resolver.py`

- [ ] **Step 1: Add valid AWS S3 plus Glue resolver test**

Append:

```python
def test_resolver_accepts_aws_s3_plus_glue_with_workload_identity() -> None:
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="aws-s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            sts=True,
            path_style_access=False,
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa", "aws-pod-identity"],
            requires_server_side_storage_access=True,
            supports_no_sts=False,
            supports_path_style_access=False,
        ),
    )
    identity = PluginCapabilities(
        plugin_type="identity",
        plugin_name="aws-irsa",
        capabilities=CapabilitySet(identity_modes=["aws-irsa"]),
    )

    result = resolver.validate([storage, identity], [catalog])

    assert result.valid is True
    assert result.issues == []
```

- [ ] **Step 2: Add invalid MinIO plus Glue resolver test**

Append:

```python
def test_resolver_rejects_minio_plus_glue_native_s3_requirement() -> None:
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities=CapabilitySet(
            protocols=["s3-compatible"],
            credential_modes=["kubernetes-secret"],
            path_style_access=True,
            sts=False,
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert [issue.code for issue in result.issues] == [
        "COMPOSITION_PROTOCOL_UNSUPPORTED",
        "COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
    ]
```

- [ ] **Step 3: Add missing identity rejection test**

Append:

```python
def test_resolver_rejects_glue_workload_identity_without_identity_provider() -> None:
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="aws-s3",
        capabilities=CapabilitySet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
        ),
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements=RequirementSet(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
        ),
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert result.issues[0].code == "COMPOSITION_IDENTITY_PROVIDER_MISSING"
```

- [ ] **Step 4: Run resolver tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/composition/test_resolver.py -q
```

Expected: PASS. If any test fails because the expected diagnostic order differs, keep all asserted codes but sort them explicitly:

```python
assert sorted(issue.code for issue in result.issues) == [
    "COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
    "COMPOSITION_PROTOCOL_UNSUPPORTED",
]
```

- [ ] **Step 5: Commit**

```bash
git add packages/floe-core/tests/unit/composition/test_resolver.py
git commit -m "test: prove AWS S3 and Glue resolver compatibility"
```

---

### Task 5: Add Compilation-Level Fake Plugin Contract Tests

**Files:**
- Modify: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`

- [ ] **Step 1: Add fake binding helpers**

Add local helpers near the existing fake plugin tests:

```python
def _fake_aws_s3_binding() -> StorageDeploymentBinding:
    from floe_core.schemas.compiled_artifacts import (
        DagsterStorageBinding,
        DbtStorageBinding,
        StorageCapabilities,
        StorageCredentialBinding,
        StorageDeploymentBinding,
        StorageProvisioningIntent,
        StorageRuntimeBinding,
        StorageServiceEndpoint,
        StorageWarehouse,
    )

    return StorageDeploymentBinding(
        provider="aws-s3",
        protocol="s3",
        endpoint=StorageServiceEndpoint(
            internal_url="https://s3.ap-southeast-2.amazonaws.com",
            external_url="https://s3.ap-southeast-2.amazonaws.com",
            region="ap-southeast-2",
            warehouse_path="s3://floe-provider-tests/warehouse/",
            path_style_access=False,
        ),
        warehouse=StorageWarehouse(
            uri="s3://floe-provider-tests/warehouse/",
            bucket="floe-provider-tests",
            prefix="warehouse/",
        ),
        allowed_locations=["s3://floe-provider-tests/warehouse/"],
        credentials=StorageCredentialBinding(
            mode="workload-identity",
            service_account_ref="floe-provider-tests",
        ),
        capabilities=StorageCapabilities(
            protocols=["s3"],
            credential_modes=["workload-identity"],
            identity_modes=["aws-irsa"],
            sts_supported=True,
            path_style_access=False,
        ),
        provisioning=StorageProvisioningIntent(
            enabled=False,
            mode="external",
            default_create_policy="must-exist",
        ),
        runtime=StorageRuntimeBinding(
            pyiceberg_properties={"s3.region": "ap-southeast-2"},
        ),
        dbt=DbtStorageBinding(
            profile_name="floe",
            target_name="dev",
            schema_name="analytics",
        ),
        dagster=DagsterStorageBinding(
            resource_key="aws_s3_storage",
            asset_io_manager_key="iceberg_io_manager",
        ),
    )
```

- [ ] **Step 2: Add fake plugin compile test**

Add a test that monkeypatches `PluginRegistry` with fake `StoragePlugin` and `CatalogPlugin` classes. The fake catalog should return Glue requirements and a `CatalogDeploymentBinding(provider="glue", glue=...)`.

```python
def test_compile_accepts_fake_aws_s3_plus_glue_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from floe_core.composition.models import PluginRequirements, RequirementSet
    from floe_core.plugin_types import PluginType
    from floe_core.schemas.compiled_artifacts import (
        CatalogDeploymentBinding,
        GlueCatalogDeploymentBinding,
    )

    class FakeAwsS3Plugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "aws-s3"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_pyiceberg_fileio(self) -> FileIO:
            raise NotImplementedError

        def get_warehouse_uri(self, namespace: str) -> str:
            return f"s3://floe-provider-tests/warehouse/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> StorageDeploymentBinding:
            return _fake_aws_s3_binding()

    class FakeGluePlugin(CatalogPlugin):
        @property
        def name(self) -> str:
            return "glue"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_storage_requirements(self) -> PluginRequirements:
            return PluginRequirements(
                plugin_type="catalog",
                plugin_name="glue",
                requirements=RequirementSet(
                    protocols=["s3"],
                    credential_modes=["workload-identity"],
                    identity_modes=["aws-irsa"],
                ),
            )

        def build_catalog_deployment(
            self,
            storage: StorageDeploymentBinding,
        ) -> CatalogDeploymentBinding:
            return CatalogDeploymentBinding(
                provider="glue",
                glue=GlueCatalogDeploymentBinding(
                    region=storage.endpoint.region,
                    warehouse=storage.warehouse.uri if storage.warehouse else storage.endpoint.warehouse_path,
                    catalog_id="278833447053",
                    database_prefix="floe_provider_",
                ),
            )
```

Complete the fake catalog's unused abstract methods with `raise NotImplementedError`, and wire a registry that returns `FakeAwsS3Plugin` for `PluginType.STORAGE` and `FakeGluePlugin` for `PluginType.CATALOG`.

Use a copied `demo/manifest.yaml` with:

```python
manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
manifest["plugins"]["storage"]["type"] = "aws-s3"
manifest["plugins"]["storage"]["config"] = {}
manifest["plugins"]["catalog"]["type"] = "glue"
manifest["plugins"]["catalog"]["config"] = {}
manifest_path = tmp_path / "manifest.yaml"
manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
```

Assert:

```python
artifacts = compile_pipeline(
    ROOT / "demo" / "customer-360" / "floe.yaml",
    manifest_path,
    emit_lineage=False,
)

assert artifacts.deployment is not None
assert artifacts.deployment.storage.provider == "aws-s3"
assert artifacts.deployment.catalog.provider == "glue"
assert artifacts.deployment.catalog.glue.region == "ap-southeast-2"
assert "raw-secret-value" not in artifacts.model_dump_json()
```

- [ ] **Step 3: Run focused compilation test**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py::test_compile_accepts_fake_aws_s3_plus_glue_contract -q
```

Expected: PASS after abstract method stubs and registry monkeypatch are complete.

- [ ] **Step 4: Commit**

```bash
git add packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py
git commit -m "test: prove compile contract for AWS S3 plus Glue"
```

---

### Task 6: Final Verification

**Files:**
- No new source files.

- [ ] **Step 1: Run focused test set**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestGlueCatalogDeploymentBinding -q
uv run pytest packages/floe-core/tests/unit/test_runtime_catalog_connection.py -q
uv run pytest packages/floe-core/tests/unit/composition/test_resolver.py -q
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py -q
uv run pytest packages/floe-iceberg/tests/unit/test_runtime_catalog.py -q
```

Expected: all PASS.

- [ ] **Step 2: Run static checks**

Run:

```bash
uv run ruff check packages/floe-core/src/floe_core/schemas/compiled_artifacts.py \
  packages/floe-core/src/floe_core/runtime_catalog_connection.py \
  packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py \
  packages/floe-core/tests/unit/test_runtime_catalog_connection.py \
  packages/floe-core/tests/unit/composition/test_resolver.py \
  packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py \
  packages/floe-iceberg/tests/unit/test_runtime_catalog.py
uv run mypy packages/floe-core/src/floe_core/schemas/compiled_artifacts.py \
  packages/floe-core/src/floe_core/runtime_catalog_connection.py \
  packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py
git diff --check
```

Expected: all PASS.

- [ ] **Step 3: Commit any final fixups**

If static checks required formatting or type fixups:

```bash
git add <changed-files>
git commit -m "chore: finalize AWS provider core contracts"
```

If no files changed, skip this commit.

- [ ] **Step 4: Report handoff**

Report:

- branch name
- commit SHAs
- tests run
- whether plugin implementation worktrees can now be created

Do not create plugin worktrees until this branch is merged or explicitly selected as their base.
