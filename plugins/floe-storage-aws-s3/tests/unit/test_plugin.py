"""Unit tests for the native AWS S3 storage plugin."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from floe_storage_aws_s3.config import AwsS3ObjectStoreConfig, _normalize_prefix
from floe_storage_aws_s3.plugin import AwsS3ObjectStorePlugin

TEST_BUCKET = "floe-provider-tests"
TEST_REGION = "ap-southeast-2"
TEST_SERVICE_ACCOUNT = "floe-provider-tests"
TEST_WAREHOUSE_URI = f"s3://{TEST_BUCKET}/warehouse/"
TEST_ARTIFACT_URI = f"s3://{TEST_BUCKET}/artifacts/"
TEST_AWS_ENDPOINT = f"https://s3.{TEST_REGION}.amazonaws.com"


class TestPluginMetadata:
    """Test plugin metadata and config schema."""

    @pytest.mark.requirement("STORAGE-AWS-S3-001")
    def test_plugin_metadata(self) -> None:
        """Plugin metadata exposes the stable aws-s3 identity and tracer name."""
        plugin = AwsS3ObjectStorePlugin()

        assert plugin.name == "aws-s3"
        assert plugin.version.count(".") == 2
        assert plugin.floe_api_version == "1.0"
        assert plugin.description == "AWS S3 object storage plugin for Iceberg data"
        assert plugin.tracer_name == "floe.storage.aws_s3"

    @pytest.mark.requirement("STORAGE-AWS-S3-002")
    def test_get_config_schema_returns_aws_s3_config(self) -> None:
        """Plugin config schema points consumers at the AWS S3 config model."""
        assert AwsS3ObjectStorePlugin().get_config_schema() is AwsS3ObjectStoreConfig


class TestAwsS3ObjectStoreConfig:
    """Test AWS S3 config validation."""

    @pytest.mark.requirement("STORAGE-AWS-S3-003")
    def test_workload_identity_config_requires_service_account(self) -> None:
        """Workload-identity mode rejects config without a service account ref."""
        with pytest.raises(ValidationError, match="service_account_ref"):
            AwsS3ObjectStoreConfig(
                bucket=TEST_BUCKET,
                region=TEST_REGION,
                credential_mode="workload-identity",
            )

    @pytest.mark.requirement("STORAGE-AWS-S3-004")
    def test_kubernetes_secret_config_requires_secret_name(self) -> None:
        """Kubernetes-secret mode rejects config without a Secret reference."""
        with pytest.raises(ValidationError, match="credential_secret_name"):
            AwsS3ObjectStoreConfig(
                bucket=TEST_BUCKET,
                region=TEST_REGION,
                credential_mode="kubernetes-secret",
            )

    @pytest.mark.requirement("STORAGE-AWS-S3-005")
    def test_environment_config_rejects_secret_fields(self) -> None:
        """Environment mode rejects Kubernetes Secret fields to keep sources exclusive."""
        with pytest.raises(ValidationError, match="only accepts environment variable names"):
            AwsS3ObjectStoreConfig(
                bucket=TEST_BUCKET,
                region=TEST_REGION,
                credential_mode="environment",
                credential_secret_name="aws-creds",  # pragma: allowlist secret
            )

    @pytest.mark.requirement("STORAGE-AWS-S3-020")
    def test_workload_identity_config_rejects_secret_name(self) -> None:
        """Workload-identity mode rejects Kubernetes Secret fields from other modes."""
        with pytest.raises(ValidationError, match="only accepts service_account_ref"):
            AwsS3ObjectStoreConfig(
                bucket=TEST_BUCKET,
                region=TEST_REGION,
                credential_mode="workload-identity",
                service_account_ref=TEST_SERVICE_ACCOUNT,
                credential_secret_name="aws-creds",  # pragma: allowlist secret
            )

    @pytest.mark.requirement("STORAGE-AWS-S3-021")
    def test_kubernetes_secret_config_rejects_service_account(self) -> None:
        """Kubernetes-secret mode rejects workload identity service account refs."""
        with pytest.raises(ValidationError, match="only accepts credential_secret_name"):
            AwsS3ObjectStoreConfig(
                bucket=TEST_BUCKET,
                region=TEST_REGION,
                credential_mode="kubernetes-secret",
                credential_secret_name="aws-creds",  # pragma: allowlist secret
                service_account_ref=TEST_SERVICE_ACCOUNT,
            )

    @pytest.mark.requirement("STORAGE-AWS-S3-022")
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("warehouse", "warehouse/"),
            ("/warehouse/", "warehouse/"),
            ("", ""),
            ("/", ""),
            ("//", ""),
            ("a/b/c", "a/b/c/"),
        ],
    )
    def test_normalize_prefix_edge_cases(self, raw: str, expected: str) -> None:
        """Prefix normalization handles slash-stripping edge cases deterministically."""
        assert _normalize_prefix(raw) == expected

    @pytest.mark.requirement("STORAGE-AWS-S3-006")
    def test_endpoint_override_must_be_http_url(self) -> None:
        """Endpoint overrides must be explicit HTTP URLs for runtime clients."""
        with pytest.raises(ValidationError, match="endpoint_override"):
            AwsS3ObjectStoreConfig(
                bucket=TEST_BUCKET,
                region=TEST_REGION,
                endpoint_override="s3.ap-southeast-2.amazonaws.com",
            )

    @pytest.mark.requirement("STORAGE-AWS-S3-007")
    def test_config_defaults_are_native_aws(self) -> None:
        """Default config favors native AWS S3 behavior and externally managed buckets."""
        config = AwsS3ObjectStoreConfig(
            bucket=TEST_BUCKET,
            region=TEST_REGION,
            credential_mode="workload-identity",
            service_account_ref=TEST_SERVICE_ACCOUNT,
        )

        assert config.warehouse_prefix == "warehouse/"
        assert config.artifact_bucket == TEST_BUCKET
        assert config.artifact_prefix == "artifacts/"
        assert config.path_style_access is False
        assert config.sts_supported is True
        assert config.create_policy == "must-exist"

    @pytest.mark.requirement("STORAGE-AWS-S3-024")
    def test_artifact_bucket_rejects_empty_string(self) -> None:
        """Artifact bucket overrides must be non-empty when explicitly provided."""
        with pytest.raises(ValidationError, match="artifact_bucket"):
            AwsS3ObjectStoreConfig(
                bucket=TEST_BUCKET,
                artifact_bucket="",
                region=TEST_REGION,
                credential_mode="environment",
            )


class TestAwsS3DeploymentBinding:
    """Test secret-free AWS S3 deployment bindings."""

    @pytest.mark.requirement("STORAGE-AWS-S3-008")
    def test_workload_identity_binding_emits_native_s3_contract(self) -> None:
        """Workload identity emits native s3 bindings without credential values."""
        config = AwsS3ObjectStoreConfig(
            bucket=TEST_BUCKET,
            region=TEST_REGION,
            credential_mode="workload-identity",
            service_account_ref=TEST_SERVICE_ACCOUNT,
        )
        plugin = AwsS3ObjectStorePlugin(config=config)

        binding = plugin.get_deployment_binding()
        payload = binding.model_dump_json()

        assert binding.provider == "aws-s3"
        assert binding.protocol == "s3"
        assert binding.endpoint.internal_url == TEST_AWS_ENDPOINT
        assert binding.endpoint.external_url == TEST_AWS_ENDPOINT
        assert binding.endpoint.region == TEST_REGION
        assert binding.endpoint.warehouse_path == TEST_WAREHOUSE_URI
        assert binding.endpoint.path_style_access is False
        assert binding.warehouse.uri == TEST_WAREHOUSE_URI
        assert binding.warehouse.bucket == TEST_BUCKET
        assert binding.warehouse.prefix == "warehouse/"
        assert binding.allowed_locations == [
            TEST_WAREHOUSE_URI,
            TEST_ARTIFACT_URI,
        ]
        bucket_contracts = [
            (bucket.name, bucket.purpose, bucket.create_policy) for bucket in binding.buckets
        ]
        assert bucket_contracts == [
            (TEST_BUCKET, "warehouse", "must-exist"),
            (TEST_BUCKET, "artifacts", "must-exist"),
        ]
        assert binding.credentials.mode == "workload-identity"
        assert binding.credentials.service_account_ref == TEST_SERVICE_ACCOUNT
        assert binding.capabilities.protocols == ["s3"]
        assert binding.capabilities.credential_modes == ["workload-identity"]
        assert binding.capabilities.identity_modes == ["aws-irsa", "aws-pod-identity"]
        assert binding.capabilities.sts_supported is True
        assert binding.capabilities.path_style_access is False
        assert binding.provisioning.enabled is False
        assert binding.provisioning.mode == "external"
        assert binding.provisioning.default_create_policy == "must-exist"
        assert binding.runtime.pyiceberg_properties == {"s3.region": TEST_REGION}
        assert binding.runtime.env_refs == {}
        assert binding.dbt.profile_fragment == {
            "s3_region": TEST_REGION,
            "s3_path_style_access": False,
        }
        assert binding.dagster.resources == {
            "bucket": TEST_BUCKET,
            "region_name": TEST_REGION,
            "path_style_access": False,
        }
        assert "AWS_SECRET_ACCESS_KEY" not in payload
        assert "raw-secret-value" not in payload

    @pytest.mark.requirement("STORAGE-AWS-S3-009")
    def test_environment_binding_uses_env_refs_without_values(self) -> None:
        """Environment mode projects environment variable names instead of values."""
        config = AwsS3ObjectStoreConfig(
            bucket=TEST_BUCKET,
            region=TEST_REGION,
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
        }

    @pytest.mark.requirement("STORAGE-AWS-S3-023")
    def test_environment_dbt_binding_does_not_require_session_token(self) -> None:
        """dbt profile env refs omit optional AWS_SESSION_TOKEN for non-STS credentials."""
        config = AwsS3ObjectStoreConfig(
            bucket=TEST_BUCKET,
            region=TEST_REGION,
            credential_mode="environment",
        )
        binding = AwsS3ObjectStorePlugin(config=config).get_deployment_binding()

        assert "s3_session_token" not in binding.dbt.env_refs
        assert "sessionToken" in binding.credentials.env_refs

    @pytest.mark.requirement("STORAGE-AWS-S3-010")
    def test_kubernetes_secret_binding_uses_secret_refs_without_values(self) -> None:
        """Kubernetes-secret mode projects Secret key references without values."""
        config = AwsS3ObjectStoreConfig(
            bucket=TEST_BUCKET,
            region=TEST_REGION,
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
        assert binding.runtime.env_refs == {
            "accessKeyId": "AWS_ACCESS_KEY_ID",
            "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
        }

    @pytest.mark.requirement("STORAGE-AWS-S3-025")
    def test_kubernetes_secret_runtime_env_refs_project_aws_env_names(self) -> None:
        """Secret-backed mode still exposes runtime AWS env names for job wiring."""
        config = AwsS3ObjectStoreConfig(
            bucket=TEST_BUCKET,
            region=TEST_REGION,
            credential_mode="kubernetes-secret",
            credential_secret_name="aws-s3-credentials",  # pragma: allowlist secret
        )
        binding = AwsS3ObjectStorePlugin(config=config).get_deployment_binding()

        assert binding.runtime.env_refs == {
            "accessKeyId": "AWS_ACCESS_KEY_ID",
            "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
        }

    @pytest.mark.requirement("STORAGE-AWS-S3-011")
    def test_endpoint_override_projects_localstack_properties(self) -> None:
        """Endpoint overrides are projected for local S3-compatible testing."""
        config = AwsS3ObjectStoreConfig(
            bucket=TEST_BUCKET,
            region=TEST_REGION,
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
            "s3.region": TEST_REGION,
            "s3.path-style-access": "true",
        }


class TestStoragePluginMethods:
    """Test required StoragePlugin methods."""

    @pytest.fixture()
    def configured_plugin(self) -> AwsS3ObjectStorePlugin:
        """Return an AWS S3 plugin configured for workload-identity testing."""
        config = AwsS3ObjectStoreConfig(
            bucket=TEST_BUCKET,
            region=TEST_REGION,
            credential_mode="workload-identity",
            service_account_ref=TEST_SERVICE_ACCOUNT,
        )
        return AwsS3ObjectStorePlugin(config=config)

    @pytest.mark.requirement("STORAGE-AWS-S3-012")
    def test_get_warehouse_uri(self, configured_plugin: AwsS3ObjectStorePlugin) -> None:
        """Namespace warehouse URIs are derived below the configured warehouse prefix."""
        assert configured_plugin.get_warehouse_uri("bronze") == f"{TEST_WAREHOUSE_URI}bronze/"

    @pytest.mark.requirement("STORAGE-AWS-S3-013")
    def test_get_dbt_profile_config(self, configured_plugin: AwsS3ObjectStorePlugin) -> None:
        """Legacy dbt profile helper returns the binding-derived storage fragment."""
        assert configured_plugin.get_dbt_profile_config() == {
            "s3_region": TEST_REGION,
            "s3_path_style_access": False,
        }

    @pytest.mark.requirement("STORAGE-AWS-S3-014")
    def test_get_dagster_io_manager_config(self, configured_plugin: AwsS3ObjectStorePlugin) -> None:
        """Legacy Dagster helper returns the binding-derived storage fragment."""
        assert configured_plugin.get_dagster_io_manager_config() == {
            "bucket": TEST_BUCKET,
            "region_name": TEST_REGION,
            "path_style_access": False,
        }

    @pytest.mark.requirement("STORAGE-AWS-S3-015")
    def test_get_pyiceberg_catalog_config_has_no_credentials(
        self, configured_plugin: AwsS3ObjectStorePlugin
    ) -> None:
        """PyIceberg catalog config exposes only non-secret S3 properties."""
        assert configured_plugin.get_pyiceberg_catalog_config() == {"s3.region": TEST_REGION}

    @pytest.mark.requirement("STORAGE-AWS-S3-016")
    def test_get_pyiceberg_fileio(self, configured_plugin: AwsS3ObjectStorePlugin) -> None:
        """FileIO construction delegates to PyIceberg without needing inline credentials."""
        from pyiceberg.io.fsspec import FsspecFileIO

        with patch.dict("os.environ", {}, clear=False):
            fileio = configured_plugin.get_pyiceberg_fileio()

        assert isinstance(fileio, FsspecFileIO)

    @pytest.mark.requirement("STORAGE-AWS-S3-017")
    def test_get_helm_values_override_is_empty(
        self,
        configured_plugin: AwsS3ObjectStorePlugin,
    ) -> None:
        """AWS S3 has no Helm-managed service values because buckets are external."""
        assert configured_plugin.get_helm_values_override() == {}

    @pytest.mark.requirement("STORAGE-AWS-S3-018")
    def test_methods_raise_without_config(self) -> None:
        """Unconfigured plugin methods raise structured configuration errors."""
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

    @pytest.mark.requirement("STORAGE-AWS-S3-019")
    def test_pyproject_declares_floe_storage_entry_point(self) -> None:
        """Package metadata declares the aws-s3 storage plugin entry point."""
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        assert pyproject["project"]["name"] == "floe-storage-aws-s3"
        assert pyproject["project"]["entry-points"]["floe.storage"] == {
            "aws-s3": "floe_storage_aws_s3.plugin:AwsS3ObjectStorePlugin"
        }
