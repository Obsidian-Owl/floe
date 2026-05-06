# Storage Composition Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the storage-side MinIO work by replacing remaining chart-driven storage coupling with neutral storage bindings, catalog-owned translation, and resolver-validated plugin composition.

**Architecture:** `floe-core` owns compatibility resolution and typed deployment bindings. `floe-storage-minio` emits neutral storage desired state. `floe-catalog-polaris` translates that storage state into Polaris deployment/bootstrap config. Helm renders resolved deployment bindings and no longer reconstructs semantic storage config from independent chart values.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, PyIceberg, Apache Polaris, dbt-duckdb, Dagster, Helm, Kubernetes Secrets, MinIO, DevPod, Hetzner.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-05-05-storage-minio-architecture-design.md`
- Research brief: `docs/research/storage-composition-20260507.md`
- Plugin tracker: `docs/architecture/plugin-composition-uplift-tracker.md`
- Storage schema: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Storage plugin ABC: `packages/floe-core/src/floe_core/plugins/storage.py`
- Catalog plugin ABC: `packages/floe-core/src/floe_core/plugins/catalog.py`
- MinIO plugin: `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py`
- Polaris plugin: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- Helm generator: `packages/floe-core/src/floe_core/cli/helm/generate.py`
- Polaris bootstrap chart: `charts/floe-platform/templates/job-polaris-bootstrap.yaml`
- Polaris deployment chart: `charts/floe-platform/templates/deployment-polaris.yaml`

## File Structure

- Create `packages/floe-core/src/floe_core/composition/`: resolver, capability models, requirement models, issue model.
- Modify `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`: expand storage binding and add catalog deployment binding.
- Modify `packages/floe-core/src/floe_core/plugins/storage.py`: make neutral `get_deployment_binding()` the primary storage compile contract.
- Modify `packages/floe-core/src/floe_core/plugins/catalog.py`: add storage requirements and catalog deployment translation methods.
- Modify `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py`: emit neutral storage binding only.
- Modify `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`: translate storage binding into Polaris deployment/bootstrap binding.
- Modify `packages/floe-core/src/floe_core/compilation/stages.py`: run composition resolver and attach deployment bindings.
- Modify `packages/floe-core/src/floe_core/cli/helm/generate.py`: render Helm values from deployment bindings.
- Modify `charts/floe-platform/templates/job-polaris-bootstrap.yaml`: consume generated Polaris catalog config rather than independently assembling storage truth.
- Modify `charts/floe-platform/templates/deployment-polaris.yaml` and `configmap-polaris.yaml`: remove speculative Polaris credential env surfaces not backed by the official deployment binding.
- Modify architecture docs listed in the design spec.
- Add and update tests in `packages/floe-core/tests/unit/composition/`, `packages/floe-core/tests/unit/schemas/`, `plugins/floe-storage-minio/tests/unit/`, `plugins/floe-catalog-polaris/tests/unit/`, `packages/floe-core/tests/unit/helm/`, `charts/floe-platform/tests/`, and `tests/contract/`.

## Task 1: Add Composition Primitives

**Files:**
- Create: `packages/floe-core/src/floe_core/composition/__init__.py`
- Create: `packages/floe-core/src/floe_core/composition/models.py`
- Create: `packages/floe-core/src/floe_core/composition/resolver.py`
- Test: `packages/floe-core/tests/unit/composition/test_resolver.py`

- [ ] **Step 1: Write failing resolver tests**

Add `packages/floe-core/tests/unit/composition/test_resolver.py`:

```python
from floe_core.composition.models import (
    CompositionIssue,
    PluginCapabilities,
    PluginRequirements,
)
from floe_core.composition.resolver import CompositionResolver


def test_resolver_accepts_satisfied_requirements() -> None:
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities={
            "protocols": ["s3-compatible"],
            "credential_modes": ["kubernetes-secret"],
            "path_style_access": True,
            "sts": False,
        },
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="polaris",
        requirements={
            "protocols": ["s3-compatible", "s3"],
            "credential_modes": ["kubernetes-secret", "workload-identity"],
            "requires_server_side_storage_access": True,
            "supports_no_sts": True,
            "supports_path_style_access": True,
        },
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is True
    assert result.issues == []


