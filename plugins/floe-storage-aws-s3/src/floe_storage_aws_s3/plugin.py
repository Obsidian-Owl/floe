"""AWS S3 StoragePlugin implementation for Floe."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from floe_core.plugins.storage import StoragePlugin
from floe_core.schemas.compiled_artifacts import (
    DagsterStorageBinding,
    DbtStorageBinding,
    KubernetesSecretRef,
    StorageBucketRequirement,
    StorageCapabilities,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageProvisioningIntent,
    StorageRuntimeBinding,
    StorageServiceEndpoint,
    StorageWarehouse,
)

from floe_storage_aws_s3.config import AwsS3ObjectStoreConfig

if TYPE_CHECKING:
    from floe_core.plugins.storage import FileIO
    from pydantic import BaseModel

TRACER_NAME = "floe.storage.aws_s3"
AWS_ACCESS_KEY_ENV = "AWS_ACCESS_KEY_ID"
AWS_SECRET_KEY_ENV = "AWS_SECRET_ACCESS_KEY"  # pragma: allowlist secret
AWS_SESSION_TOKEN_ENV = "AWS_SESSION_TOKEN"
KEY_ACCESS_KEY_ID = "accessKeyId"
KEY_SECRET_ACCESS_KEY = "secretAccessKey"  # pragma: allowlist secret
KEY_SESSION_TOKEN = "sessionToken"


def _s3_uri(bucket: str, prefix: str) -> str:
    """Build an S3 URI from bucket and normalized prefix."""
    return f"s3://{bucket}/{prefix}" if prefix else f"s3://{bucket}"


class AwsS3ObjectStorePlugin(StoragePlugin):
    """Native AWS S3 storage plugin implementing the StoragePlugin ABC."""

    def __init__(self, config: AwsS3ObjectStoreConfig | None = None) -> None:
        """Initialize the AWS S3 storage plugin."""
        super().__init__()
        self._config = config

    def _require_config(self) -> AwsS3ObjectStoreConfig:
        """Return config or raise a structured plugin configuration error."""
        if self._config is None:
            from floe_core.plugin_errors import PluginConfigurationError

            raise PluginConfigurationError(
                "aws-s3",
                [{"field": "_config", "message": "Plugin 'aws-s3' not configured"}],
            )
        if not isinstance(self._config, AwsS3ObjectStoreConfig):
            from floe_core.plugin_errors import PluginConfigurationError

            raise PluginConfigurationError(
                "aws-s3",
                [{"field": "_config", "message": "Plugin 'aws-s3' config has invalid type"}],
            )
        return self._config

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "aws-s3"

    @property
    def version(self) -> str:
        """Return the plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Return the required Floe API version."""
        return "1.0"

    @property
    def description(self) -> str:
        """Return a human-readable plugin description."""
        return "AWS S3 object storage plugin for Iceberg data"

    @property
    def tracer_name(self) -> str:
        """Return the OpenTelemetry tracer name."""
        return TRACER_NAME

    def get_config_schema(self) -> type[BaseModel]:
        """Return the Pydantic config schema for this plugin."""
        return AwsS3ObjectStoreConfig

    def _endpoint_url(self) -> str:
        """Return the S3 endpoint URL used by runtime consumers."""
        config = self._require_config()
        return config.endpoint_override or f"https://s3.{config.region}.amazonaws.com"

    def _pyiceberg_properties(self) -> dict[str, str]:
        """Return non-secret PyIceberg S3 properties."""
        config = self._require_config()
        properties = {"s3.region": config.region}
        if config.endpoint_override is not None:
            properties["s3.endpoint"] = config.endpoint_override
            properties["s3.path-style-access"] = str(config.path_style_access).lower()
        return properties

    def get_pyiceberg_fileio(self) -> FileIO:
        """Create a PyIceberg FileIO instance for AWS S3."""
        from pyiceberg.io.fsspec import FsspecFileIO

        return FsspecFileIO(properties=self._pyiceberg_properties())

    def get_pyiceberg_catalog_config(self) -> dict[str, Any]:
        """Return non-secret PyIceberg catalog config for legacy callers."""
        return self._pyiceberg_properties()

    def _credential_binding(self) -> StorageCredentialBinding:
        """Return secret-free credential references for the configured mode."""
        config = self._require_config()
        if config.credential_mode == "workload-identity":
            if config.service_account_ref is None:
                msg = "workload-identity credential_mode requires service_account_ref"
                raise ValueError(msg)
            return StorageCredentialBinding(
                mode="workload-identity",
                service_account_ref=config.service_account_ref,
            )
        if config.credential_mode == "kubernetes-secret":
            if config.credential_secret_name is None:
                msg = "kubernetes-secret credential_mode requires credential_secret_name"
                raise ValueError(msg)
            return StorageCredentialBinding(
                mode="kubernetes-secret",
                secret_ref=KubernetesSecretRef(
                    name=config.credential_secret_name,
                    namespace=config.credential_secret_namespace,
                    keys={
                        KEY_ACCESS_KEY_ID: config.access_key_secret_key,
                        KEY_SECRET_ACCESS_KEY: config.secret_key_secret_key,
                        KEY_SESSION_TOKEN: config.session_token_secret_key,
                    },
                ),
            )
        return StorageCredentialBinding(
            mode="environment",
            env_refs={
                KEY_ACCESS_KEY_ID: AWS_ACCESS_KEY_ENV,
                KEY_SECRET_ACCESS_KEY: AWS_SECRET_KEY_ENV,
                KEY_SESSION_TOKEN: AWS_SESSION_TOKEN_ENV,
            },
        )

    def get_deployment_binding(self) -> StorageDeploymentBinding:
        """Return secret-free AWS S3 deployment binding for compiled artifacts."""
        config = self._require_config()
        endpoint = self._endpoint_url()
        warehouse_uri = _s3_uri(config.bucket, config.warehouse_prefix)
        artifact_bucket = config.artifact_bucket or config.bucket
        artifact_uri = _s3_uri(artifact_bucket, config.artifact_prefix)
        credential_binding = self._credential_binding()
        identity_modes = (
            ["aws-irsa", "aws-pod-identity"]
            if config.credential_mode == "workload-identity"
            else []
        )
        runtime_env_refs = (
            dict(credential_binding.env_refs) if config.credential_mode == "environment" else {}
        )
        runtime_properties = self._pyiceberg_properties()
        dbt_profile_fragment: dict[str, Any] = {
            "s3_region": config.region,
            "s3_path_style_access": config.path_style_access,
        }
        dagster_resources: dict[str, Any] = {
            "bucket": config.bucket,
            "region_name": config.region,
            "path_style_access": config.path_style_access,
        }
        if config.endpoint_override is not None:
            dbt_profile_fragment["s3_endpoint"] = config.endpoint_override
            dagster_resources["endpoint_url"] = config.endpoint_override

        dbt_env_refs = (
            {
                "s3_access_key_id": AWS_ACCESS_KEY_ENV,
                "s3_secret_access_key": AWS_SECRET_KEY_ENV,
            }
            if config.credential_mode == "environment"
            else {}
        )
        dagster_env_refs = (
            {
                AWS_ACCESS_KEY_ENV: AWS_ACCESS_KEY_ENV,
                AWS_SECRET_KEY_ENV: AWS_SECRET_KEY_ENV,
                AWS_SESSION_TOKEN_ENV: AWS_SESSION_TOKEN_ENV,
            }
            if config.credential_mode == "environment"
            else {}
        )

        return StorageDeploymentBinding(
            provider="aws-s3",
            protocol="s3",
            endpoint=StorageServiceEndpoint(
                internal_url=endpoint,
                external_url=endpoint,
                region=config.region,
                warehouse_path=warehouse_uri,
                path_style_access=config.path_style_access,
            ),
            warehouse=StorageWarehouse(
                uri=warehouse_uri,
                bucket=config.bucket,
                prefix=config.warehouse_prefix,
            ),
            allowed_locations=[warehouse_uri, artifact_uri],
            buckets=[
                StorageBucketRequirement(
                    name=config.bucket,
                    uri=warehouse_uri,
                    purpose="warehouse",
                    create_policy=config.create_policy,
                    prefixes=[config.warehouse_prefix],
                ),
                StorageBucketRequirement(
                    name=artifact_bucket,
                    uri=artifact_uri,
                    purpose="artifacts",
                    create_policy=config.create_policy,
                    prefixes=[config.artifact_prefix],
                ),
            ],
            credentials=credential_binding,
            capabilities=StorageCapabilities(
                protocols=["s3"],
                credential_modes=[config.credential_mode],
                identity_modes=identity_modes,
                sts_supported=config.sts_supported,
                path_style_access=config.path_style_access,
            ),
            provisioning=StorageProvisioningIntent(
                enabled=False,
                mode="external",
                default_create_policy=config.create_policy,
            ),
            runtime=StorageRuntimeBinding(
                pyiceberg_properties=runtime_properties,
                dbt_profile_fragment=dbt_profile_fragment,
                dagster_resources=dagster_resources,
                env_refs=runtime_env_refs,
            ),
            dbt=DbtStorageBinding(
                profile_name="floe",
                target_name="dev",
                schema_name="analytics",
                profile_fragment=dbt_profile_fragment,
                env_refs=dbt_env_refs,
            ),
            dagster=DagsterStorageBinding(
                resource_key="aws_s3_storage",
                asset_io_manager_key="iceberg_io_manager",
                resources=dagster_resources,
                env_refs=dagster_env_refs,
            ),
            notes=[
                "AWS S3 buckets are externally managed; compile does not create buckets.",
                f"Artifact location: {artifact_uri}",
            ],
        )

    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate warehouse URI for a namespace."""
        config = self._require_config()
        return _s3_uri(config.bucket, f"{config.warehouse_prefix}{namespace}/")

    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Return storage-specific dbt profile config."""
        return dict(self.get_deployment_binding().dbt.profile_fragment)

    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Return storage-specific Dagster resource config."""
        return dict(self.get_deployment_binding().dagster.resources)

    def get_helm_values_override(self) -> dict[str, Any]:
        """Return no chart values; AWS S3 is externally managed."""
        self._require_config()
        return {}
