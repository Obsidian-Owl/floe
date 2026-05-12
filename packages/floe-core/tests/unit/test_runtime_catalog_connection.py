from __future__ import annotations

from floe_core.runtime_catalog_connection import build_runtime_catalog_connection
from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    CredentialRef,
    DagsterStorageBinding,
    DbtStorageBinding,
    GlueCatalogDeploymentBinding,
    PolarisCatalogDeploymentBinding,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageServiceEndpoint,
    StorageWarehouse,
)


def _storage_binding() -> StorageDeploymentBinding:
    return StorageDeploymentBinding(
        provider="minio",
        protocol="s3-compatible",
        endpoint=StorageServiceEndpoint(
            internal_url="http://floe-platform-minio:9000",
            external_url="http://localhost:9000",
            region="us-east-1",
            warehouse_path="s3://floe-iceberg",
            path_style_access=True,
        ),
        warehouse=StorageWarehouse(uri="s3://floe-iceberg", bucket="floe-iceberg"),
        credentials=StorageCredentialBinding(mode="none"),
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


def _catalog_binding() -> CatalogDeploymentBinding:
    return CatalogDeploymentBinding(
        provider="polaris",
        polaris=PolarisCatalogDeploymentBinding(
            storage_type="S3",
            warehouse="s3://floe-iceberg",
            default_base_location="s3://floe-iceberg",
            allowed_locations=["s3://floe-iceberg"],
            endpoint="http://localhost:9000",
            endpoint_internal="http://floe-platform-minio:9000",
            catalog_uri="http://polaris:8181/api/catalog",
            path_style_access=True,
            sts_unavailable=True,
            credential_refs={
                "accessKeyId": CredentialRef(source="none", name="none"),
                "secretAccessKey": CredentialRef(  # pragma: allowlist secret
                    source="none",
                    name="none",
                ),
            },
        ),
    )


def test_build_runtime_catalog_connection_prefers_catalog_owned_fields() -> None:
    connection = build_runtime_catalog_connection(
        storage=_storage_binding(),
        catalog=_catalog_binding(),
    )

    assert connection.catalog_name == "polaris"
    assert connection.catalog_uri == "http://polaris:8181/api/catalog"
    assert connection.warehouse == "s3://floe-iceberg"
    assert connection.storage_endpoint == "http://floe-platform-minio:9000"
    assert connection.region == "us-east-1"
    assert connection.path_style_access is True
    assert connection.credential_refs["accessKeyId"].source == "none"


def test_build_runtime_catalog_connection_degrades_without_catalog() -> None:
    connection = build_runtime_catalog_connection(storage=_storage_binding(), catalog=None)

    assert connection.catalog_name == "iceberg"
    assert connection.catalog_uri is None
    assert connection.warehouse == "s3://floe-iceberg"
    assert connection.storage_endpoint == "http://floe-platform-minio:9000"
    assert connection.region == "us-east-1"
    assert connection.path_style_access is True


def test_build_runtime_catalog_connection_maps_glue_binding() -> None:
    catalog = CatalogDeploymentBinding(
        provider="glue",
        glue=GlueCatalogDeploymentBinding(
            catalog_name="glue",
            region="ap-southeast-2",
            warehouse="s3://floe-provider-tests/warehouse/",
            catalog_id="278833447053",
            database_prefix="floe_provider_",
            endpoint="https://glue.ap-southeast-2.amazonaws.com",
            skip_archive=True,
            max_retries=5,
            retry_mode="standard",
        ),
    )

    connection = build_runtime_catalog_connection(storage=None, catalog=catalog)

    assert connection.catalog_name == "glue"
    assert connection.warehouse == "s3://floe-provider-tests/warehouse/"
    assert connection.region == "ap-southeast-2"
    assert connection.properties == {
        "type": "glue",
        "glue.region": "ap-southeast-2",
        "glue.id": "278833447053",
        "glue.endpoint": "https://glue.ap-southeast-2.amazonaws.com",
        "glue.skip-archive": "true",
        "glue.max-retries": 5,
        "glue.retry-mode": "standard",
    }