def test_resolver_rejects_incompatible_protocol() -> None:
    resolver = CompositionResolver()
    storage = PluginCapabilities(
        plugin_type="storage",
        plugin_name="minio",
        capabilities={"protocols": ["s3-compatible"], "credential_modes": ["kubernetes-secret"]},
    )
    catalog = PluginRequirements(
        plugin_type="catalog",
        plugin_name="glue",
        requirements={"protocols": ["s3"], "credential_modes": ["workload-identity"]},
    )

    result = resolver.validate([storage], [catalog])

    assert result.valid is False
    assert result.issues == [
        CompositionIssue(
            severity="error",
            code="COMPOSITION_PROTOCOL_UNSUPPORTED",
            message="catalog glue requires one of protocols ['s3']; storage minio provides ['s3-compatible']",
            plugins=["storage:minio", "catalog:glue"],
        )
    ]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/composition/test_resolver.py -q
```

Expected: import failure for `floe_core.composition`.

- [ ] **Step 3: Implement composition models**

Create `packages/floe-core/src/floe_core/composition/models.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PluginCapabilities(BaseModel):
    """Capabilities a plugin provides to the composition resolver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_type: str = Field(..., min_length=1)
    plugin_name: str = Field(..., min_length=1)
    capabilities: dict[str, Any] = Field(default_factory=dict)

    @property
    def ref(self) -> str:
        return f"{self.plugin_type}:{self.plugin_name}"


class PluginRequirements(BaseModel):
    """Requirements a plugin needs from peer plugins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_type: str = Field(..., min_length=1)
    plugin_name: str = Field(..., min_length=1)
    requirements: dict[str, Any] = Field(default_factory=dict)

    @property
    def ref(self) -> str:
        return f"{self.plugin_type}:{self.plugin_name}"


class CompositionIssue(BaseModel):
    """Compatibility issue found while composing selected plugins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: Literal["error", "warning"]
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    plugins: list[str] = Field(default_factory=list)


class CompositionValidationResult(BaseModel):
    """Resolver validation result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    issues: list[CompositionIssue] = Field(default_factory=list)
```

- [ ] **Step 4: Implement resolver**

Create `packages/floe-core/src/floe_core/composition/resolver.py`:

```python
from __future__ import annotations

from floe_core.composition.models import (
    CompositionIssue,
    CompositionValidationResult,
    PluginCapabilities,
    PluginRequirements,
)


class CompositionResolver:
    """Validate that selected plugin capabilities satisfy peer requirements."""

    def validate(
        self,
        capabilities: list[PluginCapabilities],
        requirements: list[PluginRequirements],
    ) -> CompositionValidationResult:
        issues: list[CompositionIssue] = []
        storage = next((item for item in capabilities if item.plugin_type == "storage"), None)
        if storage is None:
            return CompositionValidationResult(valid=True, issues=[])

        for requirement in requirements:
            if requirement.plugin_type != "catalog":
                continue
            issues.extend(self._validate_storage_for_catalog(storage, requirement))

        return CompositionValidationResult(
            valid=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )

    def _validate_storage_for_catalog(
        self,
        storage: PluginCapabilities,
        catalog: PluginRequirements,
    ) -> list[CompositionIssue]:
        issues: list[CompositionIssue] = []
        storage_protocols = list(storage.capabilities.get("protocols", []))
        required_protocols = list(catalog.requirements.get("protocols", []))
        if required_protocols and not set(storage_protocols).intersection(required_protocols):
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_PROTOCOL_UNSUPPORTED",
                    message=(
                        f"catalog {catalog.plugin_name} requires one of protocols "
                        f"{required_protocols}; storage {storage.plugin_name} provides {storage_protocols}"
                    ),
                    plugins=[storage.ref, catalog.ref],
                )
            )

        storage_modes = list(storage.capabilities.get("credential_modes", []))
        required_modes = list(catalog.requirements.get("credential_modes", []))
        if required_modes and not set(storage_modes).intersection(required_modes):
            issues.append(
                CompositionIssue(
                    severity="error",
                    code="COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
                    message=(
                        f"catalog {catalog.plugin_name} requires one of credential modes "
                        f"{required_modes}; storage {storage.plugin_name} provides {storage_modes}"
                    ),
                    plugins=[storage.ref, catalog.ref],
                )
            )

        return issues
