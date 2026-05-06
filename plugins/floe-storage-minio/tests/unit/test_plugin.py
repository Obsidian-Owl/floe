"""Unit tests for MinIOStoragePlugin.

Tests AC-1 (plugin structure and discoverability) and AC-2 (config validation).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from floe_storage_minio.config import MinIOStorageConfig
from floe_storage_minio.plugin import MinIOStoragePlugin

# ---------------------------------------------------------------------------
# AC-1: MinIOStoragePlugin exists and implements StoragePlugin ABC
# ---------------------------------------------------------------------------


class TestPluginMetadata:
    """Test PluginMetadata abstract properties."""

    @pytest.mark.requirement("AC-1")
    def test_plugin_name(self) -> None:
        """Plugin name must be 'minio'."""
        plugin = MinIOStoragePlugin()
        assert plugin.name == "minio"

    @pytest.mark.requirement("AC-1")
    def test_plugin_version(self) -> None:
        """Plugin must report a semver version."""
        plugin = MinIOStoragePlugin()
        parts = plugin.version.split(".")
        assert len(parts) == 3

    @pytest.mark.requirement("AC-1")
    def test_plugin_floe_api_version(self) -> None:
        """Plugin must report floe API version."""
        plugin = MinIOStoragePlugin()
        assert plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("AC-1")
    def test_plugin_description(self) -> None:
        """Plugin must have a description."""
        plugin = MinIOStoragePlugin()
        assert len(plugin.description) > 0

    @pytest.mark.requirement("AC-5")
    def test_tracer_name_is_dot_separated(self) -> None:
        """tracer_name must return 'floe.storage.minio' (dot-separated convention)."""
        plugin = MinIOStoragePlugin()
        assert plugin.tracer_name == "floe.storage.minio"

    @pytest.mark.requirement("AC-5")
    def test_tracer_name_follows_convention(self) -> None:
        """tracer_name must follow floe.<category>.<name> convention."""
        plugin = MinIOStoragePlugin()
        parts = plugin.tracer_name.split(".")
        assert len(parts) == 3, f"Expected 3 dot-separated parts, got {parts}"
        assert parts[0] == "floe", f"Tracer name must start with 'floe', got '{parts[0]}'"

    @pytest.mark.requirement("AC-1")
    def test_get_config_schema_returns_minio_config(self) -> None:
        """get_config_schema must return MinIOStorageConfig class."""
        plugin = MinIOStoragePlugin()
        schema = plugin.get_config_schema()
        assert schema is MinIOStorageConfig

    @pytest.mark.requirement("AC-1")
    def test_plugin_instantiates_without_config(self) -> None:
        """Plugin must accept config=None for loader discovery."""
        plugin = MinIOStoragePlugin()
        assert plugin._config is None

    @pytest.mark.requirement("AC-1")
    def test_plugin_instantiates_with_config(self) -> None:
        """Plugin must accept a real config."""
        config = MinIOStorageConfig(endpoint="http://minio:9000", bucket="test")
        plugin = MinIOStoragePlugin(config=config)
        assert plugin._config is config


# ---------------------------------------------------------------------------
# AC-2: MinIOStorageConfig Pydantic model
# ---------------------------------------------------------------------------


class TestMinIOStorageConfig:
    """Test MinIOStorageConfig validation."""

    @pytest.mark.requirement("AC-2")
    def test_valid_minimal_config(self) -> None:
        """Config with only required fields must validate."""
        config = MinIOStorageConfig(endpoint="http://minio:9000", bucket="data")
        assert config.endpoint == "http://minio:9000"
        assert config.bucket == "data"
        assert config.region == "us-east-1"
        assert config.path_style_access is True
        assert config.access_key_id is None
        assert config.secret_access_key is None

    @pytest.mark.requirement("AC-2")
    def test_valid_full_config(self) -> None:
        """Config with all fields must validate."""
        config = MinIOStorageConfig(
            endpoint="http://minio:9000",
            bucket="floe-data",
            region="eu-west-1",
            path_style_access=False,
            artifact_bucket="floe-artifacts",
            credential_secret_name="custom-minio-credentials",  # pragma: allowlist secret
            credential_secret_namespace="floe-system",  # pragma: allowlist secret
            access_key_secret_key="root-user",  # pragma: allowlist secret
            secret_key_secret_key="root-password",  # pragma: allowlist secret
            external_endpoint="http://localhost:9000",
            access_key_id=SecretStr("AKID"),  # pragma: allowlist secret
            secret_access_key=SecretStr("SECRET"),  # pragma: allowlist secret
        )
        expected_credential_name = "custom-minio-credentials"  # pragma: allowlist secret

        assert config.region == "eu-west-1"
        assert config.path_style_access is False
        assert config.artifact_bucket == "floe-artifacts"
        assert config.credential_secret_name == expected_credential_name
        assert config.credential_secret_namespace == "floe-system"  # pragma: allowlist secret
        assert config.access_key_secret_key == "root-user"  # pragma: allowlist secret
        assert config.secret_key_secret_key == "root-password"  # pragma: allowlist secret
        assert config.external_endpoint == "http://localhost:9000"
        assert config.access_key_id is not None
        assert config.access_key_id.get_secret_value() == "AKID"

    @pytest.mark.requirement("AC-2")
    def test_demo_manifest_config(self) -> None:
        """Config matching demo/manifest.yaml must validate."""
        config = MinIOStorageConfig(
            endpoint="http://floe-platform-minio:9000",
            bucket="floe-data",
            region="us-east-1",
            path_style_access=True,
        )
        assert config.endpoint == "http://floe-platform-minio:9000"
        assert config.bucket == "floe-data"

    @pytest.mark.requirement("AC-2")
    def test_missing_endpoint_rejected(self) -> None:
        """Missing endpoint must raise ValidationError."""
        with pytest.raises(ValidationError, match="endpoint"):
            MinIOStorageConfig(bucket="data")  # type: ignore[call-arg]

    @pytest.mark.requirement("AC-2")
    def test_missing_bucket_rejected(self) -> None:
        """Missing bucket must raise ValidationError."""
        with pytest.raises(ValidationError, match="bucket"):
            MinIOStorageConfig(endpoint="http://minio:9000")  # type: ignore[call-arg]

    @pytest.mark.requirement("AC-2")
    def test_empty_endpoint_rejected(self) -> None:
        """Empty endpoint must raise ValidationError."""
        with pytest.raises(ValidationError):
            MinIOStorageConfig(endpoint="", bucket="data")

    @pytest.mark.requirement("AC-2")
    def test_empty_bucket_rejected(self) -> None:
        """Empty bucket must raise ValidationError."""
        with pytest.raises(ValidationError):
            MinIOStorageConfig(endpoint="http://minio:9000", bucket="")

    @pytest.mark.requirement("AC-2")
    def test_extra_fields_rejected(self) -> None:
        """Unknown fields must raise ValidationError (extra=forbid)."""
        with pytest.raises(ValidationError):
            MinIOStorageConfig(
                endpoint="http://minio:9000",
                bucket="data",
                unknown_field="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("AC-2")
    def test_config_is_frozen(self) -> None:
        """Config must be immutable (frozen=True)."""
        config = MinIOStorageConfig(endpoint="http://minio:9000", bucket="data")
        with pytest.raises(ValidationError):
            config.endpoint = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StoragePlugin method tests (require config)
# ---------------------------------------------------------------------------


class TestStoragePluginMethods:
    """Test StoragePlugin ABC method implementations."""

    @pytest.fixture()
    def configured_plugin(self) -> MinIOStoragePlugin:
        """Return a plugin with valid config."""
        config = MinIOStorageConfig(
            endpoint="http://minio:9000",
            bucket="floe-data",
            region="us-east-1",
            path_style_access=True,
        )
        return MinIOStoragePlugin(config=config)

    @pytest.mark.requirement("AC-1")
    def test_get_warehouse_uri(self, configured_plugin: MinIOStoragePlugin) -> None:
        """get_warehouse_uri must return s3://bucket/namespace/ URI."""
        uri = configured_plugin.get_warehouse_uri("bronze")
        assert uri == "s3://floe-data/bronze/"

    @pytest.mark.requirement("AC-1")
    def test_get_warehouse_uri_different_namespace(
        self, configured_plugin: MinIOStoragePlugin
    ) -> None:
        """get_warehouse_uri must work for any namespace."""
        assert configured_plugin.get_warehouse_uri("silver") == "s3://floe-data/silver/"

    @pytest.mark.requirement("AC-1")
    def test_get_dbt_profile_config(self, configured_plugin: MinIOStoragePlugin) -> None:
        """get_dbt_profile_config must return S3-compatible dbt config."""
        config = configured_plugin.get_dbt_profile_config()
        assert config["s3_region"] == "us-east-1"
        assert config["s3_endpoint"] == "http://minio:9000"
        assert config["s3_path_style_access"] is True

    @pytest.mark.requirement("AC-1")
    def test_get_dagster_io_manager_config(self, configured_plugin: MinIOStoragePlugin) -> None:
        """get_dagster_io_manager_config must return S3-compatible IOManager config."""
        config = configured_plugin.get_dagster_io_manager_config()
        assert config["bucket"] == "floe-data"
        assert config["endpoint_url"] == "http://minio:9000"
        assert config["region_name"] == "us-east-1"

    @pytest.mark.requirement("AC-1")
    def test_get_helm_values_override_uses_secret_refs(
        self, configured_plugin: MinIOStoragePlugin
    ) -> None:
        """get_helm_values_override must configure MinIO without secret values."""
        values = configured_plugin.get_helm_values_override()
        payload = str(values)

        assert values["minio"]["enabled"] is True
        assert values["minio"]["auth"] == {
            "existingSecret": "floe-platform-minio-credentials"  # pragma: allowlist secret
        }
        assert values["minio"]["defaultBuckets"] == "floe-data,floe-artifacts"
        assert values["polaris"]["storage"]["s3"]["credentialSecretName"] == (
            "floe-platform-minio-credentials"
        )
        assert values["polaris"]["bootstrap"]["defaultBaseLocation"] == "s3://floe-data"
        assert "minio" + "admin" not in payload
        assert "SECRET" not in payload

    @pytest.mark.requirement("AC-1")
    def test_get_pyiceberg_fileio(self, configured_plugin: MinIOStoragePlugin) -> None:
        """get_pyiceberg_fileio must return a FsspecFileIO instance."""
        from pyiceberg.io.fsspec import FsspecFileIO

        with patch.dict(
            "os.environ", {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"}
        ):
            fileio = configured_plugin.get_pyiceberg_fileio()
        assert isinstance(fileio, FsspecFileIO)

    @pytest.mark.requirement("AC-1")
    def test_get_pyiceberg_catalog_config_uses_pyiceberg_s3_keys(
        self, configured_plugin: MinIOStoragePlugin
    ) -> None:
        """Catalog config must use PyIceberg S3 keys, not raw manifest keys."""
        with patch.dict(
            "os.environ", {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "secret"}
        ):
            config = configured_plugin.get_pyiceberg_catalog_config()

        assert config == {
            "s3.endpoint": "http://minio:9000",
            "s3.region": "us-east-1",
            "s3.path-style-access": "true",
            "s3.access-key-id": "test",
            "s3.secret-access-key": "secret",
        }
        assert "s3.path_style_access" not in config
        assert "path_style_access" not in config


class TestUnconfiguredPlugin:
    """Test that unconfigured plugin raises clear errors."""

    @pytest.mark.requirement("AC-1")
    def test_methods_raise_without_config(self) -> None:
        """All StoragePlugin methods must raise PluginConfigurationError when unconfigured."""
        from floe_core.plugin_errors import PluginConfigurationError

        plugin = MinIOStoragePlugin()
        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_warehouse_uri("test")
        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_dbt_profile_config()
        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_dagster_io_manager_config()
        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_pyiceberg_fileio()
        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_pyiceberg_catalog_config()
        with pytest.raises(PluginConfigurationError, match="not configured"):
            plugin.get_deployment_binding()


class TestMinIODeploymentBinding:
    """Tests for secret-free MinIO deployment bindings."""

    def test_get_deployment_binding_returns_secret_free_minio_contract(self) -> None:
        """MinIO plugin must emit neutral storage state without catalog projections."""
        config = MinIOStorageConfig(
            endpoint="http://minio:9000",
            bucket="floe-data",
            region="us-east-1",
            path_style_access=True,
            external_endpoint="http://localhost:9000",
            access_key_id=SecretStr("INLINE_ACCESS_VALUE"),  # pragma: allowlist secret
            secret_access_key=SecretStr("INLINE_CREDENTIAL_VALUE"),  # pragma: allowlist secret
        )
        plugin = MinIOStoragePlugin(config=config)

        binding = plugin.get_deployment_binding()
        payload = binding.model_dump_json()
        helm_payload = str(plugin.get_helm_values_override())

        assert binding.provider == "minio"
        assert binding.protocol == "s3-compatible"
        assert binding.endpoint.internal_url == "http://minio:9000"
        assert binding.endpoint.external_url == "http://localhost:9000"
        assert binding.endpoint.region == "us-east-1"
        assert binding.endpoint.warehouse_path == "s3://floe-data"
        assert binding.endpoint.path_style_access is True
        assert binding.warehouse is not None
        assert binding.warehouse.uri == "s3://floe-data"
        assert binding.warehouse.bucket == "floe-data"
        assert binding.allowed_locations == ["s3://floe-data", "s3://floe-artifacts"]
        assert [bucket.purpose for bucket in binding.buckets] == ["warehouse", "artifacts"]
        assert binding.buckets[0].name == "floe-data"
        assert binding.buckets[0].purpose == "warehouse"
        assert binding.buckets[0].create_policy == "create-if-missing"
        assert binding.capabilities.protocols == ["s3-compatible"]
        assert binding.capabilities.credential_modes == ["kubernetes-secret"]
        assert binding.capabilities.sts_supported is False
        assert binding.capabilities.path_style_access is True
        assert binding.provisioning.enabled is True
        assert binding.provisioning.mode == "helm-job"
        assert binding.provisioning.default_create_policy == "create-if-missing"
        assert binding.runtime.pyiceberg_properties == {
            "s3.endpoint": "http://minio:9000",
            "s3.region": "us-east-1",
            "s3.path-style-access": "true",
        }
        assert binding.runtime.env_refs == {
            "accessKeyId": "AWS_ACCESS_KEY_ID",
            "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
        }
        assert not hasattr(binding, "polaris")
        assert binding.credentials.mode == "kubernetes-secret"
        assert binding.credentials.secret_ref is not None
        assert binding.credentials.secret_ref.name == "floe-platform-minio-credentials"
        assert binding.credentials.secret_ref.namespace == "floe-system"
        assert binding.credentials.secret_ref.keys == {
            "accessKeyId": "root-user",
            "secretAccessKey": "root-password",  # pragma: allowlist secret
        }
        assert binding.dbt.profile_name == "floe"
        assert binding.dbt.target_name == "dev"
        assert binding.dbt.schema_name == "analytics"
        assert binding.dbt.env_refs == {
            "s3_access_key_id": "AWS_ACCESS_KEY_ID",
            "s3_secret_access_key": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
        }
        assert binding.dagster.resource_key == "minio_storage"
        assert binding.dagster.asset_io_manager_key == "iceberg_io_manager"
        assert binding.dagster.env_refs == {
            "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
        }
        assert "minio" + "admin" not in payload
        assert "secretKey" not in payload
        assert "INLINE_ACCESS_VALUE" not in payload
        assert "INLINE_ACCESS_VALUE" not in helm_payload
        assert "INLINE_CREDENTIAL_VALUE" not in payload
        assert "INLINE_CREDENTIAL_VALUE" not in helm_payload

    def test_minio_binding_uses_configured_artifact_bucket_in_helm_values(self) -> None:
        """Deprecated Helm projection must include configured storage buckets."""
        config = MinIOStorageConfig(
            endpoint="http://floe-platform-minio:9000",
            bucket="warehouse",
            artifact_bucket="artifacts",
        )
        plugin = MinIOStoragePlugin(config=config)

        assert plugin.get_helm_values_override()["minio"]["defaultBuckets"] == (
            "warehouse,artifacts"
        )
        assert plugin.get_deployment_binding().endpoint.warehouse_path == "s3://warehouse"
