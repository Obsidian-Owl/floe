"""Compilation tests for storage deployment bindings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from floe_core.compilation.errors import CompilationException
from floe_core.compilation.stages import CompilationStage, compile_pipeline
from floe_core.composition.models import PluginRequirements, RequirementSet
from floe_core.plugin_errors import PluginConfigurationError
from floe_core.plugins.catalog import CatalogPlugin
from floe_core.plugins.storage import FileIO, StoragePlugin
from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    CredentialRef,
    DagsterStorageBinding,
    DbtStorageBinding,
    KubernetesSecretRef,
    PolarisCatalogDeploymentBinding,
    StorageCapabilities,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageServiceEndpoint,
    StorageWarehouse,
)

ROOT = Path(__file__).resolve().parents[5]
pytestmark = pytest.mark.requirement("AC-4")


@pytest.fixture(autouse=True)
def _disable_plugin_instrumentation_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep storage compilation tests focused on deployment binding behavior."""
    import floe_core.compilation.stages as stages

    monkeypatch.setattr(stages, "_discover_plugins_for_audit", lambda: [])


def test_demo_compile_emits_minio_storage_deployment_binding() -> None:
    """Demo compilation must attach the MinIO deployment storage binding."""
    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        ROOT / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.plugins is not None
    assert artifacts.plugins.storage is not None
    assert artifacts.plugins.storage.type == "minio"
    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None

    storage = artifacts.deployment.storage
    payload = storage.model_dump_json()

    assert storage.provider == "minio"
    assert storage.endpoint.internal_url == "http://floe-platform-minio:9000"
    assert storage.endpoint.warehouse_path == "s3://floe-iceberg"
    assert storage.warehouse is not None
    assert storage.credentials.mode == "kubernetes-secret"
    assert storage.credentials.secret_ref is not None
    assert storage.credentials.secret_ref.name == "floe-platform-minio-credentials"
    assert storage.dbt.profile_fragment["s3_endpoint"] == "http://floe-platform-minio:9000"
    assert storage.dagster.resources["endpoint_url"] == "http://floe-platform-minio:9000"
    assert artifacts.deployment.catalog is not None
    assert artifacts.deployment.catalog.provider == "polaris"
    assert artifacts.deployment.catalog.polaris.warehouse == "floe-demo"
    assert (
        artifacts.deployment.catalog.polaris.endpoint_internal
        == artifacts.deployment.storage.endpoint.internal_url
    )
    assert (
        artifacts.deployment.catalog.polaris.default_base_location
        == artifacts.deployment.storage.warehouse.uri
    )
    assert artifacts.dbt_profiles is not None
    dev_profile = artifacts.dbt_profiles["customer-360"]["outputs"]["dev"]
    assert dev_profile["s3_endpoint"] == "http://floe-platform-minio:9000"
    assert dev_profile["s3_region"] == "us-east-1"
    assert dev_profile["s3_access_key_id"] == "{{ env_var('AWS_ACCESS_KEY_ID') }}"
    assert "minio" + "admin" not in payload


def test_storage_binding_compile_uses_isolated_plugin_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage binding compilation must not mutate the global plugin registry."""
    import floe_core.plugin_registry as plugin_registry

    def fail_global_registry() -> None:
        raise AssertionError("compile must use an isolated storage plugin registry")

    monkeypatch.setattr(plugin_registry, "get_registry", fail_global_registry)

    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        ROOT / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None
    assert artifacts.deployment.storage.provider == "minio"


def test_missing_storage_plugin_raises_structured_compilation_error(tmp_path: Path) -> None:
    """Storage plugin resolution failures must use the compilation error model."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"]["storage"]["type"] = "missing-storage"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            manifest_path,
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "E201"
    assert "missing-storage" in error.message
    assert error.context == {"storage_plugin": "missing-storage"}