```

Create `packages/floe-core/src/floe_core/composition/__init__.py`:

```python
from floe_core.composition.models import (
    CompositionIssue,
    CompositionValidationResult,
    PluginCapabilities,
    PluginRequirements,
)
from floe_core.composition.resolver import CompositionResolver

__all__ = [
    "CompositionIssue",
    "CompositionResolver",
    "CompositionValidationResult",
    "PluginCapabilities",
    "PluginRequirements",
]
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/composition/test_resolver.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add packages/floe-core/src/floe_core/composition packages/floe-core/tests/unit/composition/test_resolver.py
git commit -m "feat: add plugin composition resolver primitives"
```

## Task 2: Expand Storage And Catalog Deployment Bindings

**Files:**
- Modify: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Test: `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`

- [ ] **Step 1: Write schema tests**

Add tests that construct:

```python
StorageDeploymentBinding(
    provider="minio",
    protocol="s3-compatible",
    endpoint=StorageServiceEndpoint(
        internal_url="http://floe-platform-minio:9000",
        external_url="http://localhost:9000",
        region="us-east-1",
        warehouse_path="s3://floe-iceberg",
        path_style_access=True,
    ),
    warehouse=StorageWarehouse(uri="s3://floe-iceberg", bucket="floe-iceberg"),
    allowed_locations=["s3://floe-iceberg"],
    buckets=[StorageBucketRequirement(name="floe-iceberg", uri="s3://floe-iceberg", purpose="warehouse", create_policy="create-if-missing")],
    credentials=StorageCredentialBinding(...),
    capabilities=StorageCapabilities(protocols=["s3-compatible"], credential_modes=["kubernetes-secret"], sts_supported=False),
    provisioning=StorageProvisioningIntent(enabled=True, mode="helm-job", default_create_policy="create-if-missing"),
    runtime=StorageRuntimeBinding(pyiceberg_properties={"s3.endpoint": "http://floe-platform-minio:9000"}),
)
```

Also add `CatalogDeploymentBinding` tests for Polaris storage config and assert
no raw secret values appear in serialized artifacts.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py -q
```

Expected: constructor/type failures for new binding models and fields.

- [ ] **Step 3: Implement Pydantic models**

Add focused Pydantic models near the existing deployment binding models:

```python
class StorageWarehouse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    uri: NonEmptyString
    bucket: NonEmptyString
    prefix: str = ""


class StorageBucketRequirement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: NonEmptyString
    uri: NonEmptyString
    purpose: Literal["warehouse", "artifacts", "landing", "quarantine", "checkpoints", "exports"]
    create_policy: Literal["create-if-missing", "must-exist", "never-create"]
    prefixes: list[str] = Field(default_factory=list)
    features: dict[str, str] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)


class StorageCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    protocols: list[NonEmptyString]
    credential_modes: list[NonEmptyString]
    sts_supported: bool
    path_style_access: bool = False


class StorageProvisioningIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool
    mode: Literal["helm-job", "external", "manual", "future-plugin-runtime"]
    default_create_policy: Literal["create-if-missing", "must-exist", "never-create"]


class StorageRuntimeBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    pyiceberg_properties: dict[str, str] = Field(default_factory=dict)
    dbt_profile_fragment: dict[str, Any] = Field(default_factory=dict)
    dagster_resources: dict[str, Any] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)


class PolarisCatalogDeploymentBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    storage_type: Literal["S3"]
    default_base_location: NonEmptyString
    allowed_locations: list[NonEmptyString]
    endpoint: NonEmptyString
    endpoint_internal: NonEmptyString
    path_style_access: bool
    sts_unavailable: bool
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)


class CatalogDeploymentBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    provider: Literal["polaris"]
    polaris: PolarisCatalogDeploymentBinding
```

Update `StorageServiceEndpoint` to include `path_style_access: bool = False`.
Update `DeploymentConfig` to include `catalog: CatalogDeploymentBinding | None = None`.

