"""Unit tests for the native AWS S3 storage plugin."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import tomllib
from pydantic import ValidationError

from floe_storage_aws_s3.config import AwsS3ObjectStoreConfig
from floe_storage_aws_s3.plugin import AwsS3ObjectStorePlugin


class TestPluginMetadata:
    """Test plugin metadata and config schema."""

    def test_plugin_metadata(self) -> None:
        plugin = AwsS3ObjectStorePlugin()

        assert plugin.name == "aws-s3"
        assert plugin.version.count(".") == 2
        assert plugin.floe_api_version == "1.0"
        assert plugin.description == "AWS S3 object storage plugin for Iceberg data"
        assert plugin.tracer_name == "floe.storage.aws_s3"

    def test_get_config_schema_returns_aws_s3_config(self) -> None:
        assert AwsS3ObjectStorePlugin().get_config_schema() is AwsS3ObjectStoreConfig


class TestAwsS3ObjectStoreConfig:
    """Test AWS S3 config validation."""

    def test_workload_identity_config_requires_service_account(self) -> None:
        with pytest.raises(ValidationError, match="service_account_ref"):
            AwsS3ObjectStoreConfig(
                bucket="floe-provider-tests",
                region="ap-southeast-2",
                credential_mode="workload-identity",
            )

    def test_kubernetes_secret_config_requires_secret_name(self) -> None:
        with pytest.raises(ValidationError, match="credential_secret_name"):
            AwsS3ObjectStoreConfig(
                bucket="floe-provider-tests",
                region="ap-southeast-2",
                credential_mode="kubernetes-secret",
            )

    def test_environment_config_rejects_secret_fields(self) -> None:
        with pytest.raises(ValidationError, match="only accepts environment variable names"):
            AwsS3ObjectStoreConfig(
                bucket="floe-provider-tests",
                region="ap-southeast-2",
                credential_mode="environment",
                credential_secret_name="aws-creds",  # pragma: allowlist secret
            )

    def test_endpoint_override_must_be_http_url(self) -> None:
        with pytest.raises(ValidationError, match="endpoint_override"):
            AwsS3ObjectStoreConfig(
                bucket="floe-provider-tests",
                region="ap-southeast-2",
                endpoint_override="s3.ap-southeast-2.amazonaws.com",
            )

    def test_config_defaults_are_native_aws(self) -> None:
        config = AwsS3ObjectStoreConfig(
            bucket="floe-provider-tests",
            region="ap-southeast-2",
            credential_mode="workload-identity",
            service_account_ref="floe-provider-tests",
        )

        assert config.warehouse_prefix == "warehouse/"
        assert config.artifact_bucket == "floe-provider-tests"
        assert config.artifact_prefix == "artifacts/"
        assert config.path_style_access is False
        assert config.sts_supported is True
        assert config.create_policy == "must-exist"


class TestAwsS3DeploymentBinding:
    """Test secret-free AWS S3 deployment bindings."""

    def test_workload_identity_binding_emits_native_s3_contract(self) -> None:
        config = AwsS3ObjectStoreConfig(
            bucket="floe-provider-tests",
            region="ap-southeast-2",
            credential_mode="workload-identity",
            service_account_ref="floe-provider-tests",
        )
        plugin = AwsS3ObjectStorePlugin(config=config)

        binding = plugin.get_deployment_binding()
        payload = binding.model_dump_json()

        assert binding.provider == "aws-s3"
        assert binding.protocol == "s3"
        assert binding.endpoint.internal_url == "https://s3.ap-southeast-2.amazonaws.com"
        assert binding.endpoint.external_url == "https://s3.ap-southeast-2.amazonaws.com"
        assert binding.endpoint.region == "ap-southeast-2"
        assert binding.endpoint.warehouse_path == "s3://floe-provider-tests/warehouse/"
        assert binding.endpoint.path_style_access is False
        assert binding.warehouse is not None
        assert binding.warehouse.uri == "s3://floe-provider-tests/warehouse/"
        assert binding.warehouse.bucket == "floe-provider-tests"
        assert binding.warehouse.prefix == "warehouse/"
        assert binding.allowed_locations == [
            "s3://floe-provider-tests/warehouse/",
            "s3://floe-provider-tests/artifacts/",
        ]
        bucket_contracts = [
            (bucket.name, bucket.purpose, bucket.create_policy) for bucket in binding.buckets
        ]
        assert bucket_contracts == [
            ("floe-provider-tests", "warehouse", "must-exist"),
            ("floe-provider-tests", "artifacts", "must-exist"),
        ]
        assert binding.credentials.mode == "workload-identity"
        assert binding.credentials.service_account_ref == "floe-provider-tests"
        assert binding.capabilities.protocols == ["s3"]
        assert binding.capabilities.credential_modes == ["workload-identity"]
        assert binding.capabilities.identity_modes == ["aws-irsa", "aws-pod-identity"]
        assert binding.capabilities.sts_supported is True
        assert binding.capabilities.path_style_access is False
        assert binding.provisioning.enabled is False
        assert binding.provisioning.mode == "external"
        assert binding.provisioning.default_create_policy == "must-exist"
        assert binding.runtime.pyiceberg_properties == {"s3.region": "ap-southeast-2"}
        assert binding.runtime.env_refs == {}
        assert binding.dbt.profile_fragment == {
            "s3_region": "ap-southeast-2",
            "s3_path_style_access": False,
        }
        assert binding.dagster.resources == {
            "bucket": "floe-provider-tests",
            "region_name": "ap-southeast-2",
            "path_style_access": False,
        }
        assert "AWS_SECRET_ACCESS_KEY" not in payload
        assert "raw-secret-value" not in payload

    def test_environment_binding_uses_env_refs_without_values(self) -> None:
        config = AwsS3ObjectStoreConfig(
            bucket="floe-provider-tests",
            region="ap-southeast-2",
            credential_mode="environment",
        )
        binding = AwsS3ObjectStorePlugin(config=config).get_deployment_binding()

        assert binding.credentials.mode == "environment"
        assert binding.credentials.env_refs == {
            "accessKeyId": "AWS_ACCESS_KEY_ID",
            "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
            "sessionToken": "AWS_SESSION_TOKEN",
        }
        assert binding.runtime.env_refs == binding.credentials.env_refs
        assert binding.dbt.env_refs == {
            "s3_access_key_id": "AWS_ACCESS_KEY_ID",
            "s3_secret_access_key": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
            "s3_session_token": "AWS_SESSION_TOKEN",
        }

    def test_kubernetes_secret_binding_uses_secret_refs_without_values(self) -> None:
        config = AwsS3ObjectStoreConfig(
            bucket="floe-provider-tests",
            region="ap-southeast-2",
            credential_mode="kubernetes-secret",
            credential_secret_name="aws-s3-credentials",  # pragma: allowlist secret
            credential_secret_namespace="floe-system",  # pragma: allowlist secret
        )
        binding = AwsS3ObjectStorePlugin(config=config).get_deployment_binding()

        assert binding.credentials.mode == "kubernetes-secret"
        assert binding.credentials.secret_ref is not None
        assert binding.credentials.secret_ref.name == "aws-s3-credentials"
        assert binding.credentials.secret_ref.namespace == "floe-system"
        assert binding.credentials.secret_ref.keys == {
            "accessKeyId": "accessKeyId",
            "secretAccessKey": "secretAccessKey",  # pragma: allowlist secret
            "sessionToken": "sessionToken",
        }

    def test_endpoint_override_projects_localstack_properties(self) -> None:
        config = AwsS3ObjectStoreConfig(
            bucket="floe-provider-tests",
            region="ap-southeast-2",
            endpoint_override="http://localhost:4566",
            path_style_access=True,
            credential_mode="environment",
        )
        binding = AwsS3ObjectStorePlugin(config=config).get_deployment_binding()

        assert binding.endpoint.internal_url == "http://localhost:4566"
        assert binding.endpoint.external_url == "http://localhost:4566"
        assert binding.endpoint.path_style_access is True
        assert binding.runtime.pyiceberg_properties == {
            "s3.endpoint": "http://localhost:4566",
            "s3.region": "ap-southeast-2",
            "s3.path-style-access": "true",
        }


class TestStoragePluginMethods:
    """Test required StoragePlugin methods."""

    @pytest.fixture()
    def configured_plugin(self) -> AwsS3ObjectStorePlugin:
        config = AwsS3ObjectStoreConfig(
            bucket="floe-provider-tests",
            region="ap-southeast-2",
            credential_mode="workload-identity",
            service_account_ref="floe-provider-tests",
        )
        return AwsS3ObjectStorePlugin(config=config)

    def test_get_warehouse_uri(self, configured_plugin: AwsS3ObjectStorePlugin) -> None:
        assert configured_plugin.get_warehouse_uri("bronze") == (
            "s3://floe-provider-tests/warehouse/bronze/"
        )

    def test_get_dbt_profile_config(self, configured_plugin: AwsS3ObjectStorePlugin) -> None:
        assert configured_plugin.get_dbt_profile_config() == {
            "s3_region": "ap-southeast-2",
            "s3_path_style_access": False,
        }

    def test_get_dagster_io_manager_config(self, configured_plugin: AwsS3ObjectStorePlugin) -> None:
        assert configured_plugin.get_dagster_io_manager_config() == {
            "bucket": "floe-provider-tests",
            "region_name": "ap-southeast-2",
            "path_style_access": False,
        }

    def test_get_pyiceberg_catalog_config_has_no_credentials(
        self, configured_plugin: AwsS3ObjectStorePlugin
    ) -> None:
        assert configured_plugin.get_pyiceberg_catalog_config() == {"s3.region": "ap-southeast-2"}

    def test_get_pyiceberg_fileio(self, configured_plugin: AwsS3ObjectStorePlugin) -> None:
        from pyiceberg.io.fsspec import FsspecFileIO

        with patch.dict("os.environ", {}, clear=False):
            fileio = configured_plugin.get_pyiceberg_fileio()

        assert isinstance(fileio, FsspecFileIO)

    def test_get_helm_values_override_is_empty(
        self,
        configured_plugin: AwsS3ObjectStorePlugin,
    ) -> None:
        assert configured_plugin.get_helm_values_override() == {}

    def test_methods_raise_without_config(self) -> None:
        from floe_core.plugin_errors import PluginConfigurationError

        plugin = AwsS3ObjectStorePlugin()

        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_deployment_binding()
        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_warehouse_uri("bronze")
        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_pyiceberg_catalog_config()


class TestPackageMetadata:
    """Test package metadata without requiring workspace registration."""

    def test_pyproject_declares_floe_storage_entry_point(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        assert pyproject["project"]["name"] == "floe-storage-aws-s3"
        assert pyproject["project"]["entry-points"]["floe.storage"] == {
            "aws-s3": "floe_storage_aws_s3.plugin:AwsS3ObjectStorePlugin"
        }
