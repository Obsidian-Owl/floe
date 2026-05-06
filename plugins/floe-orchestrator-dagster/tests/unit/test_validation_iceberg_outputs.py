"""Unit tests for Iceberg output validation library API.

The sibling ``tests/unit/validation/test_iceberg_outputs.py`` covers reset
and CLI behavior for the same module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from floe_core.plugin_types import PluginType
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    DagsterStorageBinding,
    DbtStorageBinding,
    DeploymentConfig,
    KubernetesSecretRef,
    ObservabilityConfig,
    PluginRef,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageServiceEndpoint,
)
from floe_core.schemas.telemetry import ResourceAttributes, TelemetryConfig

from floe_orchestrator_dagster.validation.iceberg_outputs import (
    expected_iceberg_tables,
    validate_iceberg_outputs,
)


def _make_storage_deployment(endpoint: str) -> DeploymentConfig:
    """Build a compiled MinIO storage deployment binding."""
    return DeploymentConfig(
        storage=StorageDeploymentBinding(
            provider="minio",
            endpoint=StorageServiceEndpoint(
                internal_url=endpoint,
                external_url=endpoint,
                region="us-east-1",
                warehouse_path="s3://floe-iceberg",
            ),
            credentials=StorageCredentialBinding(
                mode="kubernetes-secret",
                secret_ref=KubernetesSecretRef(
                    name="floe-platform-minio",
                    namespace="floe-system",
                    keys={
                        "accessKeyId": "root-user",
                        "secretAccessKey": "root-password",  # pragma: allowlist secret
                    },
                ),
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
    )


def _make_artifacts(
    *,
    transforms: ResolvedTransforms | None = None,
    deployment: DeploymentConfig | None = None,
) -> CompiledArtifacts:
    """Build compiled artifacts with configured catalog and storage plugins."""
    return CompiledArtifacts(
        version="0.5.0",
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version="0.5.0",
            source_hash="sha256:abc123def456",
            product_name="customer-360",
            product_version="1.0.0",
        ),
        identity={
            "product_id": "default.customer_360",
            "domain": "default",
            "repository": "github.com/test/customer-360",
        },
        mode="simple",
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="customer-360",
                    service_version="1.0.0",
                    deployment_environment="dev",
                    floe_namespace="default",
                    floe_product_name="customer-360",
                    floe_product_version="1.0.0",
                    floe_mode="dev",
                ),
            ),
            lineage=True,
            lineage_namespace="customer-360",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="polaris", version="0.1.0", config={"uri": "memory://"}),
            storage=PluginRef(type="minio", version="1.0.0", config={"endpoint": "memory://"}),
        ),
        transforms=transforms,
        deployment=deployment,
    )


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_expected_iceberg_tables_fails_when_transforms_missing() -> None:
    """Deriving default expected tables requires compiled transform metadata."""
    artifacts = _make_artifacts(transforms=None)

    with pytest.raises(RuntimeError, match="CompiledArtifacts has no transforms"):
        expected_iceberg_tables(artifacts)


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_validate_iceberg_outputs_passes_storage_catalog_config_to_catalog() -> None:
    """Validation must pass StoragePlugin catalog config into catalog.connect()."""
    artifacts = _make_artifacts(
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name="mart_customer_360", compute="duckdb")],
            default_compute="duckdb",
        )
    )
    catalog_plugin = MagicMock()
    storage_plugin = MagicMock()
    catalog = MagicMock()
    table = MagicMock()
    catalog_config = {
        "s3.endpoint": "http://minio:9000",
        "s3.path-style-access": "true",
    }
    catalog_plugin.connect.return_value = catalog
    catalog.load_table.return_value = table
    storage_plugin.get_pyiceberg_catalog_config.return_value = catalog_config
    registry = MagicMock()

    def get_side_effect(plugin_type: PluginType, _name: str) -> MagicMock:
        if plugin_type is PluginType.CATALOG:
            return catalog_plugin
        return storage_plugin

    registry.get.side_effect = get_side_effect
    registry.configure.return_value = MagicMock()

    with patch("floe_core.plugin_registry.get_registry", return_value=registry):
        result = validate_iceberg_outputs(artifacts)

    catalog_plugin.connect.assert_called_once_with(config=catalog_config)
    storage_plugin.get_pyiceberg_catalog_config.assert_called_once_with()
    storage_plugin.get_pyiceberg_fileio.assert_not_called()
    catalog.load_table.assert_called_once_with("customer_360.mart_customer_360")
    assert result.table_names == ["customer_360.mart_customer_360"]


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_validate_iceberg_outputs_prefers_compiled_storage_endpoint() -> None:
    """Compiled storage binding endpoint must override plugin config endpoint."""
    artifacts = _make_artifacts(
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name="mart_customer_360", compute="duckdb")],
            default_compute="duckdb",
        ),
        deployment=_make_storage_deployment("http://compiled-minio:9000"),
    )
    catalog_plugin = MagicMock()
    storage_plugin = MagicMock()
    catalog = MagicMock()
    catalog.load_table.return_value = MagicMock()
    storage_plugin.get_pyiceberg_catalog_config.return_value = {
        "s3.endpoint": "http://plugin-config-minio:9000",
        "s3.region": "us-west-2",
        "s3.path-style-access": "true",
    }
    catalog_plugin.connect.return_value = catalog
    registry = MagicMock()

    def get_side_effect(plugin_type: PluginType, _name: str) -> MagicMock:
        if plugin_type is PluginType.CATALOG:
            return catalog_plugin
        return storage_plugin

    registry.get.side_effect = get_side_effect
    registry.configure.return_value = MagicMock()

    with patch("floe_core.plugin_registry.get_registry", return_value=registry):
        validate_iceberg_outputs(artifacts)

    catalog_plugin.connect.assert_called_once()
    connect_config = catalog_plugin.connect.call_args.kwargs["config"]
    assert connect_config["s3.endpoint"] == "http://compiled-minio:9000"
    assert connect_config["s3.region"] == "us-east-1"
    assert connect_config["s3.path-style-access"] == "true"