- [ ] **Step 4: Run schema tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add packages/floe-core/src/floe_core/schemas/compiled_artifacts.py packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py
git commit -m "feat: expand storage and catalog deployment bindings"
```

## Task 3: Move Polaris Translation Into The Polaris Plugin

**Files:**
- Modify: `packages/floe-core/src/floe_core/plugins/catalog.py`
- Modify: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- Test: `plugins/floe-catalog-polaris/tests/unit/test_storage_composition.py`

- [ ] **Step 1: Write Polaris translation tests**

Create `plugins/floe-catalog-polaris/tests/unit/test_storage_composition.py` with tests asserting `PolarisCatalogPlugin.build_catalog_deployment(storage)` emits:

- `storage_type == "S3"`
- `endpoint`
- `endpoint_internal`
- `path_style_access is True`
- `sts_unavailable is True`
- `allowed_locations` includes warehouse URI
- credential refs, not raw credential values

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest plugins/floe-catalog-polaris/tests/unit/test_storage_composition.py -q
```

Expected: missing method failure.

- [ ] **Step 3: Add CatalogPlugin methods**

Add abstract methods to `packages/floe-core/src/floe_core/plugins/catalog.py`:

```python
def get_storage_requirements(self) -> PluginRequirements:
    """Return storage requirements for composition validation."""


def build_catalog_deployment(
    self,
    storage: StorageDeploymentBinding,
) -> CatalogDeploymentBinding:
    """Translate neutral storage binding into catalog-owned deployment config."""
```

- [ ] **Step 4: Implement Polaris translation**

In `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`, implement:

```python
def get_storage_requirements(self) -> PluginRequirements:
    return PluginRequirements(
        plugin_type="catalog",
        plugin_name="polaris",
        requirements={
            "protocols": ["s3-compatible", "s3"],
            "credential_modes": ["kubernetes-secret", "workload-identity"],
            "requires_server_side_storage_access": True,
            "supports_no_sts": True,
            "supports_path_style_access": True,
        },
    )


def build_catalog_deployment(self, storage: StorageDeploymentBinding) -> CatalogDeploymentBinding:
    access_ref = storage.credentials.as_credential_ref("accessKeyId")
    secret_ref = storage.credentials.as_credential_ref("secretAccessKey")
    return CatalogDeploymentBinding(
        provider="polaris",
        polaris=PolarisCatalogDeploymentBinding(
            storage_type="S3",
            default_base_location=storage.warehouse.uri,
            allowed_locations=storage.allowed_locations,
            endpoint=storage.endpoint.external_url,
            endpoint_internal=storage.endpoint.internal_url,
            path_style_access=storage.endpoint.path_style_access,
            sts_unavailable=not storage.capabilities.sts_supported,
            credential_refs={"accessKeyId": access_ref, "secretAccessKey": secret_ref},
        ),
    )
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest plugins/floe-catalog-polaris/tests/unit/test_storage_composition.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add packages/floe-core/src/floe_core/plugins/catalog.py plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py plugins/floe-catalog-polaris/tests/unit/test_storage_composition.py
git commit -m "feat: let polaris own storage deployment translation"
```

## Task 4: Make MinIO Emit Neutral Storage Only

**Files:**
- Modify: `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py`
- Test: `plugins/floe-storage-minio/tests/unit/test_plugin.py`

- [ ] **Step 1: Update failing MinIO tests**

Change tests so `get_deployment_binding()` asserts neutral fields:

```python
assert binding.provider == "minio"
assert binding.protocol == "s3-compatible"
assert binding.endpoint.internal_url == "http://minio:9000"
assert binding.endpoint.path_style_access is True
assert binding.capabilities.sts_supported is False
assert binding.buckets[0].purpose == "warehouse"
assert not hasattr(binding, "polaris")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest plugins/floe-storage-minio/tests/unit/test_plugin.py -q
```

Expected: failures for missing neutral fields or stale Polaris-shaped assertions.

- [ ] **Step 3: Update MinIO binding generation**

