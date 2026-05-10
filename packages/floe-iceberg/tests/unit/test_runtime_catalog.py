"""Tests for translating runtime catalog projections to PyIceberg config."""

from __future__ import annotations

from floe_core.schemas.compiled_artifacts import CredentialRef, RuntimeCatalogConnection

from floe_iceberg.runtime_catalog import runtime_catalog_connection_to_pyiceberg_config


def test_runtime_catalog_connection_to_pyiceberg_config_maps_non_secret_fields() -> None:
    connection = RuntimeCatalogConnection(
        catalog_name="polaris",
        catalog_uri="http://polaris:8181/api/catalog",
        warehouse="s3://floe-iceberg",
        storage_endpoint="http://floe-platform-minio:9000",
        region="us-east-1",
        path_style_access=True,
        properties={"token-refresh-enabled": "true"},
        credential_refs={
            "accessKeyId": CredentialRef(source="none", name="none"),
        },
        env_refs={"PYICEBERG_CATALOG__POLARIS__CREDENTIAL": "POLARIS_CREDENTIAL"},
    )

    config = runtime_catalog_connection_to_pyiceberg_config(connection)

    assert config == {
        "uri": "http://polaris:8181/api/catalog",
        "warehouse": "s3://floe-iceberg",
        "s3.endpoint": "http://floe-platform-minio:9000",
        "s3.region": "us-east-1",
        "s3.path-style-access": "true",
        "token-refresh-enabled": "true",
    }


def test_runtime_catalog_connection_to_pyiceberg_config_omits_missing_fields() -> None:
    config = runtime_catalog_connection_to_pyiceberg_config(
        RuntimeCatalogConnection(catalog_name="iceberg")
    )

    assert config == {}


def test_runtime_catalog_connection_to_pyiceberg_config_handles_none_connection() -> None:
    assert runtime_catalog_connection_to_pyiceberg_config(None) == {}


def test_runtime_catalog_connection_to_pyiceberg_config_merges_properties_last() -> None:
    connection = RuntimeCatalogConnection(
        catalog_name="polaris",
        catalog_uri="http://polaris:8181/api/catalog",
        warehouse="s3://floe-iceberg",
        storage_endpoint="http://floe-platform-minio:9000",
        region="us-east-1",
        path_style_access=True,
        properties={
            "s3.endpoint": "http://override-minio:9000",
            "s3.path-style-access": "false",
        },
    )

    config = runtime_catalog_connection_to_pyiceberg_config(connection)

    assert config["s3.endpoint"] == "http://override-minio:9000"
    assert config["s3.path-style-access"] == "false"
    assert config["s3.region"] == "us-east-1"
