"""Unit tests for the native AWS Glue catalog plugin."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
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

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from floe_catalog_glue.config import GlueCatalogConfig
from floe_catalog_glue.plugin import GlueCatalogPlugin

TEST_REGION = "ap-southeast-2"
TEST_BUCKET = "floe-provider-tests"
TEST_SERVICE_ACCOUNT = "floe-provider-tests"
TEST_ACCOUNT_ID = "278833447053"
TEST_WAREHOUSE_URI = f"s3://{TEST_BUCKET}/warehouse/"
TEST_S3_ENDPOINT = f"https://s3.{TEST_REGION}.amazonaws.com"
TEST_GLUE_ENDPOINT = f"https://glue.{TEST_REGION}.amazonaws.com"


def _s3_storage_binding(
    *,
    credential_mode: str = "workload-identity",
    protocol: str = "s3",
) -> StorageDeploymentBinding:
    if credential_mode == "workload-identity":
        credentials = StorageCredentialBinding(
            mode="workload-identity",
            service_account_ref=TEST_SERVICE_ACCOUNT,
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
    elif credential_mode == "kubernetes-secret":
        from floe_core.schemas.compiled_artifacts import KubernetesSecretRef

        credentials = StorageCredentialBinding(
            mode="kubernetes-secret",
            secret_ref=KubernetesSecretRef(
                name="aws-glue-creds",  # pragma: allowlist secret
                namespace="data-platform",  # pragma: allowlist secret
                keys={
                    "accessKeyId": "accessKeyId",
                    "secretAccessKey": "secretAccessKey",  # pragma: allowlist secret
                    "sessionToken": "sessionToken",
                },
            ),
        )
    else:
        credentials = StorageCredentialBinding(mode="none")

    return StorageDeploymentBinding(
        provider="aws-s3",
        protocol=protocol,
        endpoint=StorageServiceEndpoint(
            internal_url=TEST_S3_ENDPOINT,
            external_url=TEST_S3_ENDPOINT,
            region=TEST_REGION,
            warehouse_path=TEST_WAREHOUSE_URI,
            path_style_access=False,
        ),
        warehouse=StorageWarehouse(
            uri=TEST_WAREHOUSE_URI,
            bucket=TEST_BUCKET,
            prefix="warehouse/",
        ),
        allowed_locations=[TEST_WAREHOUSE_URI],
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
        runtime=StorageRuntimeBinding(pyiceberg_properties={"s3.region": TEST_REGION}),
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

    @pytest.mark.requirement("CATALOG-GLUE-001")
    def test_plugin_metadata(self) -> None:
        """Plugin metadata exposes the stable glue identity and tracer name."""
        plugin = GlueCatalogPlugin()

        assert plugin.name == "glue"
        assert plugin.version.count(".") == 2
        assert plugin.floe_api_version == "1.0"
        assert plugin.description == "AWS Glue catalog plugin for Iceberg table management"
        assert plugin.tracer_name == "floe.catalog.glue"

    @pytest.mark.requirement("CATALOG-GLUE-002")
    def test_get_config_schema_returns_glue_config(self) -> None:
        """Plugin config schema points consumers at the Glue config model."""
        assert GlueCatalogPlugin().get_config_schema() is GlueCatalogConfig


class TestGlueCatalogConfig:
    """Test AWS Glue config validation."""

    @pytest.mark.requirement("CATALOG-GLUE-003")
    def test_workload_identity_config_requires_service_account(self) -> None:
        """Workload-identity mode rejects config without a service account ref."""
        with pytest.raises(ValidationError, match="service_account_ref"):
            GlueCatalogConfig(
                region=TEST_REGION,
                credential_mode="workload-identity",
            )

    @pytest.mark.requirement("CATALOG-GLUE-004")
    def test_kubernetes_secret_config_requires_secret_name(self) -> None:
        """Kubernetes-secret mode rejects config without a Secret reference."""
        with pytest.raises(ValidationError, match="credential_secret_name"):
            GlueCatalogConfig(
                region=TEST_REGION,
                credential_mode="kubernetes-secret",
            )

    @pytest.mark.requirement("CATALOG-GLUE-005")
    def test_environment_config_rejects_credential_refs(self) -> None:
        """Environment mode rejects identity references to keep credential modes exclusive."""
        with pytest.raises(ValidationError, match="only accepts environment variable names"):
            GlueCatalogConfig(
                region=TEST_REGION,
                credential_mode="environment",
                service_account_ref=TEST_SERVICE_ACCOUNT,
            )

    @pytest.mark.requirement("CATALOG-GLUE-006")
    def test_catalog_id_must_be_aws_account_id(self) -> None:
        """Catalog IDs must use the AWS 12-digit account ID shape."""
        with pytest.raises(ValidationError, match="catalog_id"):
            GlueCatalogConfig(
                region=TEST_REGION,
                catalog_id="not-an-account",
                credential_mode="environment",
            )

    @pytest.mark.requirement("CATALOG-GLUE-007")
    def test_endpoint_override_must_be_http_url(self) -> None:
        """Glue endpoint overrides must be explicit HTTP URLs."""
        with pytest.raises(ValidationError, match="endpoint_override"):
            GlueCatalogConfig(
                region=TEST_REGION,
                endpoint_override="glue.ap-southeast-2.amazonaws.com",
                credential_mode="environment",
            )

    @pytest.mark.requirement("CATALOG-GLUE-008")
    def test_config_rejects_raw_aws_credentials(self) -> None:
        """Raw AWS credential fields are rejected to prevent secret embedding."""
        with pytest.raises(ValidationError, match="raw AWS credential fields"):
            GlueCatalogConfig(
                region=TEST_REGION,
                credential_mode="environment",
                access_key_id="AKIAIOSFODNN7EXAMPLE",  # type: ignore[call-arg] # pragma: allowlist secret
            )

    @pytest.mark.requirement("CATALOG-GLUE-009")
    def test_config_rejects_raw_secret_access_key(self) -> None:
        """Raw secret_access_key fields are rejected before config construction."""
        with pytest.raises(ValidationError, match="raw AWS credential fields"):
            GlueCatalogConfig(
                region=TEST_REGION,
                credential_mode="environment",
                secret_access_key="raw-secret-value",  # type: ignore[call-arg] # pragma: allowlist secret
            )

    @pytest.mark.requirement("CATALOG-GLUE-010")
    def test_warehouse_must_be_s3_uri(self) -> None:
        """Warehouse overrides must use s3:// because Glue composes with AWS S3."""
        with pytest.raises(ValidationError, match="s3://"):
            GlueCatalogConfig(
                region=TEST_REGION,
                warehouse="gs://bucket/path/",
                credential_mode="environment",
            )

    @pytest.mark.requirement("CATALOG-GLUE-011")
    def test_warehouse_gets_trailing_slash(self) -> None:
        """Warehouse overrides are normalized to slash-terminated S3 URIs."""
        config = GlueCatalogConfig(
            region=TEST_REGION,
            warehouse="s3://bucket/path",
            credential_mode="environment",
        )

        assert config.warehouse == "s3://bucket/path/"

    @pytest.mark.requirement("CATALOG-GLUE-012")
    def test_config_defaults_are_native_aws(self) -> None:
        """Default Glue config uses AWS-native behavior and no warehouse override."""
        config = GlueCatalogConfig(
            region=TEST_REGION,
            credential_mode="workload-identity",
            service_account_ref=TEST_SERVICE_ACCOUNT,
        )

        assert config.warehouse is None
        assert config.database_prefix is None
        assert config.skip_archive is True
        assert config.max_retries is None
        assert config.retry_mode is None


