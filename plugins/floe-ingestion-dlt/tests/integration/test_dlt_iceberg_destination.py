"""dlt Iceberg destination integration tests."""

from __future__ import annotations

import os
import uuid
from typing import Any

import dlt
import pytest
from floe_core.plugins.ingestion import IngestionConfig
from testing.fixtures.credentials import (
    get_minio_credentials,
    get_polaris_credentials,
    get_polaris_oauth2_server_uri,
    get_polaris_scope,
    get_polaris_warehouse,
)
from testing.fixtures.polaris import (
    PolarisConfig,
    create_polaris_catalog,
    rewrite_table_io_for_host_access,
)
from testing.fixtures.services import ServiceEndpoint

from floe_ingestion_dlt.config import DltIngestionConfig, IngestionSourceConfig
from floe_ingestion_dlt.plugin import DltIngestionPlugin


def _catalog_config() -> dict[str, Any]:
    polaris_uri = os.environ.get("POLARIS_URI")
    if polaris_uri is None:
        polaris_uri = f"{ServiceEndpoint('polaris').url}/api/catalog"

    minio_endpoint = os.environ.get("MINIO_ENDPOINT")
    if minio_endpoint is None:
        minio_endpoint = os.environ.get("MINIO_URL", ServiceEndpoint("minio").url)

    client_id, client_secret = get_polaris_credentials()
    return {
        "uri": polaris_uri,
        "warehouse": os.environ.get("POLARIS_WAREHOUSE", get_polaris_warehouse()),
        "credential": os.environ.get(
            "POLARIS_CREDENTIAL",
            f"{client_id}:{client_secret}",  # pragma: allowlist secret
        ),
        "scope": os.environ.get("POLARIS_SCOPE", get_polaris_scope()),
        "oauth2_server_uri": get_polaris_oauth2_server_uri(catalog_endpoint=polaris_uri),
        "bucket": os.environ.get("MINIO_BUCKET", "floe-iceberg"),
        "s3_endpoint": minio_endpoint,
        "s3_region": os.environ.get("AWS_REGION", "us-east-1"),
        "s3_path_style_access": True,
    }


def _runtime_binding(catalog_config: dict[str, Any]) -> dict[str, Any]:
    catalog_name = str(catalog_config.get("catalog_name", "polaris"))
    env_catalog = catalog_name.upper().replace("-", "_")
    prefix = f"PYICEBERG_CATALOG__{env_catalog}__"
    iceberg_catalog_env = {
        "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": catalog_name,
        "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
        f"{prefix}TYPE": "rest",
        f"{prefix}URI": str(catalog_config["uri"]),
        f"{prefix}WAREHOUSE": str(catalog_config["warehouse"]),
        f"{prefix}S3__ENDPOINT": str(catalog_config["s3_endpoint"]),
        f"{prefix}S3__REGION": str(catalog_config["s3_region"]),
    }
    if catalog_config.get("s3_path_style_access"):
        iceberg_catalog_env[f"{prefix}S3__PATH_STYLE_ACCESS"] = "true"
    if catalog_config.get("credential"):
        iceberg_catalog_env[f"{prefix}CREDENTIAL"] = str(catalog_config["credential"])
    if catalog_config.get("scope"):
        iceberg_catalog_env[f"{prefix}SCOPE"] = str(catalog_config["scope"])
    if catalog_config.get("oauth2_server_uri"):
        iceberg_catalog_env[f"{prefix}OAUTH2_SERVER_URI"] = str(catalog_config["oauth2_server_uri"])
    return {
        "destination": "filesystem",
        "source": "filesystem",
        "destination_filesystem": _destination_filesystem_binding(catalog_config),
        "source_filesystem": {
            "endpoint_url": catalog_config["s3_endpoint"],
            "region_name": catalog_config["s3_region"],
            "s3_url_style": "path" if catalog_config["s3_path_style_access"] else "virtual",
        },
        "iceberg_catalog_env": iceberg_catalog_env,
    }


def _destination_filesystem_binding(catalog_config: dict[str, Any]) -> dict[str, Any]:
    """Build dlt filesystem destination config in runtime-binding shape."""
    bucket_url = str(catalog_config.get("bucket_url") or catalog_config["bucket"])
    if "://" not in bucket_url:
        bucket_url = f"s3://{bucket_url}"
    credentials = {
        "endpoint_url": catalog_config["s3_endpoint"],
        "region_name": catalog_config["s3_region"],
    }
    if catalog_config.get("s3_path_style_access"):
        credentials["s3_url_style"] = "path"
    return {
        "bucket_url": bucket_url,
        "credentials": credentials,
    }


def test_dlt_writes_iceberg_table_via_polaris_and_minio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tiny in-memory dlt resource lands in Polaris-backed Iceberg."""
    namespace = f"dlt_task6_{uuid.uuid4().hex[:12]}"
    table_name = "tiny_rows"
    destination_table = f"{namespace}.{table_name}"
    catalog_config = _catalog_config()
    minio_access, minio_secret = get_minio_credentials()
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", minio_access)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", minio_secret)  # pragma: allowlist secret
    monkeypatch.setenv("AWS_REGION", catalog_config["s3_region"])

    catalog = create_polaris_catalog(
        PolarisConfig(
            uri=catalog_config["uri"],
            warehouse=catalog_config["warehouse"],
            scope=catalog_config["scope"],
        )
    )

    plugin = DltIngestionPlugin()
    plugin.configure(
        DltIngestionConfig(
            sources=[
                IngestionSourceConfig(
                    name="tiny_rows",
                    source_type="filesystem",
                    source_config={},
                    destination_table=destination_table,
                )
            ]
        )
    )
    plugin.startup()

    @dlt.resource(name=table_name)
    def tiny_rows() -> Any:
        yield {"id": 1, "name": "one"}
        yield {"id": 2, "name": "two"}

    try:
        pipeline = plugin.create_pipeline(
            IngestionConfig(
                source_type="filesystem",
                source_config={},
                destination_table=destination_table,
                write_mode="replace",
                runtime_binding=_runtime_binding(catalog_config),
            )
        )

        result = plugin.run(
            pipeline,
            source=tiny_rows,
            table_name=table_name,
            write_disposition="replace",
            schema_contract="evolve",
        )
        assert result.success, result.errors

        table = catalog.load_table(destination_table)
        rewrite_table_io_for_host_access(table)
        rows = table.scan().to_arrow().to_pylist()

        assert sorted(rows, key=lambda row: row["id"]) == [
            {"id": 1, "name": "one"},
            {"id": 2, "name": "two"},
        ]
    finally:
        plugin.shutdown()
        try:
            catalog.drop_table(destination_table, purge_requested=False)
        except Exception:
            pass
        try:
            catalog.drop_namespace(namespace)
        except Exception:
            pass
