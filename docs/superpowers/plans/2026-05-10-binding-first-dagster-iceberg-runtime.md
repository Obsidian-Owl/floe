# Binding-First Dagster/Iceberg Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Dagster and `floe_iceberg.writer` runtime catalog setup off `StoragePlugin.get_pyiceberg_catalog_config()` and onto resolved, secret-free deployment bindings.

**Architecture:** `floe-core` owns a neutral `RuntimeCatalogConnection` projection derived from `StorageDeploymentBinding` and `CatalogDeploymentBinding`. `floe-iceberg` owns PyIceberg-specific translation from that neutral projection into catalog connection properties. Dagster resource, export, and validation paths consume the translated runtime config while keeping plugin configuration only for plugin instance validation.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, Dagster resource factory tests, PyIceberg connection property conventions.

---

## Baseline Evidence

Run in `.worktrees/binding-first-runtime` before implementation:

```bash
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py packages/floe-iceberg/tests/unit/test_writer.py -q
```

Expected baseline: `212 passed`.

## File Map

- Modify: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Test: `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
- Create: `packages/floe-core/src/floe_core/runtime_catalog_connection.py`
- Test: `packages/floe-core/tests/unit/test_runtime_catalog_connection.py`
- Create: `packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py`
- Test: `packages/floe-iceberg/tests/unit/test_runtime_catalog.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py`
- Modify: `packages/floe-iceberg/src/floe_iceberg/writer.py`
- Test: `packages/floe-iceberg/tests/unit/test_writer.py`
- Optional docs update if public behavior text changes: `docs/superpowers/specs/2026-05-09-binding-first-dagster-iceberg-runtime-design.md`

## Task 1: Core Runtime Catalog Projection

**Files:**
- Modify: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Create: `packages/floe-core/src/floe_core/runtime_catalog_connection.py`
- Test: `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`
- Test: `packages/floe-core/tests/unit/test_runtime_catalog_connection.py`

- [ ] **Step 1: Add failing schema tests for the neutral runtime connection model**

Append tests near the existing storage/catalog deployment binding tests in `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`:

```python
class TestRuntimeCatalogConnection:
    """Tests for secret-free runtime catalog connection projection."""

    def test_runtime_catalog_connection_serializes_secret_free_fields(self) -> None:
        from floe_core.schemas.compiled_artifacts import CredentialRef, RuntimeCatalogConnection

        connection = RuntimeCatalogConnection(
            catalog_name="polaris",
            catalog_uri="http://polaris:8181/api/catalog",
            warehouse="s3://floe-iceberg",
            storage_endpoint="http://floe-platform-minio:9000",
            region="us-east-1",
            path_style_access=True,
            properties={"token-refresh-enabled": "true"},
            credential_refs={
                "accessKeyId": CredentialRef(
                    source="kubernetes-secret",
                    name="floe-platform-minio-credentials",
                    key="root-user",
                )
            },
            env_refs={"PYICEBERG_CATALOG__POLARIS__CREDENTIAL": "POLARIS_CREDENTIAL"},
        )

        payload = connection.model_dump(mode="json")

        assert payload["catalog_uri"] == "http://polaris:8181/api/catalog"
        assert payload["path_style_access"] is True
        assert payload["credential_refs"]["accessKeyId"]["name"] == "floe-platform-minio-credentials"
        assert "secret" not in str(payload).lower().replace("secret-free", "")

    def test_runtime_catalog_connection_rejects_raw_secret_material(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import RuntimeCatalogConnection

        with pytest.raises(ValidationError, match="raw credential material"):
            RuntimeCatalogConnection(
                catalog_name="polaris",
                properties={
                    "s3.secret-access-key": "raw-secret-value",  # pragma: allowlist secret
                },
            )
```

- [ ] **Step 2: Run schema tests to verify they fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestRuntimeCatalogConnection -q
```

Expected: fail because `RuntimeCatalogConnection` does not exist.

- [ ] **Step 3: Add `RuntimeCatalogConnection` to compiled artifact schemas**

Add this model after `CatalogDeploymentBinding` in `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`:

```python
class RuntimeCatalogConnection(BaseModel):
    """Secret-free runtime catalog connection projection for Iceberg consumers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_name: NonEmptyString = "iceberg"
    catalog_uri: NonEmptyString | None = None
    warehouse: NonEmptyString | None = None
    storage_endpoint: NonEmptyString | None = None
    region: NonEmptyString | None = None
    path_style_access: bool | None = None
    properties: dict[str, str] = Field(default_factory=dict)
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)

    @field_validator("properties")
    @classmethod
    def validate_secret_free_properties(cls, value: dict[str, str]) -> dict[str, str]:
        """Ensure runtime catalog properties do not inline credential material."""
        _assert_no_secret_material(value, "runtime_catalog.properties")
        return value
```

Also add `"RuntimeCatalogConnection"` to the module `__all__` list.

- [ ] **Step 4: Add failing derivation tests**

Create `packages/floe-core/tests/unit/test_runtime_catalog_connection.py`:

```python
from __future__ import annotations

from floe_core.runtime_catalog_connection import build_runtime_catalog_connection
from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    CredentialRef,
    DbtStorageBinding,
    DagsterStorageBinding,
    PolarisCatalogDeploymentBinding,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageServiceEndpoint,
    StorageWarehouse,
)


def _storage_binding() -> StorageDeploymentBinding:
    return StorageDeploymentBinding(
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
        credentials=StorageCredentialBinding(mode="none"),
        dbt=DbtStorageBinding(
            profile_name="floe",
            target_name="dev",
            schema_name="analytics",
        ),
        dagster=DagsterStorageBinding(
            resource_key="minio_storage",
            asset_io_manager_key="iceberg_io_manager",
        ),
    )


def _catalog_binding() -> CatalogDeploymentBinding:
    return CatalogDeploymentBinding(
        provider="polaris",
        polaris=PolarisCatalogDeploymentBinding(
            storage_type="S3",
            warehouse="s3://floe-iceberg",
            default_base_location="s3://floe-iceberg",
            allowed_locations=["s3://floe-iceberg"],
            endpoint="http://localhost:9000",
            endpoint_internal="http://floe-platform-minio:9000",
            catalog_uri="http://polaris:8181/api/catalog",
            path_style_access=True,
            sts_unavailable=True,
            credential_refs={
                "accessKeyId": CredentialRef(source="none", name="none"),
                "secretAccessKey": CredentialRef(source="none", name="none"),  # pragma: allowlist secret
            },
        ),
    )


def test_build_runtime_catalog_connection_prefers_catalog_owned_fields() -> None:
    connection = build_runtime_catalog_connection(
        storage=_storage_binding(),
        catalog=_catalog_binding(),
    )

    assert connection.catalog_name == "polaris"
    assert connection.catalog_uri == "http://polaris:8181/api/catalog"
    assert connection.warehouse == "s3://floe-iceberg"
    assert connection.storage_endpoint == "http://floe-platform-minio:9000"
    assert connection.region == "us-east-1"
    assert connection.path_style_access is True
    assert connection.credential_refs["accessKeyId"].source == "none"


def test_build_runtime_catalog_connection_degrades_without_catalog() -> None:
    connection = build_runtime_catalog_connection(storage=_storage_binding(), catalog=None)

    assert connection.catalog_name == "iceberg"
    assert connection.catalog_uri is None
    assert connection.warehouse == "s3://floe-iceberg"
    assert connection.storage_endpoint == "http://floe-platform-minio:9000"
    assert connection.region == "us-east-1"
    assert connection.path_style_access is True
```

- [ ] **Step 5: Run derivation tests to verify they fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_runtime_catalog_connection.py -q
```

Expected: fail because `floe_core.runtime_catalog_connection` does not exist.

- [ ] **Step 6: Implement the derivation helper**

Create `packages/floe-core/src/floe_core/runtime_catalog_connection.py`:

```python
"""Build secret-free runtime catalog connection projections from deployment bindings."""

from __future__ import annotations

from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    RuntimeCatalogConnection,
    StorageDeploymentBinding,
)


