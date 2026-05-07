"""Compilation tests for storage deployment bindings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from floe_core.compilation.errors import CompilationException
from floe_core.compilation.stages import CompilationStage, compile_pipeline
from floe_core.composition.models import (
    CapabilitySet,
    PluginCapabilities,
    PluginRequirements,
    RequirementSet,
)
from floe_core.plugin_errors import PluginConfigurationError
from floe_core.plugins.catalog import CatalogPlugin
from floe_core.plugins.identity import IdentityPlugin, TokenValidationResult, UserInfo
from floe_core.plugins.secrets import SecretsPlugin
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


def test_composition_error_codes_are_documented() -> None:
    """Public composition failures must be listed for stable operator diagnostics."""
    from floe_core.compilation.errors import ERROR_CODES

    expected_codes = {
        "COMPOSITION_PLUGIN_MISSING",
        "COMPOSITION_PLUGIN_INTERFACE_INVALID",
        "COMPOSITION_PLUGIN_CONFIG_INVALID",
        "COMPOSITION_STORAGE_MISSING",
        "COMPOSITION_PROTOCOL_UNSUPPORTED",
        "COMPOSITION_CREDENTIAL_MODE_UNSUPPORTED",
        "COMPOSITION_DEPLOYMENT_BINDING_MISSING",
        "COMPOSITION_RENDERER_PRECONDITION_FAILED",
    }

    assert expected_codes.issubset(ERROR_CODES)


class FakeSecretsPlugin(SecretsPlugin):
    """Secrets plugin used to prove compiler composition wiring."""

    @property
    def name(self) -> str:
        return "fake-secrets"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def get_config_schema(self) -> None:
        return None

    def get_secret(self, key: str) -> str | None:
        return None

    def set_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> None:
        return None

    def list_secrets(self, prefix: str = "") -> list[str]:
        return []

    def get_secret_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            plugin_type="secrets",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["external-secret-sync"],
                secret_projection_modes=["external-secret-sync"],
                providers=["infisical"],
            ),
        )


class FakeIdentityPlugin(IdentityPlugin):
    """Identity plugin used to prove compiler composition wiring."""

    @property
    def name(self) -> str:
        return "fake-identity"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def get_config_schema(self) -> None:
        return None

    def authenticate(self, credentials: dict[str, Any]) -> str | None:
        return None

    def get_user_info(self, token: str) -> UserInfo | None:
        return None

    def validate_token(self, token: str) -> TokenValidationResult:
        return TokenValidationResult(valid=False)

    def get_identity_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            plugin_type="identity",
            plugin_name=self.name,
            capabilities=CapabilitySet(
                credential_modes=["workload-identity"],
                identity_modes=["aws-irsa"],
                providers=["aws"],
            ),
        )


class ExternalSecretStoragePlugin(StoragePlugin):
    """Storage fake that selects external-secret-sync credentials."""

    @property
    def name(self) -> str:
        return "aws-object-storage"

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
        return f"s3://warehouse/{namespace}"

    def get_dbt_profile_config(self) -> dict[str, Any]:
        return {}

    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        return {}

    def get_helm_values_override(self) -> dict[str, Any]:
        return {}

    def get_deployment_binding(self) -> StorageDeploymentBinding:
        return StorageDeploymentBinding(
            provider="s3",
            protocol="s3",
            endpoint=StorageServiceEndpoint(
                internal_url="https://s3.us-east-1.amazonaws.com",
                external_url="https://s3.us-east-1.amazonaws.com",
                region="us-east-1",
                warehouse_path="s3://warehouse",
                path_style_access=False,
            ),
            warehouse=StorageWarehouse(uri="s3://warehouse", bucket="warehouse"),
            credentials=StorageCredentialBinding(
                mode="external-secret-sync",
                secret_ref=KubernetesSecretRef(
                    name="s3-credentials",
                    namespace="floe-system",
                    keys={
                        "accessKeyId": "access-key-id",
                        "secretAccessKey": "secret-access-key",  # pragma: allowlist secret
                    },
                ),
            ),
            capabilities=StorageCapabilities(
                protocols=["s3"],
                credential_modes=["external-secret-sync"],
                path_style_access=False,
            ),
            dbt=DbtStorageBinding(
                profile_name="floe",
                target_name="dev",
                schema_name="analytics",
            ),
            dagster=DagsterStorageBinding(
                resource_key="s3_storage",
                asset_io_manager_key="iceberg_io_manager",
            ),
        )


class ExternalSecretCatalogPlugin(CatalogPlugin):
    """Catalog fake requiring external-secret-sync projection."""

    @property
    def name(self) -> str:
        return "glue"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def get_config_schema(self) -> None:
        return None

    def connect(self, config: dict[str, Any]) -> Any:
        raise NotImplementedError

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        return None

    def vend_credentials(self, table_path: str, operations: list[str]) -> dict[str, Any]:
        return {}

    def list_namespaces(self, parent: str | None = None) -> list[str]:
        return []

    def delete_namespace(self, namespace: str) -> None:
        return None

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        return None

    def list_tables(self, namespace: str) -> list[str]:
        return []

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        return None

    def get_storage_requirements(self) -> PluginRequirements:
        return PluginRequirements(
            plugin_type="catalog",
            plugin_name="glue",
            requirements=RequirementSet(
                protocols=["s3"],
                credential_modes=["external-secret-sync"],
                secret_projection_modes=["external-secret-sync"],
                providers=["infisical"],
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
                default_base_location="s3://warehouse",
                allowed_locations=["s3://warehouse"],
                endpoint=storage.endpoint.external_url,
                endpoint_internal=storage.endpoint.internal_url,
                path_style_access=False,
                sts_unavailable=True,
                credential_refs={
                    "accessKeyId": CredentialRef(
                        source="kubernetes-secret",
                        name="s3-credentials",
                        key="access-key-id",
                    ),
                    "secretAccessKey": CredentialRef(
                        source="kubernetes-secret",
                        name="s3-credentials",
                        key="secret-access-key",
                    ),
                },
            ),
        )


def _install_external_secret_registry(
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_secrets: bool,
) -> None:
    """Install a compiler registry with external-secret-sync storage/catalog fakes."""
    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class IsolatedRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> Any:
            if plugin_type == PluginType.STORAGE:
                return ExternalSecretStoragePlugin()
            if plugin_type == PluginType.CATALOG:
                return ExternalSecretCatalogPlugin()
            if include_secrets and plugin_type == PluginType.SECRETS:
                return FakeSecretsPlugin()
            if plugin_type == PluginType.COMPUTE:
                from floe_compute_duckdb.plugin import DuckDBComputePlugin

                return DuckDBComputePlugin()
            raise AssertionError(f"unexpected plugin lookup: {plugin_type} {name}")

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedRegistry)


def _external_secret_manifest_path(
    tmp_path: Path,
    *,
    include_secrets: bool,
) -> Path:
    """Write a manifest selecting external-secret-sync fake storage/catalog plugins."""
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"]["storage"] = {"type": "aws-object-storage"}
    manifest["plugins"]["catalog"] = {"type": "glue"}
    if include_secrets:
        manifest["plugins"]["secrets"] = {"type": "fake-secrets"}
    else:
        manifest["plugins"].pop("secrets", None)
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return manifest_path


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
    assert error.code == "COMPOSITION_PLUGIN_MISSING"
    assert "missing-storage" in error.message
    assert error.context == {"storage_plugin": "missing-storage"}


def test_wrong_storage_plugin_interface_raises_composition_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plugin loaded from storage selection must implement StoragePlugin."""

    class NotStoragePlugin:
        name = "minio"

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class WrongInterfaceRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> NotStoragePlugin:
            return NotStoragePlugin()

    monkeypatch.setattr(plugin_registry, "PluginRegistry", WrongInterfaceRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_PLUGIN_INTERFACE_INVALID"
    assert error.context == {"storage_plugin": "minio"}


def test_storage_plugin_configure_failure_raises_composition_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configure-time storage plugin validation must use the config-invalid code."""

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class ConfigFailingRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            raise PluginConfigurationError(
                name,
                [{"field": "endpoint", "message": "required"}],
            )

        def get(self, plugin_type: PluginType, name: str) -> Any:
            raise AssertionError("get() must not be reached after configure failure")

    monkeypatch.setattr(plugin_registry, "PluginRegistry", ConfigFailingRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_PLUGIN_CONFIG_INVALID"
    assert error.context == {"storage_plugin": "minio"}


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
    assert error.code == "COMPOSITION_PLUGIN_CONFIG_INVALID"
    assert "could not build deployment binding" in error.message
    assert error.context == {"storage_plugin": "minio"}


def test_storage_plugin_missing_deployment_binding_raises_composition_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage plugins without deployment bindings must produce a specific code."""

    class LegacyStoragePlugin(StoragePlugin):
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

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class LegacyStorageRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> LegacyStoragePlugin:
            return LegacyStoragePlugin()

    monkeypatch.setattr(plugin_registry, "PluginRegistry", LegacyStorageRegistry)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            ROOT / "demo" / "manifest.yaml",
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_DEPLOYMENT_BINDING_MISSING"
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


def test_compile_passes_selected_secret_and_identity_capabilities_to_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compilation should validate non-baseline credential modes with providers."""

    class IdentityStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "aws-object-storage"

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
            return f"s3://warehouse/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> StorageDeploymentBinding:
            return StorageDeploymentBinding(
                provider="s3",
                protocol="s3",
                endpoint=StorageServiceEndpoint(
                    internal_url="https://s3.us-east-1.amazonaws.com",
                    external_url="https://s3.us-east-1.amazonaws.com",
                    region="us-east-1",
                    warehouse_path="s3://warehouse",
                    path_style_access=False,
                ),
                warehouse=StorageWarehouse(uri="s3://warehouse", bucket="warehouse"),
                credentials=StorageCredentialBinding(
                    mode="workload-identity",
                    service_account_ref="floe-runtime",
                ),
                capabilities=StorageCapabilities(
                    protocols=["s3"],
                    credential_modes=["workload-identity", "external-secret-sync"],
                    identity_modes=["aws-irsa"],
                    sts_supported=True,
                    path_style_access=False,
                ),
                dbt=DbtStorageBinding(
                    profile_name="floe",
                    target_name="dev",
                    schema_name="analytics",
                ),
                dagster=DagsterStorageBinding(
                    resource_key="s3_storage",
                    asset_io_manager_key="iceberg_io_manager",
                ),
            )

    class IdentityCatalogPlugin(CatalogPlugin):
        @property
        def name(self) -> str:
            return "glue"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_config_schema(self) -> None:
            return None

        def connect(self, config: dict[str, Any]) -> Any:
            raise NotImplementedError

        def create_namespace(
            self,
            namespace: str,
            properties: dict[str, str] | None = None,
        ) -> None:
            return None

        def vend_credentials(self, table_path: str, operations: list[str]) -> dict[str, Any]:
            return {}

        def list_namespaces(self, parent: str | None = None) -> list[str]:
            return []

        def delete_namespace(self, namespace: str) -> None:
            return None

        def create_table(
            self,
            identifier: str,
            schema: dict[str, Any],
            location: str | None = None,
            properties: dict[str, str] | None = None,
        ) -> None:
            return None

        def list_tables(self, namespace: str) -> list[str]:
            return []

        def drop_table(self, identifier: str, purge: bool = False) -> None:
            return None

        def get_storage_requirements(self) -> PluginRequirements:
            return PluginRequirements(
                plugin_type="catalog",
                plugin_name="glue",
                requirements=RequirementSet(
                    protocols=["s3"],
                    credential_modes=["workload-identity"],
                    identity_modes=["aws-irsa"],
                    providers=["aws"],
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
                    default_base_location="s3://warehouse",
                    allowed_locations=["s3://warehouse"],
                    endpoint=storage.endpoint.external_url,
                    endpoint_internal=storage.endpoint.internal_url,
                    path_style_access=False,
                    sts_unavailable=False,
                    credential_refs={
                        "accessKeyId": CredentialRef(source="none", name="none"),
                        "secretAccessKey": CredentialRef(source="none", name="none"),
                    },
                ),
            )

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class IsolatedRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> Any:
            if plugin_type == PluginType.STORAGE:
                return IdentityStoragePlugin()
            if plugin_type == PluginType.CATALOG:
                return IdentityCatalogPlugin()
            if plugin_type == PluginType.SECRETS:
                return FakeSecretsPlugin()
            if plugin_type == PluginType.IDENTITY:
                return FakeIdentityPlugin()
            if plugin_type == PluginType.COMPUTE:
                from floe_compute_duckdb.plugin import DuckDBComputePlugin

                return DuckDBComputePlugin()
            raise AssertionError(f"unexpected plugin lookup: {plugin_type} {name}")

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedRegistry)
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"]["storage"] = {"type": "aws-object-storage"}
    manifest["plugins"]["catalog"] = {"type": "glue"}
    manifest["plugins"]["secrets"] = {"type": "fake-secrets"}
    manifest["plugins"]["identity"] = {"type": "fake-identity"}
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        manifest_path,
        emit_lineage=False,
    )

    assert artifacts.plugins is not None
    assert artifacts.plugins.secrets is not None
    assert artifacts.plugins.secrets.type == "fake-secrets"
    assert artifacts.plugins.identity is not None
    assert artifacts.plugins.identity.type == "fake-identity"
    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None
    assert artifacts.deployment.storage.credentials.mode == "workload-identity"


def test_compile_validates_selected_workload_identity_mode_not_advertised_alternatives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compilation must validate the selected storage credential mode."""

    class MixedModeStoragePlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "aws-object-storage"

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
            return f"s3://warehouse/{namespace}"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

        def get_deployment_binding(self) -> StorageDeploymentBinding:
            return StorageDeploymentBinding(
                provider="s3",
                protocol="s3",
                endpoint=StorageServiceEndpoint(
                    internal_url="https://s3.us-east-1.amazonaws.com",
                    external_url="https://s3.us-east-1.amazonaws.com",
                    region="us-east-1",
                    warehouse_path="s3://warehouse",
                    path_style_access=False,
                ),
                warehouse=StorageWarehouse(uri="s3://warehouse", bucket="warehouse"),
                credentials=StorageCredentialBinding(
                    mode="workload-identity",
                    service_account_ref="floe-runtime",
                ),
                capabilities=StorageCapabilities(
                    protocols=["s3"],
                    credential_modes=["kubernetes-secret", "workload-identity"],
                    identity_modes=["aws-irsa"],
                    sts_supported=True,
                    path_style_access=False,
                ),
                dbt=DbtStorageBinding(
                    profile_name="floe",
                    target_name="dev",
                    schema_name="analytics",
                ),
                dagster=DagsterStorageBinding(
                    resource_key="s3_storage",
                    asset_io_manager_key="iceberg_io_manager",
                ),
            )

    class IdentityAwareCatalogPlugin(CatalogPlugin):
        @property
        def name(self) -> str:
            return "glue"

        @property
        def version(self) -> str:
            return "0.1.0"

        @property
        def floe_api_version(self) -> str:
            return "1.0"

        def get_config_schema(self) -> None:
            return None

        def connect(self, config: dict[str, Any]) -> Any:
            raise NotImplementedError

        def create_namespace(
            self,
            namespace: str,
            properties: dict[str, str] | None = None,
        ) -> None:
            return None

        def vend_credentials(self, table_path: str, operations: list[str]) -> dict[str, Any]:
            return {}

        def list_namespaces(self, parent: str | None = None) -> list[str]:
            return []

        def delete_namespace(self, namespace: str) -> None:
            return None

        def create_table(
            self,
            identifier: str,
            schema: dict[str, Any],
            location: str | None = None,
            properties: dict[str, str] | None = None,
        ) -> None:
            return None

        def list_tables(self, namespace: str) -> list[str]:
            return []

        def drop_table(self, identifier: str, purge: bool = False) -> None:
            return None

        def get_storage_requirements(self) -> PluginRequirements:
            return PluginRequirements(
                plugin_type="catalog",
                plugin_name="glue",
                requirements=RequirementSet(
                    protocols=["s3"],
                    credential_modes=["kubernetes-secret", "workload-identity"],
                    identity_modes=["aws-irsa"],
                    providers=["aws"],
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
                    default_base_location="s3://warehouse",
                    allowed_locations=["s3://warehouse"],
                    endpoint=storage.endpoint.external_url,
                    endpoint_internal=storage.endpoint.internal_url,
                    path_style_access=False,
                    sts_unavailable=False,
                    credential_refs={
                        "accessKeyId": CredentialRef(source="none", name="none"),
                        "secretAccessKey": CredentialRef(source="none", name="none"),
                    },
                ),
            )

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class IsolatedRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> Any:
            if plugin_type == PluginType.STORAGE:
                return MixedModeStoragePlugin()
            if plugin_type == PluginType.CATALOG:
                return IdentityAwareCatalogPlugin()
            if plugin_type == PluginType.COMPUTE:
                from floe_compute_duckdb.plugin import DuckDBComputePlugin

                return DuckDBComputePlugin()
            raise AssertionError(f"unexpected plugin lookup: {plugin_type} {name}")

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedRegistry)
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"]["storage"] = {"type": "aws-object-storage"}
    manifest["plugins"]["catalog"] = {"type": "glue"}
    manifest["plugins"].pop("identity", None)
    manifest["plugins"].pop("secrets", None)
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            manifest_path,
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_IDENTITY_PROVIDER_MISSING"
    assert "identity mode aws-irsa" in error.message
    assert "no identity plugin was selected" in error.message