Update `get_deployment_binding()` to populate neutral storage fields and remove
Polaris-specific chart projection from the binding path. Keep
`get_helm_values_override()` only as a deprecated compatibility method if tests
still cover old plugin ABC behavior.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest plugins/floe-storage-minio/tests/unit/test_plugin.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/floe-storage-minio/src/floe_storage_minio/plugin.py plugins/floe-storage-minio/tests/unit/test_plugin.py
git commit -m "refactor: emit neutral minio storage deployment binding"
```

## Task 5: Compose Storage And Catalog During Compile

**Files:**
- Modify: `packages/floe-core/src/floe_core/compilation/stages.py`
- Test: `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`
- Test: `tests/contract/test_compilation.py`

- [ ] **Step 1: Write compile tests**

Add tests that compile the demo manifest and assert:

```python
assert artifacts.deployment.storage.provider == "minio"
assert artifacts.deployment.catalog.provider == "polaris"
assert artifacts.deployment.catalog.polaris.endpoint_internal == artifacts.deployment.storage.endpoint.internal_url
assert artifacts.deployment.catalog.polaris.default_base_location == artifacts.deployment.storage.warehouse.uri
```

Add an incompatible composition test using a fake catalog requirement for
native S3 only and assert a `CompilationException` with code
`COMPOSITION_PROTOCOL_UNSUPPORTED`.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py tests/contract/test_compilation.py -q
```

Expected: missing catalog deployment binding and resolver failures.

- [ ] **Step 3: Wire resolver into compile**

In `packages/floe-core/src/floe_core/compilation/stages.py`, after resolving and
configuring storage/catalog plugins:

```python
storage_binding = storage_plugin.get_deployment_binding()
catalog_requirements = catalog_plugin.get_storage_requirements()
composition = CompositionResolver().validate(
    [storage_binding.to_capabilities()],
    [catalog_requirements],
)
if not composition.valid:
    raise CompilationException(...)
catalog_binding = catalog_plugin.build_catalog_deployment(storage_binding)
deployment = DeploymentConfig(storage=storage_binding, catalog=catalog_binding)
```

Use the existing `CompilationException` structure and include resolver issue
codes/messages in the exception context.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py tests/contract/test_compilation.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add packages/floe-core/src/floe_core/compilation/stages.py packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py tests/contract/test_compilation.py
git commit -m "feat: compose storage and catalog deployment bindings"
```

## Task 6: Render Helm From Deployment Bindings

**Files:**
- Modify: `packages/floe-core/src/floe_core/cli/helm/generate.py`
- Test: `packages/floe-core/tests/unit/helm/test_generate_cli.py`

- [ ] **Step 1: Update Helm generator tests**

Assert `_storage_helm_values(artifacts)` reads:

- MinIO bucket requirements from `deployment.storage.buckets`
- Polaris endpoint/path-style/no-STS/secret refs from `deployment.catalog.polaris`
- no raw secret values
- no fallback to `artifacts.plugins.storage.config` for semantic storage facts

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/helm/test_generate_cli.py -q
```

Expected: stale generator assumptions.

- [ ] **Step 3: Update generator**