def build_runtime_catalog_connection(
    *,
    storage: StorageDeploymentBinding | None,
    catalog: CatalogDeploymentBinding | None,
) -> RuntimeCatalogConnection:
    """Derive a neutral runtime catalog connection from compiled deployment bindings."""
    catalog_name = "iceberg"
    catalog_uri: str | None = None
    warehouse: str | None = None
    path_style_access: bool | None = None
    properties: dict[str, str] = {}
    credential_refs = {}
    env_refs: dict[str, str] = {}

    if catalog is not None and catalog.iceberg_rest is not None:
        iceberg_rest = catalog.iceberg_rest
        catalog_name = iceberg_rest.catalog_name
        catalog_uri = iceberg_rest.uri
        warehouse = iceberg_rest.warehouse
        properties.update(iceberg_rest.properties)
        if iceberg_rest.oauth2 is not None:
            env_refs["oauth2_client_id"] = iceberg_rest.oauth2.client_id_env
            env_refs["oauth2_client_secret"] = iceberg_rest.oauth2.client_secret_env
            env_refs["oauth2_server_uri"] = iceberg_rest.oauth2.oauth2_server_uri_env
            if iceberg_rest.oauth2.oauth2_scope_env is not None:
                env_refs["oauth2_scope"] = iceberg_rest.oauth2.oauth2_scope_env

    if catalog is not None and catalog.polaris is not None:
        polaris = catalog.polaris
        catalog_name = "polaris"
        catalog_uri = polaris.catalog_uri or catalog_uri
        warehouse = polaris.warehouse or warehouse or polaris.default_base_location
        path_style_access = polaris.path_style_access
        credential_refs.update(polaris.credential_refs)

    storage_endpoint: str | None = None
    region: str | None = None
    if storage is not None:
        storage_endpoint = storage.endpoint.internal_url
        region = storage.endpoint.region
        if warehouse is None:
            warehouse = storage.warehouse.uri if storage.warehouse is not None else storage.endpoint.warehouse_path
        if path_style_access is None:
            path_style_access = storage.endpoint.path_style_access
        properties.update(storage.runtime.pyiceberg_properties)
        env_refs.update(storage.runtime.env_refs)

    return RuntimeCatalogConnection(
        catalog_name=catalog_name,
        catalog_uri=catalog_uri,
        warehouse=warehouse,
        storage_endpoint=storage_endpoint,
        region=region,
        path_style_access=path_style_access,
        properties=properties,
        credential_refs=credential_refs,
        env_refs=env_refs,
    )