def test_compile_rejects_selected_storage_mode_not_declared_by_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compiler must reject selected storage credential modes not in capabilities."""

    class MismatchedExternalSecretStoragePlugin(ExternalSecretStoragePlugin):
        def get_deployment_binding(self) -> StorageDeploymentBinding:
            binding = super().get_deployment_binding()
            return binding.model_copy(
                update={
                    "capabilities": StorageCapabilities(
                        protocols=["s3"],
                        credential_modes=["kubernetes-secret"],
                        path_style_access=False,
                    )
                }
            )

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    class IsolatedRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> Any:
            if plugin_type == PluginType.STORAGE:
                return MismatchedExternalSecretStoragePlugin()
            if plugin_type == PluginType.CATALOG:
                return ExternalSecretCatalogPlugin()
            if plugin_type == PluginType.SECRETS:
                return FakeSecretsPlugin()
            if plugin_type == PluginType.COMPUTE:
                from floe_compute_duckdb.plugin import DuckDBComputePlugin

                return DuckDBComputePlugin()
            raise AssertionError(f"unexpected plugin lookup: {plugin_type} {name}")

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedRegistry)
    manifest_path = _external_secret_manifest_path(tmp_path, include_secrets=True)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            manifest_path,
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "E201"
    assert (
        "Storage plugin 'aws-object-storage' selected credential mode 'external-secret-sync' "
        "but declares credential modes ['kubernetes-secret']"
    ) in error.message
    assert error.context == {
        "storage_plugin": "aws-object-storage",
        "selected_credential_mode": "external-secret-sync",
        "declared_credential_modes": ["kubernetes-secret"],
    }


def test_compile_requires_secrets_provider_for_selected_external_secret_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """External-secret-sync selected mode must require a capable secrets provider."""
    _install_external_secret_registry(monkeypatch, include_secrets=False)
    manifest_path = _external_secret_manifest_path(tmp_path, include_secrets=False)

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(
            ROOT / "demo" / "customer-360" / "floe.yaml",
            manifest_path,
            emit_lineage=False,
        )

    error = exc_info.value.error
    assert error.stage == CompilationStage.RESOLVE
    assert error.code == "COMPOSITION_SECRET_PROVIDER_MISSING"
    assert "secret projection mode external-secret-sync" in error.message
    assert "no secrets plugin was selected" in error.message
    assert error.context == {
        "composition_issues": [
            {
                "severity": "error",
                "code": "COMPOSITION_SECRET_PROVIDER_MISSING",
                "message": (
                    "catalog glue requires one of secret providers ['infisical'] "
                    "for secret projection mode external-secret-sync but no secrets "
                    "plugin was selected"
                ),
                "plugins": ["catalog:glue"],
            }
        ],
        "storage_plugin": "aws-object-storage",
        "catalog_plugin": "glue",
    }


def test_compile_accepts_selected_external_secret_sync_with_capable_secrets_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """External-secret-sync selected mode compiles with matching secrets capabilities."""
    _install_external_secret_registry(monkeypatch, include_secrets=True)
    manifest_path = _external_secret_manifest_path(tmp_path, include_secrets=True)

    artifacts = compile_pipeline(
        ROOT / "demo" / "customer-360" / "floe.yaml",
        manifest_path,
        emit_lineage=False,
    )

    assert artifacts.plugins is not None
    assert artifacts.plugins.secrets is not None
    assert artifacts.plugins.secrets.type == "fake-secrets"
    assert artifacts.deployment is not None
    assert artifacts.deployment.storage is not None
    assert artifacts.deployment.storage.credentials.mode == "external-secret-sync"


def test_storage_only_compile_validates_selected_identity_plugin_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured identity plugin should be ABC-validated even without catalog."""

    class StorageOnlyPlugin(StoragePlugin):
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
            return f"s3://warehouse/{namespace}"

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
                    internal_url="http://minio:9000",
                    external_url="http://minio:9000",
                    region="us-east-1",
                    warehouse_path="s3://warehouse",
                    path_style_access=True,
                ),
                warehouse=StorageWarehouse(uri="s3://warehouse", bucket="warehouse"),
                credentials=StorageCredentialBinding(
                    mode="kubernetes-secret",
                    secret_ref=KubernetesSecretRef(
                        name="minio-credentials",
                        namespace="floe-system",
                        keys={
                            "accessKeyId": "root-user",
                            "secretAccessKey": "root-password",  # pragma: allowlist secret
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
                    resource_key="minio_storage",
                    asset_io_manager_key="iceberg_io_manager",
                ),
            )

    class NotIdentityPlugin(StoragePlugin):
        @property
        def name(self) -> str:
            return "fake-identity"

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
            return "s3://unused"

        def get_dbt_profile_config(self) -> dict[str, Any]:
            return {}

        def get_dagster_io_manager_config(self) -> dict[str, Any]:
            return {}

        def get_helm_values_override(self) -> dict[str, Any]:
            return {}

    class IsolatedRegistry:
        def discover_all(self) -> None:
            return None

        def configure(
            self,
            plugin_type: PluginType,
            name: str,
            config: dict[str, Any],
        ) -> None:
            return None

        def get(self, plugin_type: PluginType, name: str) -> Any:
            if plugin_type == PluginType.STORAGE:
                return StorageOnlyPlugin()
            if plugin_type == PluginType.IDENTITY:
                return NotIdentityPlugin()
            raise AssertionError(f"unexpected plugin lookup: {plugin_type} {name}")

    import floe_core.plugin_registry as plugin_registry
    from floe_core.plugin_types import PluginType

    monkeypatch.setattr(plugin_registry, "PluginRegistry", IsolatedRegistry)
    manifest_path = tmp_path / "manifest.yaml"
    manifest = yaml.safe_load((ROOT / "demo" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["plugins"].pop("catalog", None)
    manifest["plugins"]["storage"] = {"type": "minio"}
    manifest["plugins"]["identity"] = {"type": "fake-identity"}
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
    assert "is not an IdentityPlugin" in error.message
    assert error.context == {"identity_plugin": "fake-identity"}
