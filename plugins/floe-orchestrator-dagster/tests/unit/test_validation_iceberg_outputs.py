"""Unit tests for Iceberg output validation library API.

The sibling ``tests/unit/validation/test_iceberg_outputs.py`` covers reset
and CLI behavior for the same module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest
from floe_core.plugin_types import PluginType
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    DagsterStorageBinding,
    DbtStorageBinding,
    DeploymentConfig,
    IngestionOutputTable,
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
from testing.fixtures.credentials import (
    get_polaris_credentials,
    get_polaris_oauth2_server_uri,
    get_polaris_scope,
    get_polaris_warehouse,
)

from floe_orchestrator_dagster.validation.iceberg_outputs import (
    expected_iceberg_tables,
    validate_iceberg_outputs,
)

POLARIS_ENDPOINT = "http://polaris:8181/api/catalog"
POLARIS_CLIENT_ID, POLARIS_CLIENT_SECRET = get_polaris_credentials()
POLARIS_CREDENTIAL = f"{POLARIS_CLIENT_ID}:{POLARIS_CLIENT_SECRET}"
POLARIS_SCOPE = get_polaris_scope()
POLARIS_TOKEN_URL = get_polaris_oauth2_server_uri(catalog_endpoint=POLARIS_ENDPOINT)
POLARIS_WAREHOUSE = get_polaris_warehouse()


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
    ingestion_outputs: list[IngestionOutputTable] | None = None,
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
        ingestion_outputs=ingestion_outputs or [],
    )


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_validate_iceberg_outputs_completes_secret_free_polaris_config_from_env() -> None:
    """Runtime validation must hydrate Polaris credentials outside CompiledArtifacts."""
    artifacts = _make_artifacts(
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name="mart_customer_360", compute="duckdb")],
            default_compute="duckdb",
        )
    )
    catalog_config = dict(artifacts.plugins.catalog.config or {})
    catalog_config["warehouse"] = POLARIS_WAREHOUSE
    catalog_config["oauth2"] = {
        "client_id": POLARIS_CLIENT_ID,
        "token_url": POLARIS_TOKEN_URL,
        "scope": POLARIS_SCOPE,
    }
    artifacts = artifacts.model_copy(
        update={
            "plugins": artifacts.plugins.model_copy(
                update={
                    "catalog": artifacts.plugins.catalog.model_copy(
                        update={"config": catalog_config}
                    )
                }
            )
        }
    )
    catalog_plugin = MagicMock()
    storage_plugin = MagicMock()
    catalog = MagicMock()
    catalog.load_table.return_value = MagicMock()
    catalog_plugin.connect.return_value = catalog
    storage_plugin.get_pyiceberg_catalog_config.return_value = {}
    registry = MagicMock()

    def get_side_effect(plugin_type: PluginType, _name: str) -> MagicMock:
        if plugin_type is PluginType.CATALOG:
            return catalog_plugin
        return storage_plugin

    registry.get.side_effect = get_side_effect
    registry.configure.return_value = MagicMock()

    with (
        patch.dict("os.environ", {"POLARIS_CREDENTIAL": POLARIS_CREDENTIAL}, clear=True),
        patch("floe_core.plugin_registry.get_registry", return_value=registry),
    ):
        validate_iceberg_outputs(artifacts)

    registry.configure.assert_has_calls(
        [
            call(
                PluginType.CATALOG,
                "polaris",
                {
                    "uri": "memory://",
                    "warehouse": POLARIS_WAREHOUSE,
                    "oauth2": {
                        "client_id": POLARIS_CLIENT_ID,
                        "client_secret": POLARIS_CLIENT_SECRET,
                        "token_url": POLARIS_TOKEN_URL,
                        "scope": POLARIS_SCOPE,
                    },
                },
            )
        ],
        any_order=True,
    )


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_expected_iceberg_tables_fails_when_transforms_missing() -> None:
    """Deriving default expected tables requires compiled transform metadata."""
    artifacts = _make_artifacts(transforms=None)

    with pytest.raises(RuntimeError, match="CompiledArtifacts has no transforms"):
        expected_iceberg_tables(artifacts)


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_expected_iceberg_tables_includes_ingestion_outputs_when_requested() -> None:
    """Callers can opt into validating compiled ingestion output tables."""
    artifacts = _make_artifacts(transforms=None).model_copy(
        update={
            "ingestion_outputs": [
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
            ]
        }
    )

    assert expected_iceberg_tables(artifacts, include_ingestion=True) == ["bronze.raw_transactions"]


@pytest.mark.requirement("ALPHA-ICEBERG")
def test_expected_iceberg_tables_deduplicates_after_qualification() -> None:
    """Expected table derivation removes duplicate identifiers without reordering."""
    artifacts = _make_artifacts(
        transforms=ResolvedTransforms(
            models=[
                ResolvedModel(name="orders", compute="duckdb"),
                ResolvedModel(name="customer_360.dim_customer", compute="duckdb"),
            ],
            default_compute="duckdb",
        ),
        ingestion_outputs=[
            IngestionOutputTable(
                source_name="raw-orders",
                source_type="filesystem",
                logical_table="raw.orders",
                physical_table="customer_360.orders",
                file_format="csv",
                source_path="./seeds/orders.csv",
                write_mode="replace",
                schema_contract="evolve",
            ),
            IngestionOutputTable(
                source_name="dim-customer",
                source_type="filesystem",
                logical_table="customer_360.dim_customer",
                physical_table="customer_360.dim_customer",
                file_format="csv",
                source_path="./seeds/dim_customer.csv",
                write_mode="replace",
                schema_contract="evolve",
            ),
        ],
    )

    assert expected_iceberg_tables(artifacts, include_ingestion=True) == [
        "customer_360.orders",
        "customer_360.dim_customer",
    ]
    assert expected_iceberg_tables(
        artifacts,
        expected_tables=[
            "orders",
            "customer_360.orders",
            "analytics.orders",
            "analytics.orders",
        ],
    ) == [
        "customer_360.orders",
        "analytics.orders",
    ]


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