```

- [ ] **Step 7: Run Task 1 tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestRuntimeCatalogConnection packages/floe-core/tests/unit/test_runtime_catalog_connection.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
git add packages/floe-core/src/floe_core/schemas/compiled_artifacts.py packages/floe-core/src/floe_core/runtime_catalog_connection.py packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py packages/floe-core/tests/unit/test_runtime_catalog_connection.py
git commit -m "Add runtime catalog connection projection"
```

## Task 2: PyIceberg Translation In `floe-iceberg`

**Files:**
- Create: `packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py`
- Test: `packages/floe-iceberg/tests/unit/test_runtime_catalog.py`

- [ ] **Step 1: Add failing PyIceberg translation tests**

Create `packages/floe-iceberg/tests/unit/test_runtime_catalog.py`:

```python
from __future__ import annotations

from floe_core.schemas.compiled_artifacts import RuntimeCatalogConnection
from floe_iceberg.runtime_catalog import runtime_catalog_connection_to_pyiceberg_config


def test_runtime_catalog_connection_to_pyiceberg_config_maps_non_secret_fields() -> None:
    connection = RuntimeCatalogConnection(
        catalog_name="polaris",
        catalog_uri="http://polaris:8181/api/catalog",
        warehouse="s3://floe-iceberg",
        storage_endpoint="http://floe-platform-minio:9000",
        region="us-east-1",
        path_style_access=True,
        properties={"token-refresh-enabled": "true"},
        env_refs={"PYICEBERG_CATALOG__POLARIS__CREDENTIAL": "POLARIS_CREDENTIAL"},
    )

    config = runtime_catalog_connection_to_pyiceberg_config(connection)

    assert config == {
        "uri": "http://polaris:8181/api/catalog",
        "warehouse": "s3://floe-iceberg",
        "s3.endpoint": "http://floe-platform-minio:9000",
        "s3.region": "us-east-1",
        "s3.path-style-access": "true",
        "token-refresh-enabled": "true",
    }


def test_runtime_catalog_connection_to_pyiceberg_config_omits_missing_fields() -> None:
    config = runtime_catalog_connection_to_pyiceberg_config(
        RuntimeCatalogConnection(catalog_name="iceberg")
    )

    assert config == {}
```

