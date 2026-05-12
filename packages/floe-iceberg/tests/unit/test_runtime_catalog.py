"""Tests for translating runtime catalog projections to PyIceberg config."""

from __future__ import annotations

from unittest.mock import Mock, patch

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


def test_runtime_catalog_connection_to_pyiceberg_config_preserves_glue_properties() -> None:
    connection = RuntimeCatalogConnection(
        catalog_name="glue",
        warehouse="s3://floe-provider-tests/warehouse/",
        properties={
            "type": "glue",
            "glue.region": "ap-southeast-2",
            "glue.id": "278833447053",
            "glue.skip-archive": "true",
            "glue.max-retries": 5,
            "glue.retry-mode": "standard",
        },
    )

    config = runtime_catalog_connection_to_pyiceberg_config(connection)

    assert config == {
        "warehouse": "s3://floe-provider-tests/warehouse/",
        "type": "glue",
        "glue.region": "ap-southeast-2",
        "glue.id": "278833447053",
        "glue.skip-archive": "true",
        "glue.max-retries": 5,
        "glue.retry-mode": "standard",
    }


def test_runtime_catalog_connection_to_pyiceberg_config_preserves_glue_retry_type() -> None:
    connection = RuntimeCatalogConnection(
        catalog_name="glue",
        warehouse="s3://floe-provider-tests/warehouse/",
        properties={
            "type": "glue",
            "glue.region": "ap-southeast-2",
            "glue.max-retries": 5,
            "glue.retry-mode": "standard",
        },
    )

    config = runtime_catalog_connection_to_pyiceberg_config(connection)

    assert config["glue.max-retries"] == 5
    assert isinstance(config["glue.max-retries"], int)


def test_pyiceberg_glue_catalog_accepts_typed_retry_config_without_aws_call() -> None:
    from pyiceberg.catalog import load_catalog

    connection = RuntimeCatalogConnection(
        catalog_name="glue",
        warehouse="s3://floe-provider-tests/warehouse/",
        properties={
            "type": "glue",
            "glue.region": "ap-southeast-2",
            "glue.skip-archive": "true",
            "glue.max-retries": 5,
            "glue.retry-mode": "standard",
        },
    )
    config = runtime_catalog_connection_to_pyiceberg_config(connection)

    with patch("pyiceberg.catalog.glue.boto3.Session") as session_cls:
        session = session_cls.return_value
        session.client.return_value = Mock()

        load_catalog("glue", **config)

    client_kwargs = session.client.call_args.kwargs
    assert client_kwargs["config"].retries == {
        "max_attempts": 5,
        "mode": "standard",
    }