def test_storage_plugin_binding_failure_raises_structured_compilation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-resolution StoragePlugin failures must use the compilation error model."""

    class FailingStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "minio"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_config_schema(self) -> None:
            return None

        def get_pyiceberg_fileio(self) -> FileIO:
            raise NotImplementedError

        def get_warehouse_uri(self, namespace: str) -> str:
            return f"s3://unused/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> Any:
            raise PluginConfigurationError(
                "minio",
                [{"field": "endpoint", "message": "post-resolution failure"}],
            )

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class IsolatedFailingRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> FailingStoragePlugin:
            return FailingStoragePlugin()

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedFailingRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "E201"
    assert "could not build deployment binding" in error.message
    assert error.context == {"storage_plugin": "minio"}


def test_incompatible_storage_catalog_composition_raises_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compilation must reject catalog storage requirements MinIO cannot satisfy."""

    class FakeStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "minio"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_pyiceberg_fileio(self) -> FileIO:
            raise NotImplementedError

        def get_warehouse_uri(self, namespace: str) -> str:
            return f"s3://floe-iceberg/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> StorageDeploymentBinding:
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
                allowed_locations=["s3://floe-iceberg"],
                credentials=StorageCredentialBinding(
                    mode="kubernetes-secret",
                    secret_ref=KubernetesSecretRef(
                        name="floe-platform-minio-credentials",
                        namespace="floe-system",
                        keys={
                            "accessKeyId": "accesskey",
                            "secretAccessKey": "secretkey",  # pragma: allowlist secret
                        },
                    ),
                ),
                capabilities=StorageCapabilities(
                    protocols=["s3-compatible"],
                    credential_modes=["kubernetes-secret"],
                    path_style_access=True,
                ),
                dbt=DbtStorageBinding(
                    profile_name="floe",
                    target_name="dev",
                    schema_name="analytics",
                ),
                dagster=DagsterStorageBinding(
                    resource_key="storage",
                    asset_io_manager_key="io_manager",
                ),
            )

    class NativeS3OnlyCatalogPlugin(CatalogPlugin):
        @property
        def name(self) -> str:
            return "polaris"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def connect(self, config: dict[str, Any]) -> Any:
            raise NotImplementedError

        def create_namespace(
            self,
            namespace: str,
            properties: dict[str, str] | None = None,
        ) -> None:
            raise NotImplementedError

        def vend_credentials(self, table_path: str, operations: list[str]) -> dict[str, Any]:
            raise NotImplementedError

        def list_namespaces(self, parent: str | None = None) -> list[str]:
            raise NotImplementedError

        def delete_namespace(self, namespace: str) -> None:
            raise NotImplementedError

        def create_table(
            self,
            identifier: str,
            schema: dict[str, Any],
            location: str | None = None,
            properties: dict[str, str] | None = None,
        ) -> None:
            raise NotImplementedError

        def list_tables(self, namespace: str) -> list[str]:
            raise NotImplementedError

        def drop_table(self, identifier: str, purge: bool = False) -> None:
            raise NotImplementedError

        def get_storage_requirements(self) -> PluginRequirements:
            return PluginRequirements(
                plugin_type="catalog",
                plugin_name="polaris",
                requirements=RequirementSet(
                    protocols=["s3"],
                    credential_modes=["kubernetes-secret"],
                ),
            )

        def build_catalog_deployment(
            self,
            storage: StorageDeploymentBinding,
        ) -> CatalogDeploymentBinding:
            return CatalogDeploymentBinding(
                provider="polaris",
                polaris=PolarisCatalogDeploymentBinding(
                    storage_type="S3",
                    warehouse="floe-demo",
                    default_base_location="s3://unused",
                    allowed_locations=[],
                    endpoint="http://unused",
                    endpoint_internal="http://unused",
                    path_style_access=False,
                    sts_unavailable=True,
                    credential_refs={
                        "accessKeyId": CredentialRef(source="none", name="none"),
                        "secretAccessKey": CredentialRef(source="none", name="none"),
                    },
                ),
            )

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class IsolatedCompositionRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> StoragePlugin | CatalogPlugin:
            if plugin_type == PluginType.STORAGE:
                return FakeStoragePlugin()
            if plugin_type == PluginType.CATALOG:
                return NativeS3OnlyCatalogPlugin()
            raise AssertionError(f"unexpected plugin request: {plugin_type}:{name}")

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedCompositionRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_PROTOCOL_UNSUPPORTED"
    assert "catalog polaris requires one of protocols ['s3']" in error.message
    assert error.context == {
        "composition_issues": [
            {
                "severity": "error",
                "code": "COMPOSITION_PROTOCOL_UNSUPPORTED",
                "message": (
                    "catalog polaris requires one of protocols ['s3']; "
                    "storage minio provides ['s3-compatible']"
                ),
                "plugins": ["storage:minio", "catalog:polaris"],
            }
        ],
        "storage_plugin": "minio",
        "catalog_plugin": "polaris",
    }


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
        capabilities=CapabilitySet(
            catalog_providers=["iceberg-rest"],
            table_formats=["iceberg"],
        ),
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
    assert (
        dlt.iceberg_catalog_env["PYICEBERG_CATALOG__POLARIS__URI"]
        == "http://floe-platform-polaris:8181/api/catalog"
    )
    assert dlt.iceberg_catalog_env["PYICEBERG_CATALOG__POLARIS__WAREHOUSE"] == "floe-demo"
    assert dlt.env_refs == {
        "accessKeyId": "AWS_ACCESS_KEY_ID",
        "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
    }
    assert artifacts.deployment.catalog is not None
    assert artifacts.deployment.catalog.polaris.warehouse == "floe-demo"
    assert artifacts.plugins.ingestion is not None
    assert artifacts.plugins.ingestion.config is not None
    assert "catalog_config" not in artifacts.plugins.ingestion.config


def test_transform_only_compile_skips_manifest_selected_dlt_binding(tmp_path: Path) -> None:
    """A selected ingestion plugin is inactive unless product sources were resolved."""
    spec_path = tmp_path / "floe.yaml"
    spec_path.write_text(
        """
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: transform-only
  version: 1.0.0
transforms:
  - name: orders
"""
    )
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    artifacts = compile_pipeline(spec_path, manifest_path, emit_lineage=False)

    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None
    assert artifacts.deployment.catalog is not None
    assert artifacts.deployment.ingestion is None
    assert artifacts.plugins.ingestion is not None
    assert artifacts.plugins.ingestion.config is not None
    assert "sources" not in artifacts.plugins.ingestion.config