- [ ] **Step 2: Run translation tests to verify they fail**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_runtime_catalog.py -q
```

Expected: fail because `floe_iceberg.runtime_catalog` does not exist.

- [ ] **Step 3: Implement PyIceberg translation**

Create `packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py`:

```python
"""Translate Floe runtime catalog projections into PyIceberg connection config."""

from __future__ import annotations

from typing import Any

from floe_core.schemas.compiled_artifacts import RuntimeCatalogConnection


def runtime_catalog_connection_to_pyiceberg_config(
    connection: RuntimeCatalogConnection | None,
) -> dict[str, Any]:
    """Return PyIceberg catalog connection properties for a runtime projection."""
    if connection is None:
        return {}

    config: dict[str, Any] = {}
    if connection.catalog_uri is not None:
        config["uri"] = connection.catalog_uri
    if connection.warehouse is not None:
        config["warehouse"] = connection.warehouse
    if connection.storage_endpoint is not None:
        config["s3.endpoint"] = connection.storage_endpoint
    if connection.region is not None:
        config["s3.region"] = connection.region
    if connection.path_style_access is not None:
        config["s3.path-style-access"] = str(connection.path_style_access).lower()
    config.update(connection.properties)
    return config
```

- [ ] **Step 4: Run Task 2 tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_runtime_catalog.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py packages/floe-iceberg/tests/unit/test_runtime_catalog.py
git commit -m "Translate runtime catalog projection for PyIceberg"
```

## Task 3: Dagster Resource Wiring Uses Deployment Bindings

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py`

- [ ] **Step 1: Add failing resource wiring guard test**

Add a test in `plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py` near the storage binding tests:

```python
def test_create_iceberg_resources_uses_runtime_connection_without_storage_helper(self) -> None:
    """Resource construction must not call storage-owned catalog config helpers."""
    from floe_core.schemas.compiled_artifacts import PluginRef, RuntimeCatalogConnection
    from floe_orchestrator_dagster.resources.iceberg import create_iceberg_resources

    catalog_ref = PluginRef(type="mock-catalog", version="1.0.0", config={})
    storage_ref = PluginRef(type="mock-storage", version="1.0.0", config={})
    runtime_connection = RuntimeCatalogConnection(
        catalog_uri="http://polaris:8181/api/catalog",
        warehouse="s3://floe-iceberg",
        storage_endpoint="http://compiled-minio:9000",
        region="us-east-1",
        path_style_access=True,
    )

    with (
        patch("floe_core.plugin_registry.get_registry") as mock_get_registry,
        patch("floe_iceberg.IcebergTableManager") as mock_table_manager_cls,
        patch("floe_orchestrator_dagster.io_manager.create_iceberg_io_manager") as mock_create_io_manager,
    ):
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        mock_catalog_plugin = MagicMock()
        mock_storage_plugin = MagicMock()
        mock_storage_plugin.get_pyiceberg_catalog_config.side_effect = AssertionError(
            "storage helper must not be called"
        )
        mock_registry.get.side_effect = [mock_catalog_plugin, mock_storage_plugin]
        mock_registry.configure.return_value = {}
        mock_table_manager_cls.return_value = MagicMock()
        mock_create_io_manager.return_value = MagicMock()

        create_iceberg_resources(
            catalog_ref=catalog_ref,
            storage_ref=storage_ref,
            runtime_catalog_connection=runtime_connection,
        )

    config = mock_table_manager_cls.call_args.kwargs["config"]
    assert config.catalog_connection_config == {
        "uri": "http://polaris:8181/api/catalog",
        "warehouse": "s3://floe-iceberg",
        "s3.endpoint": "http://compiled-minio:9000",
        "s3.region": "us-east-1",
        "s3.path-style-access": "true",
    }