Modify `_storage_helm_values()` so it requires both
`artifacts.deployment.storage` and `artifacts.deployment.catalog` for the
Polaris+MinIO path. Build chart values from deployment bindings only.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/helm/test_generate_cli.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add packages/floe-core/src/floe_core/cli/helm/generate.py packages/floe-core/tests/unit/helm/test_generate_cli.py
git commit -m "refactor: render helm storage values from deployment bindings"
```

## Task 7: Simplify Polaris Helm Templates

**Files:**
- Modify: `charts/floe-platform/templates/job-polaris-bootstrap.yaml`
- Modify: `charts/floe-platform/templates/deployment-polaris.yaml`
- Modify: `charts/floe-platform/templates/configmap-polaris.yaml`
- Modify: `charts/floe-platform/values.schema.json`
- Test: `charts/floe-platform/tests/bootstrap_job_test.yaml`
- Test: `charts/floe-platform/tests/deployment_polaris_bootstrap_test.yaml`
- Test: `charts/floe-platform/tests/configmap_polaris_test.yaml`

- [ ] **Step 1: Update chart tests**

Change tests to assert the chart renders the generated Polaris deployment
binding fields and Secret refs. Remove tests that preserve speculative env vars
added during tactical debugging unless they are backed by official Polaris Helm
or config fields.

- [ ] **Step 2: Run chart tests and verify failure**

Run:

```bash
helm unittest charts/floe-platform
```

Expected: failures until templates match generated binding inputs.

- [ ] **Step 3: Update templates**

Change `job-polaris-bootstrap.yaml` to render `storageConfigInfo` from generated
Polaris deployment values. Keep the JSON shape Polaris requires, but do not
invent storage truth in shell. Remove Polaris deployment env vars that are not
backed by the accepted deployment binding.

- [ ] **Step 4: Run chart tests**

Run:

```bash
helm unittest charts/floe-platform
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add charts/floe-platform/templates/job-polaris-bootstrap.yaml charts/floe-platform/templates/deployment-polaris.yaml charts/floe-platform/templates/configmap-polaris.yaml charts/floe-platform/values.schema.json charts/floe-platform/tests
git commit -m "refactor: render polaris storage bootstrap from deployment binding"
```

## Task 8: Update Architecture Docs

**Files:**
- Modify: `docs/architecture/adr/0036-storage-plugin-interface.md`
- Modify: `docs/architecture/interfaces/storage-plugin.md`
- Modify: `docs/architecture/interfaces/catalog-plugin.md`
- Modify: `docs/architecture/plugin-system/interfaces.md`
- Modify: `docs/architecture/opinionation-boundaries.md`
- Modify: `docs/contracts/compiled-artifacts.md`
- Modify: `docs/architecture/plugin-composition-uplift-tracker.md`

- [ ] **Step 1: Update docs**

Make the docs match the implemented contract:

- storage emits neutral storage bindings
- catalog owns catalog storage translation
- resolver validates compatibility
- Helm renders deployment bindings
- broader plugin uplift is tracked outside this storage PR

- [ ] **Step 2: Run doc consistency checks**

Run:

```bash
rg -n "MinIO plugin owns.*Polaris|StoragePlugin.*get_helm_values_override|storage plugin generates all consumer projections|storage.type: s3|floe-storage-s3|floe_storage_s3" docs packages plugins tests
```

Expected: no active alpha docs or tests preserve the old architecture. S3
protocol references may remain when they describe S3-compatible protocol, AWS
storage, PyIceberg properties, or Polaris storage type.

- [ ] **Step 3: Commit**

```bash
git add docs/architecture docs/contracts docs/superpowers docs/research
git commit -m "docs: align storage architecture with plugin composition model"
```

## Task 9: Verify Locally And Remotely

**Files:**
- No direct source edits unless validation exposes a product bug.

- [ ] **Step 1: Run focused unit and contract tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/composition \
  packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py \
  packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py \
  packages/floe-core/tests/unit/helm/test_generate_cli.py \
  plugins/floe-storage-minio/tests/unit/test_plugin.py \
  plugins/floe-catalog-polaris/tests/unit/test_storage_composition.py \
  tests/contract/test_compilation.py \
  tests/contract/test_storage_binding_security.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run chart checks**

Run:

```bash
helm unittest charts/floe-platform
helm template floe-platform charts/floe-platform -f charts/floe-platform/values-test.yaml >/tmp/floe-platform-rendered.yaml
```

Expected: pass and render succeeds.

- [ ] **Step 3: Run repo gate**

Run:

```bash
make check
```

Expected: pass. If unrelated failures exist, capture exact failing target and
evidence before deciding whether to patch.

- [ ] **Step 4: Run DevPod + Hetzner remote lane**

Use the repo's existing DevPod/Hetzner test lane. Preserve artifacts under
`test-artifacts/devpod-run-*`. Summarize bootstrap, developer, platform, and
destructive lanes separately.

- [ ] **Step 5: Clean up Hetzner resources**

After the remote run, verify direct provider state and remove billable
resources. Confirm servers, volumes, load balancers, floating IPs, SSH keys,
and `devpod list` have no current-run leftovers.

- [ ] **Step 6: Commit validation evidence if docs require it**

If a validation report is created, commit it:

```bash
git add docs/validation test-artifacts
git commit -m "docs: record storage composition validation"
```

## Self-Review Checklist

- Every storage fact has one owner.
- MinIO does not know Polaris deployment shape.
- Polaris owns Polaris bootstrap/config translation.
- Helm renders deployment bindings only.
- Compile remains side-effect free.
- Compiled artifacts remain secret-free.
- New catalog pressure test passes conceptually without modifying MinIO.
- Tracking doc covers follow-on plugin uplift outside this PR.