def test_dlt_ingestion_deployment_binding_ignores_host_secret_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compile-time dlt deployment binding must not read host credential env."""
    secret_env = {
        "POLARIS_CREDENTIAL": "compile-host-polaris-credential",
        "AWS_ACCESS_KEY_ID": "compile-host-access-key",
        "AWS_SECRET_ACCESS_KEY": "compile-host-secret-key",  # pragma: allowlist secret
    }
    for name, value in secret_env.items():
        monkeypatch.setenv(name, value)

    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        ROOT / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.deployment is not None
    assert artifacts.deployment.ingestion is not None
    dlt = artifacts.deployment.ingestion.dlt
    payload = artifacts.deployment.ingestion.model_dump_json()

    for name, value in secret_env.items():
        assert name not in dlt.iceberg_catalog_env
        assert value not in dlt.iceberg_catalog_env.values()
        assert value not in payload
    assert dlt.env_refs == {
        "accessKeyId": "AWS_ACCESS_KEY_ID",
        "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
    }
    assert all("CREDENTIAL" not in key for key in dlt.iceberg_catalog_env)
    assert all("ACCESS_KEY" not in key for key in dlt.iceberg_catalog_env)


def test_ingestion_plugin_binding_failure_raises_structured_compilation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-resolution IngestionPlugin failures must use the compilation error model."""
    from floe_ingestion_dlt.errors import PipelineConfigurationError
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    def fail_build_deployment_binding(
        self: DltIngestionPlugin,
        *,
        storage: StorageDeploymentBinding,
        catalog: CatalogDeploymentBinding,
    ) -> None:
        _ = (self, storage, catalog)
        raise PipelineConfigurationError("post-resolution ingestion failure")

    monkeypatch.setattr(
        DltIngestionPlugin,
        "build_deployment_binding",
        fail_build_deployment_binding,
    )

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "E201"
    assert error.message == "Ingestion plugin 'dlt' could not build deployment binding"
    assert error.context == {
        "ingestion_plugin": "dlt",
        "storage_plugin": "minio",
        "catalog_plugin": "polaris",
    }


def test_ingestion_plugin_requirements_failure_raises_structured_compilation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IngestionPlugin requirement hook failures must use the compilation error model."""
    from floe_ingestion_dlt.plugin import DltIngestionPlugin

    def fail_get_composition_requirements(self: DltIngestionPlugin) -> None:
        _ = self
        raise ValueError("requirements unavailable")

    monkeypatch.setattr(
        DltIngestionPlugin,
        "get_composition_requirements",
        fail_get_composition_requirements,
    )

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "E201"
    assert error.message == "Ingestion plugin 'dlt' could not resolve composition requirements"
    assert error.context == {
        "ingestion_plugin": "dlt",
        "storage_plugin": "minio",
        "catalog_plugin": "polaris",
    }


def test_non_ingestion_plugin_registered_for_ingestion_raises_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compile validates the ingestion plugin type before invoking hooks."""
    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    original_registry = plugin_registry.PluginRegistry

    class NotIngestionPlugin:
        pass

    class RegistryWithWrongIngestionPlugin:
        def __init__(self) -> None:
            self._delegate = original_registry()

        def discover_all(self) -> None:
            self._delegate.discover_all()

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            if plugin_type == PluginType.INGESTION:
                return None
            self._delegate.configure(plugin_type, name, config)
            return None

        def get(self, plugin_type: PluginType, name: str) -> Any:
            if plugin_type == PluginType.INGESTION:
                return NotIngestionPlugin()
            return self._delegate.get(plugin_type, name)

    monkeypatch.setattr(plugin_registry, "PluginRegistry", RegistryWithWrongIngestionPlugin)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "E201"
    assert error.message == "Plugin 'dlt' is not an IngestionPlugin"
    assert error.context == {"ingestion_plugin": "dlt"}


def test_dlt_ingestion_without_storage_raises_composition_error(tmp_path: Path) -> None:
    """dlt ingestion requires storage composition even when storage is omitted."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"].pop("storage")
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            manifest_path,
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_STORAGE_MISSING"
    assert error.context["storage_plugin"] is None
    assert error.context["catalog_plugin"] == "polaris"
    assert error.context["ingestion_plugin"] == "dlt"
    assert error.context["composition_issues"][0]["code"] == "COMPOSITION_STORAGE_MISSING"


def test_dlt_ingestion_without_catalog_raises_composition_error(tmp_path: Path) -> None:
    """dlt ingestion requires catalog composition even when catalog is omitted."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"].pop("catalog")
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            manifest_path,
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_CATALOG_MISSING"
    assert error.context["storage_plugin"] == "minio"
    assert error.context["catalog_plugin"] is None
    assert error.context["ingestion_plugin"] == "dlt"
    assert error.context["composition_issues"][0]["code"] == "COMPOSITION_CATALOG_MISSING"