```

- [ ] **Step 2: Run the resource guard test to verify it fails**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py::TestIcebergWiring::test_create_iceberg_resources_uses_runtime_connection_without_storage_helper -q
```

Expected: fail because `runtime_catalog_connection` is not accepted or the helper is still called.

- [ ] **Step 3: Update resource factory signatures and implementation**

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`:

- Import `RuntimeCatalogConnection` under `TYPE_CHECKING`.
- Remove `_catalog_connection_config_from_binding()`.
- Add `runtime_catalog_connection: RuntimeCatalogConnection | None = None` to `create_iceberg_resources()`.
- Add the same parameter to `try_create_iceberg_resources()`.
- Replace the old merge:

```python
catalog_connection_config = {
    **storage_plugin.get_pyiceberg_catalog_config(),
    **_catalog_connection_config_from_binding(storage_binding),
}
```

with:

```python
from floe_iceberg.runtime_catalog import runtime_catalog_connection_to_pyiceberg_config

catalog_connection_config = runtime_catalog_connection_to_pyiceberg_config(
    runtime_catalog_connection,
)
```

- Keep `storage_binding` only for namespace selection until all callers are moved; do not use it to build catalog connection config.

- [ ] **Step 4: Thread runtime connection from runtime builder**

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py`, replace:

```python
storage_binding = None
deployment = getattr(artifacts, "deployment", None)
if deployment is not None and getattr(deployment, "storage", None) is not None:
    storage_binding = deployment.storage.dagster
```

with:

```python
storage_binding = None
runtime_catalog_connection = None
deployment = getattr(artifacts, "deployment", None)
if deployment is not None and getattr(deployment, "storage", None) is not None:
    storage_binding = deployment.storage.dagster
    from floe_core.runtime_catalog_connection import build_runtime_catalog_connection

    runtime_catalog_connection = build_runtime_catalog_connection(
        storage=deployment.storage,
        catalog=getattr(deployment, "catalog", None),
    )
```

and pass `runtime_catalog_connection=runtime_catalog_connection` to `try_create_iceberg_resources()`.

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`, add an optional `runtime_catalog_connection` parameter to `_create_iceberg_resources()` and forward it.

- [ ] **Step 5: Update existing resource tests**

Update tests that assert storage helper calls to assert the translated runtime connection config instead. Existing tests that call `create_iceberg_resources()` without `runtime_catalog_connection` should expect no catalog connection config unless they pass one explicitly.

- [ ] **Step 6: Run resource wiring tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime.py plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py
git commit -m "Use runtime catalog projection for Dagster resources"
```

