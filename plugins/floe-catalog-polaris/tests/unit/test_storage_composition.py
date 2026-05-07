"""Unit tests for Polaris storage composition."""

from __future__ import annotations

import pytest
from floe_core.schemas.compiled_artifacts import (
    DagsterStorageBinding,
    DbtStorageBinding,
    KubernetesSecretRef,
    StorageCapabilities,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageServiceEndpoint,
    StorageWarehouse,
)
from pydantic import SecretStr

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin


def _plugin() -> PolarisCatalogPlugin:
    return PolarisCatalogPlugin(
        config=PolarisCatalogConfig(
            uri="http://polaris:8181/api/catalog",
            warehouse="floe",
            oauth2=OAuth2Config(
                client_id="polaris",
                client_secret=SecretStr("polaris-secret"),
                token_url="http://polaris:8181/api/catalog/v1/oauth/tokens",
            ),
        )
    )


def _storage_binding(*, sts_supported: bool = False) -> StorageDeploymentBinding:
    return StorageDeploymentBinding(
        provider="minio",
        endpoint=StorageServiceEndpoint(
            internal_url="http://floe-platform-minio:9000",
            external_url="http://localhost:9000",
            region="us-east-1",
            warehouse_path="s3://floe-warehouse",
            path_style_access=True,
        ),
        warehouse=StorageWarehouse(
            uri="s3://floe-warehouse",
            bucket="floe-warehouse",
        ),
        allowed_locations=["s3://floe-warehouse", "s3://floe-artifacts"],
        credentials=StorageCredentialBinding(
            mode="kubernetes-secret",
            secret_ref=KubernetesSecretRef(
                name="floe-platform-minio-credentials",
                namespace="floe-system",
                keys={
                    "accessKeyId": "access-key-id",
                    "secretAccessKey": "secret-access-key",  # pragma: allowlist secret
                },
            ),
        ),
        capabilities=StorageCapabilities(
            protocols=["s3-compatible", "s3"],
            credential_modes=["kubernetes-secret"],
            sts_supported=sts_supported,
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


def test_build_catalog_deployment_translates_storage_binding_to_polaris_binding() -> None:
    """Polaris owns the catalog-specific projection of neutral storage state."""
    binding = _plugin().build_catalog_deployment(_storage_binding(sts_supported=False))

    assert binding.provider == "polaris"
    assert binding.polaris.storage_type == "S3"
    assert binding.polaris.endpoint == "http://localhost:9000"
    assert binding.polaris.endpoint_internal == "http://floe-platform-minio:9000"
    assert binding.polaris.default_base_location == "s3://floe-warehouse"
    assert binding.polaris.path_style_access is True
    assert binding.polaris.sts_unavailable is True
    assert binding.polaris.allowed_locations == [
        "s3://floe-warehouse",
        "s3://floe-artifacts",
    ]
    assert binding.polaris.credential_refs["accessKeyId"].source == "kubernetes-secret"
    assert binding.polaris.credential_refs["accessKeyId"].name == (
        "floe-platform-minio-credentials"
    )
    assert binding.polaris.credential_refs["accessKeyId"].key == "access-key-id"
    assert binding.polaris.credential_refs["secretAccessKey"].source == "kubernetes-secret"
    assert binding.polaris.credential_refs["secretAccessKey"].name == (
        "floe-platform-minio-credentials"
    )
    assert binding.polaris.credential_refs["secretAccessKey"].key == "secret-access-key"

    payload = binding.model_dump_json()
    assert "raw-secret-value" not in payload


def test_build_catalog_deployment_requires_storage_warehouse() -> None:
    """Polaris bootstrap configuration needs an explicit warehouse URI."""
    storage = _storage_binding().model_copy(update={"warehouse": None})

    with pytest.raises(ValueError, match="warehouse"):
        _plugin().build_catalog_deployment(storage)


def test_get_storage_requirements_declares_polaris_storage_needs() -> None:
    """Polaris declares the storage capabilities it can compose with."""
    requirements = _plugin().get_storage_requirements()

    assert requirements.plugin_type == "catalog"
    assert requirements.plugin_name == "polaris"
    assert requirements.requirements.protocols == ["s3-compatible", "s3"]
    assert requirements.requirements.credential_modes == [
        "kubernetes-secret",
        "workload-identity",
    ]
    assert requirements.requirements.requires_server_side_storage_access is True
    assert requirements.requirements.supports_no_sts is True
    assert requirements.requirements.supports_path_style_access is True
