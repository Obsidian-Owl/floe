"""Unit tests for the native AWS Glue catalog plugin."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import tomllib
from floe_core.plugin_errors import CatalogUnavailableError, NotSupportedError
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
from pydantic import ValidationError

from floe_catalog_glue.config import GlueCatalogConfig
from floe_catalog_glue.plugin import GlueCatalogPlugin


def _s3_storage_binding(
    *,
    credential_mode: str = "workload-identity",
    protocol: str = "s3",
) -> StorageDeploymentBinding:
    if credential_mode == "workload-identity":
        credentials = StorageCredentialBinding(
            mode="workload-identity",
            service_account_ref="floe-provider-tests",
        )
    elif credential_mode == "environment":
        credentials = StorageCredentialBinding(
            mode="environment",
            env_refs={
                "accessKeyId": "AWS_ACCESS_KEY_ID",
                "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
                "sessionToken": "AWS_SESSION_TOKEN",
            },
        )
    else:
        credentials = StorageCredentialBinding(mode="none")

    return StorageDeploymentBinding(
        provider="aws-s3",
        protocol=protocol,
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
        credentials=credentials,
        capabilities=StorageCapabilities(
            protocols=[protocol],
            credential_modes=[credential_mode],
            identity_modes=["aws-irsa", "aws-pod-identity"]
            if credential_mode == "workload-identity"
            else [],
            sts_supported=True,
            path_style_access=False,
        ),
        provisioning=StorageProvisioningIntent(
            enabled=False,
            mode="external",
            default_create_policy="must-exist",
        ),
        runtime=StorageRuntimeBinding(pyiceberg_properties={"s3.region": "ap-southeast-2"}),
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


class TestPluginMetadata:
    """Test plugin metadata and config schema."""

    def test_plugin_metadata(self) -> None:
        plugin = GlueCatalogPlugin()

        assert plugin.name == "glue"
        assert plugin.version.count(".") == 2
        assert plugin.floe_api_version == "1.0"
        assert plugin.description == "AWS Glue catalog plugin for Iceberg table management"
        assert plugin.tracer_name == "floe.catalog.glue"

    def test_get_config_schema_returns_glue_config(self) -> None:
        assert GlueCatalogPlugin().get_config_schema() is GlueCatalogConfig


class TestGlueCatalogConfig:
    """Test AWS Glue config validation."""

    def test_workload_identity_config_requires_service_account(self) -> None:
        with pytest.raises(ValidationError, match="service_account_ref"):
            GlueCatalogConfig(
                region="ap-southeast-2",
                credential_mode="workload-identity",
            )

    def test_kubernetes_secret_config_requires_secret_name(self) -> None:
        with pytest.raises(ValidationError, match="credential_secret_name"):
            GlueCatalogConfig(
                region="ap-southeast-2",
                credential_mode="kubernetes-secret",
            )

    def test_environment_config_rejects_credential_refs(self) -> None:
        with pytest.raises(ValidationError, match="only accepts environment variable names"):
            GlueCatalogConfig(
                region="ap-southeast-2",
                credential_mode="environment",
                service_account_ref="floe-provider-tests",
            )

    def test_catalog_id_must_be_aws_account_id(self) -> None:
        with pytest.raises(ValidationError, match="catalog_id"):
            GlueCatalogConfig(
                region="ap-southeast-2",
                catalog_id="not-an-account",
                credential_mode="environment",
            )

    def test_endpoint_override_must_be_http_url(self) -> None:
        with pytest.raises(ValidationError, match="endpoint_override"):
            GlueCatalogConfig(
                region="ap-southeast-2",
                endpoint_override="glue.ap-southeast-2.amazonaws.com",
                credential_mode="environment",
            )

    def test_config_defaults_are_native_aws(self) -> None:
        config = GlueCatalogConfig(
            region="ap-southeast-2",
            credential_mode="workload-identity",
            service_account_ref="floe-provider-tests",
        )

        assert config.warehouse is None
        assert config.database_prefix is None
        assert config.skip_archive is True
        assert config.max_retries is None
        assert config.retry_mode is None


class TestStorageComposition:
    """Test Glue composition contracts."""

    def test_storage_requirements_for_workload_identity(self) -> None:
        config = GlueCatalogConfig(
            region="ap-southeast-2",
            credential_mode="workload-identity",
            service_account_ref="floe-provider-tests",
        )
        requirements = GlueCatalogPlugin(config=config).get_storage_requirements()

        assert requirements.plugin_type == "catalog"
        assert requirements.plugin_name == "glue"
        assert requirements.requirements.protocols == ["s3"]
        assert requirements.requirements.credential_modes == ["workload-identity"]
        assert requirements.requirements.identity_modes == ["aws-irsa", "aws-pod-identity"]
        assert requirements.requirements.requires_server_side_storage_access is True
        assert requirements.requirements.supports_no_sts is False
        assert requirements.requirements.supports_path_style_access is False

    def test_build_catalog_deployment_uses_storage_warehouse_by_default(self) -> None:
        config = GlueCatalogConfig(
            region="ap-southeast-2",
            catalog_id="278833447053",
            database_prefix="floe_provider_",
            credential_mode="workload-identity",
            service_account_ref="floe-provider-tests",
            skip_archive=True,
            max_retries=5,
            retry_mode="standard",
        )
        binding = GlueCatalogPlugin(config=config).build_catalog_deployment(_s3_storage_binding())

        assert binding.provider == "glue"
        assert binding.glue is not None
        assert binding.glue.catalog_name == "glue"
        assert binding.glue.region == "ap-southeast-2"
        assert binding.glue.warehouse == "s3://floe-provider-tests/warehouse/"
        assert binding.glue.catalog_id == "278833447053"
        assert binding.glue.database_prefix == "floe_provider_"
        assert binding.glue.skip_archive is True
        assert binding.glue.max_retries == 5
        assert binding.glue.retry_mode == "standard"
        assert binding.glue.credential_refs["accessKeyId"].source == "workload-identity"
        assert binding.glue.credential_refs["accessKeyId"].name == "floe-provider-tests"
        assert binding.glue.properties == {}
        assert binding.iceberg_rest is None
        assert binding.dbt is None
        assert "AWS_SECRET_ACCESS_KEY" not in binding.model_dump_json()
        assert "raw-secret-value" not in binding.model_dump_json()

    def test_build_catalog_deployment_honors_warehouse_override(self) -> None:
        config = GlueCatalogConfig(
            region="ap-southeast-2",
            warehouse="s3://custom-warehouse/prefix/",
            credential_mode="environment",
        )
        binding = GlueCatalogPlugin(config=config).build_catalog_deployment(
            _s3_storage_binding(credential_mode="environment")
        )

        assert binding.glue is not None
        assert binding.glue.warehouse == "s3://custom-warehouse/prefix/"
        assert binding.glue.credential_refs["secretAccessKey"].source == "environment"
        assert binding.glue.credential_refs["secretAccessKey"].name == "AWS_SECRET_ACCESS_KEY"

    def test_build_catalog_deployment_rejects_non_s3_storage(self) -> None:
        config = GlueCatalogConfig(region="ap-southeast-2", credential_mode="environment")
        plugin = GlueCatalogPlugin(config=config)

        with pytest.raises(ValueError, match="requires storage protocol 's3'"):
            plugin.build_catalog_deployment(_s3_storage_binding(protocol="s3-compatible"))

    def test_build_catalog_deployment_rejects_incompatible_credential_mode(self) -> None:
        config = GlueCatalogConfig(region="ap-southeast-2", credential_mode="environment")
        plugin = GlueCatalogPlugin(config=config)

        with pytest.raises(ValueError, match="requires storage credential mode"):
            plugin.build_catalog_deployment(_s3_storage_binding(credential_mode="none"))


class TestPyIcebergConnection:
    """Test PyIceberg Glue connection delegation."""

    def test_connect_builds_glue_catalog_config_without_aws_call(self) -> None:
        config = GlueCatalogConfig(
            region="ap-southeast-2",
            warehouse="s3://floe-provider-tests/warehouse/",
            catalog_id="278833447053",
            endpoint_override="https://glue.ap-southeast-2.amazonaws.com",
            credential_mode="environment",
            skip_archive=False,
            max_retries=5,
            retry_mode="standard",
        )
        plugin = GlueCatalogPlugin(config=config)
        catalog = Mock()

        with patch("floe_catalog_glue.plugin.load_catalog", return_value=catalog) as load_catalog:
            assert plugin.connect({"client.region": "ap-southeast-2"}) is catalog

        load_catalog.assert_called_once_with(
            "glue",
            type="glue",
            warehouse="s3://floe-provider-tests/warehouse/",
            **{
                "client.region": "ap-southeast-2",
                "glue.region": "ap-southeast-2",
                "glue.id": "278833447053",
                "glue.endpoint": "https://glue.ap-southeast-2.amazonaws.com",
                "glue.skip-archive": "false",
                "glue.max-retries": 5,
                "glue.retry-mode": "standard",
            },
        )


class TestCatalogOperations:
    """Test required CatalogPlugin operations delegate to PyIceberg."""

    @pytest.fixture()
    def plugin_with_catalog(self) -> GlueCatalogPlugin:
        plugin = GlueCatalogPlugin(
            config=GlueCatalogConfig(
                region="ap-southeast-2",
                warehouse="s3://floe-provider-tests/warehouse/",
                credential_mode="environment",
            )
        )
        catalog = Mock()
        catalog.list_namespaces.return_value = [("bronze",), ("silver", "sales")]
        catalog.list_tables.return_value = [("bronze", "customers")]
        plugin._catalog = catalog
        return plugin

    def test_namespace_and_table_methods_delegate_to_catalog(
        self, plugin_with_catalog: GlueCatalogPlugin
    ) -> None:
        plugin_with_catalog.create_namespace("bronze", {"owner": "data"})
        assert plugin_with_catalog.list_namespaces() == ["bronze", "silver.sales"]
        assert plugin_with_catalog.list_tables("bronze") == ["bronze.customers"]
        plugin_with_catalog.create_table("bronze.customers", {"type": "struct"})
        plugin_with_catalog.drop_table("bronze.customers", purge=True)
        plugin_with_catalog.delete_namespace("bronze")

        catalog = plugin_with_catalog._catalog
        catalog.create_namespace.assert_called_once_with("bronze", properties={"owner": "data"})
        catalog.list_namespaces.assert_called_once_with()
        catalog.list_tables.assert_called_once_with("bronze")
        catalog.create_table.assert_called_once_with("bronze.customers", {"type": "struct"})
        catalog.drop_table.assert_called_once_with("bronze.customers", purge=True)
        catalog.drop_namespace.assert_called_once_with("bronze")

    def test_catalog_methods_raise_when_not_connected(self) -> None:
        plugin = GlueCatalogPlugin(
            config=GlueCatalogConfig(region="ap-southeast-2", credential_mode="environment")
        )

        with pytest.raises(CatalogUnavailableError, match="call connect"):
            plugin.list_namespaces()

    def test_vend_credentials_not_supported(self) -> None:
        plugin = GlueCatalogPlugin(
            config=GlueCatalogConfig(region="ap-southeast-2", credential_mode="environment")
        )

        with pytest.raises(NotSupportedError, match="does not vend credentials"):
            plugin.vend_credentials("bronze.customers", ["READ"])


class TestPackageMetadata:
    """Test package metadata without requiring workspace registration."""

    def test_pyproject_declares_floe_catalog_entry_point(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        assert pyproject["project"]["name"] == "floe-catalog-glue"
        assert pyproject["project"]["entry-points"]["floe.catalogs"] == {
            "glue": "floe_catalog_glue.plugin:GlueCatalogPlugin"
        }