## Task 4: Dagster Export Uses Deployment-Derived Runtime Config

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`

- [ ] **Step 1: Add failing export guard test**

Add a test in `TestExportDbtToIceberg`:

```python
def test_export_uses_deployment_runtime_connection_without_storage_helper(
    self,
    context: MagicMock,
    project_dir: Path,
    artifacts_with_catalog: CompiledArtifacts,
) -> None:
    """Export must build writer catalog config from deployment bindings."""
    from floe_core.plugin_types import PluginType

    arrow_table = pa.table({"id": [1]})
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [("main", "customers")]
    mock_conn.execute.return_value.fetch_arrow_table.return_value = arrow_table

    registry = MagicMock()
    catalog_plugin = MagicMock()
    storage_plugin = MagicMock()
    storage_plugin.get_pyiceberg_catalog_config.side_effect = AssertionError(
        "storage helper must not be called"
    )

    def get_side_effect(plugin_type: PluginType, _plugin_name: str) -> MagicMock:
        if plugin_type is PluginType.CATALOG:
            return catalog_plugin
        return storage_plugin

    registry.get.side_effect = get_side_effect
    registry.configure.return_value = {}
    writer = _make_writer_mock()

    with (
        patch("duckdb.connect", return_value=mock_conn),
        patch.object(Path, "exists", return_value=True),
        patch("floe_core.plugin_registry.get_registry", return_value=registry),
        patch(
            "floe_orchestrator_dagster.export.iceberg.DefaultIcebergTableWriter",
            return_value=writer,
        ) as writer_cls,
    ):
        export_dbt_to_iceberg(
            context=context,
            product_name=PRODUCT_NAME,
            project_dir=project_dir,
            artifacts=artifacts_with_catalog,
        )

    assert writer_cls.call_args.kwargs["catalog_connection_config"]["s3.endpoint"] == (
        "http://floe-platform-minio:9000"
    )
```

- [ ] **Step 2: Run export guard test to verify it fails**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py::TestExportDbtToIceberg::test_export_uses_deployment_runtime_connection_without_storage_helper -q
```

Expected: fail because export still calls `storage_plugin.get_pyiceberg_catalog_config()`.

- [ ] **Step 3: Replace export catalog config helper path**

In `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`:

- Remove `_apply_compiled_storage_endpoint()`.
- Add a private helper:

```python
def _runtime_catalog_connection_config(artifacts: CompiledArtifacts) -> dict[str, Any]:
    """Return PyIceberg connection config derived from compiled deployment bindings."""
    deployment = artifacts.deployment
    if deployment is None:
        return {}

    from floe_core.runtime_catalog_connection import build_runtime_catalog_connection
    from floe_iceberg.runtime_catalog import runtime_catalog_connection_to_pyiceberg_config

    connection = build_runtime_catalog_connection(
        storage=deployment.storage,
        catalog=deployment.catalog,
    )
    return runtime_catalog_connection_to_pyiceberg_config(connection)
```

- Replace:

```python
catalog_connection_config = _apply_compiled_storage_endpoint(
    storage_plugin.get_pyiceberg_catalog_config(),
    artifacts,
)
```

with:

```python
catalog_connection_config = _runtime_catalog_connection_config(artifacts)
```

- [ ] **Step 4: Update export tests**

Update tests that configure `storage_plugin.get_pyiceberg_catalog_config.return_value` only to influence writer config. Those tests should instead assert deployment-derived values or stop asserting helper calls. Keep storage plugin `configure()` validation assertions.

- [ ] **Step 5: Run export tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py
git commit -m "Use deployment runtime config for Dagster export"
```

## Task 5: Dagster Validation Uses Deployment-Derived Runtime Config

**Files:**
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py`

- [ ] **Step 1: Add failing validation guard test**

Add a test in `plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py`:

```python
def test_connect_catalog_from_artifacts_uses_deployment_runtime_connection_without_storage_helper() -> None:
    """Validation must connect with deployment-derived config, not storage helper config."""
    artifacts = _make_artifacts(
        deployment=_make_storage_deployment("http://compiled-minio:9000"),
    )
    catalog_plugin = MagicMock()
    storage_plugin = MagicMock()
    storage_plugin.get_pyiceberg_catalog_config.side_effect = AssertionError(
        "storage helper must not be called"
    )
    registry = MagicMock()

    def get_side_effect(plugin_type: PluginType, _name: str) -> MagicMock:
        if plugin_type is PluginType.CATALOG:
            return catalog_plugin
        return storage_plugin

    registry.get.side_effect = get_side_effect
    registry.configure.return_value = MagicMock()

    with patch("floe_core.plugin_registry.get_registry", return_value=registry):
        connect_catalog_from_artifacts(artifacts)

    catalog_plugin.connect.assert_called_once()
    assert catalog_plugin.connect.call_args.kwargs["config"]["s3.endpoint"] == (
        "http://compiled-minio:9000"
    )
```