class TestStorageComposition:
    """Test Glue composition contracts."""

    @pytest.mark.requirement("CATALOG-GLUE-013")
    def test_storage_requirements_for_workload_identity(self) -> None:
        """Glue requires native S3 and compatible workload identity modes."""
        config = GlueCatalogConfig(
            region=TEST_REGION,
            credential_mode="workload-identity",
            service_account_ref=TEST_SERVICE_ACCOUNT,
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

    @pytest.mark.requirement("CATALOG-GLUE-014")
    def test_build_catalog_deployment_uses_storage_warehouse_by_default(self) -> None:
        """Glue deployment binding derives warehouse and credentials from storage."""
        config = GlueCatalogConfig(
            region=TEST_REGION,
            catalog_id=TEST_ACCOUNT_ID,
            database_prefix="floe_provider_",
            credential_mode="workload-identity",
            service_account_ref=TEST_SERVICE_ACCOUNT,
            skip_archive=True,
            max_retries=5,
            retry_mode="standard",
        )
        binding = GlueCatalogPlugin(config=config).build_catalog_deployment(_s3_storage_binding())

        assert binding.provider == "glue"
        assert binding.glue is not None
        assert binding.glue.catalog_name == "glue"
        assert binding.glue.region == TEST_REGION
        assert binding.glue.warehouse == TEST_WAREHOUSE_URI
        assert binding.glue.catalog_id == TEST_ACCOUNT_ID
        assert binding.glue.database_prefix == "floe_provider_"
        assert binding.glue.skip_archive is True
        assert binding.glue.max_retries == 5
        assert binding.glue.retry_mode == "standard"
        assert binding.glue.credential_refs["accessKeyId"].source == "workload-identity"
        assert binding.glue.credential_refs["accessKeyId"].name == TEST_SERVICE_ACCOUNT
        assert binding.glue.properties == {}
        assert binding.iceberg_rest is None
        assert binding.dbt is None
        assert "AWS_SECRET_ACCESS_KEY" not in binding.model_dump_json()
        assert "raw-secret-value" not in binding.model_dump_json()

    @pytest.mark.requirement("CATALOG-GLUE-015")
    def test_build_catalog_deployment_honors_warehouse_override(self) -> None:
        """Glue warehouse overrides replace the composed storage warehouse URI."""
        config = GlueCatalogConfig(
            region=TEST_REGION,
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

    @pytest.mark.requirement("CATALOG-GLUE-016")
    def test_build_catalog_deployment_with_kubernetes_secret(self) -> None:
        """Kubernetes-secret mode maps configured Secret keys into CredentialRefs."""
        config = GlueCatalogConfig(
            region=TEST_REGION,
            credential_mode="kubernetes-secret",
            credential_secret_name="aws-glue-creds",  # pragma: allowlist secret
            credential_secret_namespace="data-platform",  # pragma: allowlist secret
        )
        binding = GlueCatalogPlugin(config=config).build_catalog_deployment(
            _s3_storage_binding(credential_mode="kubernetes-secret")
        )

        assert binding.glue is not None
        assert binding.glue.credential_refs["accessKeyId"].source == "kubernetes-secret"
        assert binding.glue.credential_refs["accessKeyId"].name == "aws-glue-creds"
        assert binding.glue.credential_refs["accessKeyId"].key == "accessKeyId"
        assert binding.glue.credential_refs["secretAccessKey"].key == "secretAccessKey"
        assert binding.glue.credential_refs["sessionToken"].key == "sessionToken"

    @pytest.mark.requirement("CATALOG-GLUE-017")
    def test_build_catalog_deployment_rejects_non_s3_storage(self) -> None:
        """Glue rejects S3-compatible storage because live AWS Glue requires native S3."""
        config = GlueCatalogConfig(region=TEST_REGION, credential_mode="environment")
        plugin = GlueCatalogPlugin(config=config)

        with pytest.raises(ValueError, match="requires storage protocol 's3'"):
            plugin.build_catalog_deployment(_s3_storage_binding(protocol="s3-compatible"))

    @pytest.mark.requirement("CATALOG-GLUE-018")
    def test_build_catalog_deployment_rejects_incompatible_credential_mode(self) -> None:
        """Glue rejects storage bindings whose credential mode cannot satisfy Glue."""
        config = GlueCatalogConfig(region=TEST_REGION, credential_mode="environment")
        plugin = GlueCatalogPlugin(config=config)

        with pytest.raises(ValueError, match="requires storage credential mode"):
            plugin.build_catalog_deployment(_s3_storage_binding(credential_mode="none"))


class TestPyIcebergConnection:
    """Test PyIceberg Glue connection delegation."""

    @pytest.mark.requirement("CATALOG-GLUE-019")
    def test_connect_builds_glue_catalog_config_without_aws_call(self) -> None:
        """connect builds PyIceberg Glue config without contacting AWS in tests."""
        config = GlueCatalogConfig(
            region=TEST_REGION,
            warehouse=TEST_WAREHOUSE_URI,
            catalog_id=TEST_ACCOUNT_ID,
            endpoint_override=TEST_GLUE_ENDPOINT,
            credential_mode="environment",
            skip_archive=False,
            max_retries=5,
            retry_mode="standard",
        )
        plugin = GlueCatalogPlugin(config=config)
        catalog = Mock()

        with patch("floe_catalog_glue.plugin.load_catalog", return_value=catalog) as load_catalog:
            assert plugin.connect({"client.region": TEST_REGION}) is catalog

        load_catalog.assert_called_once_with(
            "glue",
            type="glue",
            warehouse=TEST_WAREHOUSE_URI,
            **{
                "client.region": TEST_REGION,
                "glue.region": TEST_REGION,
                "glue.id": TEST_ACCOUNT_ID,
                "glue.endpoint": TEST_GLUE_ENDPOINT,
                "glue.skip-archive": "false",
                "glue.max-retries": 5,
                "glue.retry-mode": "standard",
            },
        )

    @pytest.mark.requirement("CATALOG-GLUE-020")
    def test_connect_rejects_conflicting_runtime_overrides(self) -> None:
        """connect rejects overrides for plugin-owned keys so callers cannot change Glue type."""
        plugin = GlueCatalogPlugin(
            config=GlueCatalogConfig(region=TEST_REGION, credential_mode="environment")
        )

        with pytest.raises(ValueError, match="connect\\(\\) config conflicts"):
            plugin.connect({"type": "rest"})

    @pytest.mark.requirement("CATALOG-GLUE-026")
    def test_connect_accepts_matching_deployment_derived_config(self) -> None:
        """connect accepts resolved deployment config when duplicate keys match plugin config."""
        plugin = GlueCatalogPlugin(
            config=GlueCatalogConfig(
                region=TEST_REGION,
                warehouse=TEST_WAREHOUSE_URI,
                credential_mode="environment",
            )
        )
        catalog = Mock()

        with patch("floe_catalog_glue.plugin.load_catalog", return_value=catalog) as load_catalog:
            assert (
                plugin.connect(
                    {
                        "type": "glue",
                        "glue.region": TEST_REGION,
                        "warehouse": TEST_WAREHOUSE_URI,
                        "s3.region": TEST_REGION,
                    }
                )
                is catalog
            )

        load_catalog.assert_called_once_with(
            "glue",
            type="glue",
            warehouse=TEST_WAREHOUSE_URI,
            **{
                "glue.region": TEST_REGION,
                "glue.skip-archive": "true",
                "s3.region": TEST_REGION,
            },
        )


class TestCatalogOperations:
    """Test required CatalogPlugin operations delegate to PyIceberg."""

    @pytest.fixture()
    def plugin_with_catalog(self) -> GlueCatalogPlugin:
        """Return a GlueCatalogPlugin with a mocked PyIceberg catalog attached."""
        plugin = GlueCatalogPlugin(
            config=GlueCatalogConfig(
                region=TEST_REGION,
                warehouse=TEST_WAREHOUSE_URI,
                credential_mode="environment",
            )
        )
        catalog = Mock()
        catalog.list_namespaces.return_value = [("bronze",), ("silver", "sales")]
        catalog.list_tables.return_value = [("bronze", "customers")]
        plugin._catalog = catalog
        return plugin

    @pytest.mark.requirement("CATALOG-GLUE-021")
    def test_namespace_and_table_methods_delegate_to_catalog(
        self, plugin_with_catalog: GlueCatalogPlugin
    ) -> None:
        """Namespace and table methods delegate to the connected PyIceberg catalog."""
        plugin_with_catalog.create_namespace("bronze", {"owner": "data"})
        assert plugin_with_catalog.list_namespaces() == ["bronze", "silver.sales"]
        assert plugin_with_catalog.list_tables("bronze") == ["bronze.customers"]
        plugin_with_catalog.create_table("bronze.customers", {"type": "struct"})
        plugin_with_catalog.drop_table("bronze.customers_archive")
        plugin_with_catalog.drop_table("bronze.customers", purge=True)
        plugin_with_catalog.delete_namespace("bronze")

        catalog = plugin_with_catalog._catalog
        catalog.create_namespace.assert_called_once_with("bronze", properties={"owner": "data"})
        catalog.list_namespaces.assert_called_once_with()
        catalog.list_tables.assert_called_once_with("bronze")
        catalog.create_table.assert_called_once_with("bronze.customers", {"type": "struct"})
        catalog.drop_table.assert_called_once_with("bronze.customers_archive")
        catalog.purge_table.assert_called_once_with("bronze.customers")
        catalog.drop_namespace.assert_called_once_with("bronze")

    @pytest.mark.requirement("CATALOG-GLUE-022")
    def test_list_namespaces_with_parent_delegates_parent_tuple(
        self, plugin_with_catalog: GlueCatalogPlugin
    ) -> None:
        """Parent namespace listing converts dotted parent names to PyIceberg tuples."""
        assert plugin_with_catalog.list_namespaces(parent="silver.sales") == [
            "bronze",
            "silver.sales",
        ]

        catalog = plugin_with_catalog._catalog
        catalog.list_namespaces.assert_called_once_with(("silver", "sales"))

    @pytest.mark.requirement("CATALOG-GLUE-023")
    def test_catalog_methods_raise_when_not_connected(self) -> None:
        """Catalog operations require connect before delegating to PyIceberg."""
        plugin = GlueCatalogPlugin(
            config=GlueCatalogConfig(region=TEST_REGION, credential_mode="environment")
        )

        with pytest.raises(CatalogUnavailableError, match="call connect"):
            plugin.list_namespaces()

    @pytest.mark.requirement("CATALOG-GLUE-024")
    def test_vend_credentials_not_supported(self) -> None:
        """Glue rejects credential vending because AWS identity supplies credentials."""
        plugin = GlueCatalogPlugin(
            config=GlueCatalogConfig(region=TEST_REGION, credential_mode="environment")
        )

        with pytest.raises(NotSupportedError, match="does not vend credentials"):
            plugin.vend_credentials("bronze.customers", ["READ"])


class TestPackageMetadata:
    """Test package metadata without requiring workspace registration."""

    @pytest.mark.requirement("CATALOG-GLUE-025")
    def test_pyproject_declares_floe_catalog_entry_point(self) -> None:
        """Package metadata declares the glue catalog plugin entry point."""
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        assert pyproject["project"]["name"] == "floe-catalog-glue"
        assert pyproject["project"]["entry-points"]["floe.catalogs"] == {
            "glue": "floe_catalog_glue.plugin:GlueCatalogPlugin"
        }
