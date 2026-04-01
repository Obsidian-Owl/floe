"""Unit tests for S3StoragePlugin.

Tests AC-1 (plugin structure and discoverability) and AC-2 (config validation).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from floe_storage_s3.config import S3StorageConfig
from floe_storage_s3.plugin import S3StoragePlugin

# ---------------------------------------------------------------------------
# AC-1: S3StoragePlugin exists and implements StoragePlugin ABC
# ---------------------------------------------------------------------------


class TestPluginMetadata:
    """Test PluginMetadata abstract properties."""

    @pytest.mark.requirement("AC-1")
    def test_plugin_name(self) -> None:
        """Plugin name must be 's3'."""
        plugin = S3StoragePlugin()
        assert plugin.name == "s3"

    @pytest.mark.requirement("AC-1")
    def test_plugin_version(self) -> None:
        """Plugin must report a semver version."""
        plugin = S3StoragePlugin()
        parts = plugin.version.split(".")
        assert len(parts) == 3

    @pytest.mark.requirement("AC-1")
    def test_plugin_floe_api_version(self) -> None:
        """Plugin must report floe API version."""
        plugin = S3StoragePlugin()
        assert plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("AC-1")
    def test_plugin_description(self) -> None:
        """Plugin must have a description."""
        plugin = S3StoragePlugin()
        assert len(plugin.description) > 0

    @pytest.mark.requirement("AC-5")
    def test_tracer_name_is_dot_separated(self) -> None:
        """tracer_name must return 'floe.storage.s3' (dot-separated convention)."""
        plugin = S3StoragePlugin()
        assert plugin.tracer_name == "floe.storage.s3"

    @pytest.mark.requirement("AC-5")
    def test_tracer_name_follows_convention(self) -> None:
        """tracer_name must follow floe.<category>.<name> convention."""
        plugin = S3StoragePlugin()
        parts = plugin.tracer_name.split(".")
        assert len(parts) == 3, f"Expected 3 dot-separated parts, got {parts}"
        assert parts[0] == "floe", f"Tracer name must start with 'floe', got '{parts[0]}'"

    @pytest.mark.requirement("AC-1")
    def test_get_config_schema_returns_s3_config(self) -> None:
        """get_config_schema must return S3StorageConfig class."""
        plugin = S3StoragePlugin()
        schema = plugin.get_config_schema()
        assert schema is S3StorageConfig

    @pytest.mark.requirement("AC-1")
    def test_plugin_instantiates_without_config(self) -> None:
        """Plugin must accept config=None for loader discovery."""
        plugin = S3StoragePlugin()
        assert plugin._config is None

    @pytest.mark.requirement("AC-1")
    def test_plugin_instantiates_with_config(self) -> None:
        """Plugin must accept a real config."""
        config = S3StorageConfig(endpoint="http://minio:9000", bucket="test")
        plugin = S3StoragePlugin(config=config)
        assert plugin._config is config


# ---------------------------------------------------------------------------
# AC-2: S3StorageConfig Pydantic model
# ---------------------------------------------------------------------------


class TestS3StorageConfig:
    """Test S3StorageConfig validation."""

    @pytest.mark.requirement("AC-2")
    def test_valid_minimal_config(self) -> None:
        """Config with only required fields must validate."""
        config = S3StorageConfig(endpoint="http://minio:9000", bucket="data")
        assert config.endpoint == "http://minio:9000"
        assert config.bucket == "data"
        assert config.region == "us-east-1"
        assert config.path_style_access is True
        assert config.access_key_id is None
        assert config.secret_access_key is None

    @pytest.mark.requirement("AC-2")
    def test_valid_full_config(self) -> None:
        """Config with all fields must validate."""
        config = S3StorageConfig(
            endpoint="http://minio:9000",
            bucket="floe-data",
            region="eu-west-1",
            path_style_access=False,
            access_key_id=SecretStr("AKID"),
            secret_access_key=SecretStr("SECRET"),
        )
        assert config.region == "eu-west-1"
        assert config.path_style_access is False
        assert config.access_key_id is not None
        assert config.access_key_id.get_secret_value() == "AKID"

    @pytest.mark.requirement("AC-2")
    def test_demo_manifest_config(self) -> None:
        """Config matching demo/manifest.yaml must validate."""
        config = S3StorageConfig(
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
            S3StorageConfig(bucket="data")  # type: ignore[call-arg]

    @pytest.mark.requirement("AC-2")
    def test_missing_bucket_rejected(self) -> None:
        """Missing bucket must raise ValidationError."""
        with pytest.raises(ValidationError, match="bucket"):
            S3StorageConfig(endpoint="http://minio:9000")  # type: ignore[call-arg]

    @pytest.mark.requirement("AC-2")
    def test_empty_endpoint_rejected(self) -> None:
        """Empty endpoint must raise ValidationError."""
        with pytest.raises(ValidationError):
            S3StorageConfig(endpoint="", bucket="data")

    @pytest.mark.requirement("AC-2")
    def test_empty_bucket_rejected(self) -> None:
        """Empty bucket must raise ValidationError."""
        with pytest.raises(ValidationError):
            S3StorageConfig(endpoint="http://minio:9000", bucket="")

    @pytest.mark.requirement("AC-2")
    def test_extra_fields_rejected(self) -> None:
        """Unknown fields must raise ValidationError (extra=forbid)."""
        with pytest.raises(ValidationError):
            S3StorageConfig(
                endpoint="http://minio:9000",
                bucket="data",
                unknown_field="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("AC-2")
    def test_config_is_frozen(self) -> None:
        """Config must be immutable (frozen=True)."""
        config = S3StorageConfig(endpoint="http://minio:9000", bucket="data")
        with pytest.raises(ValidationError):
            config.endpoint = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StoragePlugin method tests (require config)
# ---------------------------------------------------------------------------


class TestStoragePluginMethods:
    """Test StoragePlugin ABC method implementations."""

    @pytest.fixture()
    def configured_plugin(self) -> S3StoragePlugin:
        """Return a plugin with valid config."""
        config = S3StorageConfig(
            endpoint="http://minio:9000",
            bucket="floe-data",
            region="us-east-1",
            path_style_access=True,
        )
        return S3StoragePlugin(config=config)

    @pytest.mark.requirement("AC-1")
    def test_get_warehouse_uri(self, configured_plugin: S3StoragePlugin) -> None:
        """get_warehouse_uri must return s3://bucket/namespace/ URI."""
        uri = configured_plugin.get_warehouse_uri("bronze")
        assert uri == "s3://floe-data/bronze/"

    @pytest.mark.requirement("AC-1")
    def test_get_warehouse_uri_different_namespace(
        self, configured_plugin: S3StoragePlugin
    ) -> None:
        """get_warehouse_uri must work for any namespace."""
        assert configured_plugin.get_warehouse_uri("silver") == "s3://floe-data/silver/"

    @pytest.mark.requirement("AC-1")
    def test_get_dbt_profile_config(self, configured_plugin: S3StoragePlugin) -> None:
        """get_dbt_profile_config must return S3-specific dbt config."""
        config = configured_plugin.get_dbt_profile_config()
        assert config["s3_region"] == "us-east-1"
        assert config["s3_endpoint"] == "http://minio:9000"
        assert config["s3_path_style_access"] is True

    @pytest.mark.requirement("AC-1")
    def test_get_dagster_io_manager_config(self, configured_plugin: S3StoragePlugin) -> None:
        """get_dagster_io_manager_config must return S3 IOManager config."""
        config = configured_plugin.get_dagster_io_manager_config()
        assert config["bucket"] == "floe-data"
        assert config["endpoint_url"] == "http://minio:9000"
        assert config["region_name"] == "us-east-1"

    @pytest.mark.requirement("AC-1")
    def test_get_helm_values_override_empty(self, configured_plugin: S3StoragePlugin) -> None:
        """get_helm_values_override must return empty dict (S3 is external)."""
        assert configured_plugin.get_helm_values_override() == {}

    @pytest.mark.requirement("AC-1")
    def test_get_pyiceberg_fileio(self, configured_plugin: S3StoragePlugin) -> None:
        """get_pyiceberg_fileio must return a FsspecFileIO instance."""
        from pyiceberg.io.fsspec import FsspecFileIO

        with patch.dict(
            "os.environ", {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"}
        ):
            fileio = configured_plugin.get_pyiceberg_fileio()
        assert isinstance(fileio, FsspecFileIO)


class TestUnconfiguredPlugin:
    """Test that unconfigured plugin raises clear errors."""

    @pytest.mark.requirement("AC-1")
    def test_methods_raise_without_config(self) -> None:
        """All StoragePlugin methods must raise RuntimeError when unconfigured."""
        plugin = S3StoragePlugin()
        with pytest.raises(RuntimeError, match="not configured"):
            plugin.get_warehouse_uri("test")
        with pytest.raises(RuntimeError, match="not configured"):
            plugin.get_dbt_profile_config()
        with pytest.raises(RuntimeError, match="not configured"):
            plugin.get_dagster_io_manager_config()
        with pytest.raises(RuntimeError, match="not configured"):
            plugin.get_pyiceberg_fileio()