- [ ] **Step 2: Run validation guard test to verify it fails**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py::test_connect_catalog_from_artifacts_uses_deployment_runtime_connection_without_storage_helper -q
```

Expected: fail because validation still calls `storage_plugin.get_pyiceberg_catalog_config()`.

- [ ] **Step 3: Replace validation catalog config helper path**

In `connect_catalog_from_artifacts()` replace:

```python
catalog_connection_config = storage_plugin.get_pyiceberg_catalog_config()
if artifacts.deployment is not None and artifacts.deployment.storage is not None:
    storage = artifacts.deployment.storage
    catalog_connection_config = {
        **catalog_connection_config,
        "s3.endpoint": storage.endpoint.internal_url,
        "s3.region": storage.endpoint.region,
    }
```

with:

```python
from floe_core.runtime_catalog_connection import build_runtime_catalog_connection
from floe_iceberg.runtime_catalog import runtime_catalog_connection_to_pyiceberg_config

deployment = artifacts.deployment
catalog_connection_config = runtime_catalog_connection_to_pyiceberg_config(
    build_runtime_catalog_connection(
        storage=deployment.storage if deployment is not None else None,
        catalog=deployment.catalog if deployment is not None else None,
    )
)
```

- [ ] **Step 4: Update validation tests**

Remove assertions that `storage_plugin.get_pyiceberg_catalog_config()` is called. Preserve assertions that catalog and storage plugin configs are validated via registry configuration.

- [ ] **Step 5: Run validation tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py
git commit -m "Use deployment runtime config for Iceberg validation"
```

## Task 6: Remove Writer Reflective Helper Fallback

**Files:**
- Modify: `packages/floe-iceberg/src/floe_iceberg/writer.py`
- Test: `packages/floe-iceberg/tests/unit/test_writer.py`

- [ ] **Step 1: Replace fallback test with explicit-config guard**

In `packages/floe-iceberg/tests/unit/test_writer.py`, replace `test_catalog_config_uses_storage_plugin_fallback` with:

```python
@pytest.mark.requirement("AC-318")
def test_catalog_config_without_explicit_config_does_not_probe_storage_plugin() -> None:
    """Writer must not discover catalog config through storage plugin internals."""

    class StoragePlugin:
        def get_pyiceberg_catalog_config(self) -> dict[str, str]:
            raise AssertionError("storage helper must not be called")

    catalog = _WriteCapableCatalog()
    catalog_plugin = _CatalogPlugin(catalog)
    writer = DefaultIcebergTableWriter(
        catalog_plugin=catalog_plugin,
        storage_plugin=StoragePlugin(),
    )

    writer.ensure_namespace("customer_360")

    assert catalog_plugin.connect_configs == [{}]
```

- [ ] **Step 2: Run writer guard test to verify it fails**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_writer.py::test_catalog_config_without_explicit_config_does_not_probe_storage_plugin -q
```

Expected: fail because writer still probes `get_pyiceberg_catalog_config()`.

- [ ] **Step 3: Remove reflective helper probing from writer**

In `packages/floe-iceberg/src/floe_iceberg/writer.py`, replace `_catalog_config()` with:

```python
def _catalog_config(self) -> dict[str, Any]:
    if self._catalog_connection_config is not None:
        return self._catalog_connection_config
    return {}
```

Update the `storage_plugin` constructor docstring line to:

```python
storage_plugin: Storage plugin used for file I/O and storage-owned behavior.
```

- [ ] **Step 4: Run writer tests**

Run:

```bash
uv run pytest packages/floe-iceberg/tests/unit/test_writer.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add packages/floe-iceberg/src/floe_iceberg/writer.py packages/floe-iceberg/tests/unit/test_writer.py
git commit -m "Remove writer storage config probing"
```

## Task 7: Compatibility Search Guard And Focused Regression Suite

**Files:**
- Modify: `tests/contract/test_storage_binding_security.py`

- [ ] **Step 1: Add failing production-consumer search test**

Append to `tests/contract/test_storage_binding_security.py`:

```python
def test_first_party_runtime_paths_do_not_consume_storage_pyiceberg_helper() -> None:
    """Dagster and writer runtime code must not consume storage-owned catalog config."""
    repo_root = Path(__file__).resolve().parents[2]
    searched_roots = [
        repo_root / "plugins" / "floe-orchestrator-dagster" / "src",
        repo_root / "packages" / "floe-iceberg" / "src",
    ]
    offenders: list[str] = []

    for root in searched_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "def get_pyiceberg_catalog_config" in text:
                continue
            if "get_pyiceberg_catalog_config(" in text:
                offenders.append(str(path.relative_to(repo_root)))

    assert offenders == []
```

Add `from pathlib import Path` if the file does not already import it.

- [ ] **Step 2: Run guard test**

Run:

```bash
uv run pytest tests/contract/test_storage_binding_security.py::test_first_party_runtime_paths_do_not_consume_storage_pyiceberg_helper -q
```

Expected after prior tasks: pass. If it fails, remove remaining first-party runtime calls before continuing.

- [ ] **Step 3: Run focused regression suite**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_runtime_catalog_connection.py packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py::TestRuntimeCatalogConnection packages/floe-iceberg/tests/unit/test_runtime_catalog.py packages/floe-iceberg/tests/unit/test_writer.py plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py tests/contract/test_storage_binding_security.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit Task 7**

Run:

```bash
git add tests/contract/test_storage_binding_security.py
git commit -m "Guard binding-first Iceberg runtime ownership"
```

## Task 8: Final Validation And Documentation Check

**Files:**
- Verify all changed files.
- Modify docs only if implementation names differ materially from the design.

- [ ] **Step 1: Run static gates**

Run:

```bash
make lint
make typecheck
```

Expected: both pass.

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_runtime_catalog_connection.py packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py packages/floe-iceberg/tests/unit/test_runtime_catalog.py packages/floe-iceberg/tests/unit/test_writer.py plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py tests/contract/test_storage_binding_security.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run compatibility search**

Run:

```bash
rg -n "get_pyiceberg_catalog_config\\(" plugins/floe-orchestrator-dagster/src packages/floe-iceberg/src -g '*.py'
```

Expected: no output.

- [ ] **Step 4: Run docs validators if docs changed**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
```

Expected: both pass.

- [ ] **Step 5: Commit final docs adjustment if needed**

If docs changed:

```bash
git add docs/superpowers/specs/2026-05-09-binding-first-dagster-iceberg-runtime-design.md
git commit -m "Update binding-first runtime implementation notes"
```

If no docs changed, skip this commit.

## Remote Validation Gate

This plan changes runtime/product source. After the PR is ready and local/CI validation is green, run the real remote lane before declaring runtime confidence:

```bash
DEVPOD_REMOTE_E2E_MAKE_TARGET=test-e2e-full make devpod-test
devpod list
```

Separate product failures from infra failures. If Hetzner resources are created, verify and clean billable resources before closeout.

## Self-Review

- Spec coverage: Tasks 1-2 add the neutral projection and PyIceberg translation; Tasks 3-5 migrate Dagster resource/export/validation; Task 6 removes writer probing; Task 7 adds guard coverage; Task 8 verifies local completion and docs.
- Red-flag scan: no banned planning tokens remain.
- Type consistency: `RuntimeCatalogConnection` is the neutral core model; `runtime_catalog_connection_to_pyiceberg_config()` is the PyIceberg-specific translator; Dagster paths receive either `RuntimeCatalogConnection` or build it from `DeploymentConfig`.
