"""Destination configuration tests for the dlt ingestion plugin."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest
from floe_core.plugin_metadata import HealthState
from floe_core.plugins.ingestion import IngestionConfig

from floe_ingestion_dlt.config import DltIngestionConfig, IngestionSourceConfig
from floe_ingestion_dlt.plugin import DltIngestionPlugin


def _plugin_config(catalog_config: dict[str, Any]) -> DltIngestionConfig:
    return DltIngestionConfig(
        sources=[
            IngestionSourceConfig(
                name="orders",
                source_type="filesystem",
                destination_table="bronze.orders",
            )
        ],
        catalog_config=catalog_config,
    )


def test_destination_config_matches_dlt_filesystem_iceberg_setup() -> None:
    """Catalog config maps to the exact kwargs used to build dlt filesystem destination."""
    plugin = DltIngestionPlugin()

    destination_config = plugin.get_destination_config(
        {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe-demo",
            "bucket": "floe-iceberg",
            "s3_endpoint": "http://minio:9000",
            "s3_region": "us-east-1",
            "s3_path_style_access": True,
            "s3_access_key": "must-not-pass-through",  # pragma: allowlist secret
            "s3_secret_key": "must-not-pass-through",  # pragma: allowlist secret
        }
    )

    assert destination_config == {
        "bucket_url": "s3://floe-iceberg",
        "credentials": {
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
            "s3_url_style": "path",
        },
    }


def test_destination_config_accepts_explicit_bucket_url() -> None:
    """An explicit object-store URL is passed directly to dlt filesystem."""
    plugin = DltIngestionPlugin()

    destination_config = plugin.get_destination_config(
        {
            "bucket_url": "s3://custom-warehouse/root",
            "s3_endpoint": "http://minio:9000",
        }
    )

    assert destination_config == {
        "bucket_url": "s3://custom-warehouse/root",
        "credentials": {
            "endpoint_url": "http://minio:9000",
            "s3_url_style": "path",
        },
    }


def test_create_pipeline_passes_filesystem_destination_and_sets_pyiceberg_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline creation wires dlt filesystem destination and PyIceberg catalog env."""
    destination_calls: list[dict[str, Any]] = []
    pipeline_calls: list[dict[str, Any]] = []
    fake_destination = object()

    def fake_filesystem(**kwargs: Any) -> object:
        destination_calls.append(kwargs)
        return fake_destination

    def fake_pipeline(**kwargs: Any) -> SimpleNamespace:
        pipeline_calls.append(kwargs)
        return SimpleNamespace(pipeline_name=kwargs["pipeline_name"])

    import dlt
    import dlt.destinations

    monkeypatch.setattr(dlt.destinations, "filesystem", fake_filesystem)
    monkeypatch.setattr(dlt, "pipeline", fake_pipeline)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "env-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "env-secret")  # pragma: allowlist secret

    plugin = DltIngestionPlugin()
    plugin.configure(
        _plugin_config(
            {
                "uri": "http://polaris:8181/api/catalog",
                "warehouse": "floe-demo",
                "bucket": "floe-iceberg",
                "s3_endpoint": "http://minio:9000",
                "s3_region": "us-east-1",
                "credential": "client:secret",  # pragma: allowlist secret
                "scope": "PRINCIPAL_ROLE:ALL",
                "oauth2_server_uri": "http://polaris:8181/api/catalog/v1/oauth/tokens",
            }
        )
    )
    plugin.startup()

    pipeline = plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={},
            destination_table="bronze.orders",
        )
    )

    assert pipeline.pipeline_name == "ingest_orders"
    assert destination_calls == [
        {
            "bucket_url": "s3://floe-iceberg",
            "credentials": {
                "endpoint_url": "http://minio:9000",
                "region_name": "us-east-1",
                "s3_url_style": "path",
            },
        }
    ]
    assert pipeline_calls == [
        {
            "pipeline_name": "ingest_orders",
            "dataset_name": "bronze",
            "destination": fake_destination,
        }
    ]
    assert os.environ["ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"] == "polaris"
    assert os.environ["ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE"] == "rest"
    assert os.environ["PYICEBERG_CATALOG__POLARIS__TYPE"] == "rest"
    assert os.environ["PYICEBERG_CATALOG__POLARIS__URI"] == "http://polaris:8181/api/catalog"
    assert os.environ["PYICEBERG_CATALOG__POLARIS__WAREHOUSE"] == "floe-demo"
    assert os.environ["PYICEBERG_CATALOG__POLARIS__S3__ENDPOINT"] == ("http://minio:9000")
    assert os.environ["PYICEBERG_CATALOG__POLARIS__S3__ACCESS_KEY_ID"] == ("env-access")
    assert os.environ["PYICEBERG_CATALOG__POLARIS__S3__SECRET_ACCESS_KEY"] == ("env-secret")


def test_create_pipeline_prefers_source_config_catalog_over_plugin_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source-level catalog_config can override plugin-level catalog config."""
    destination_calls: list[dict[str, Any]] = []

    def fake_filesystem(**kwargs: Any) -> object:
        destination_calls.append(kwargs)
        return object()

    import dlt
    import dlt.destinations

    monkeypatch.setattr(dlt.destinations, "filesystem", fake_filesystem)
    monkeypatch.setattr(dlt, "pipeline", lambda **kwargs: SimpleNamespace(**kwargs))

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"bucket": "plugin-bucket"}))
    plugin.startup()

    plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={"catalog_config": {"bucket": "source-bucket"}},
            destination_table="bronze.orders",
        )
    )

    assert destination_calls == [{"bucket_url": "s3://source-bucket"}]


def test_health_check_stays_fast_without_catalog_config() -> None:
    """Unconfigured health check remains import-only and non-networked."""
    plugin = DltIngestionPlugin()
    plugin.startup()

    status = plugin.health_check()

    assert status.state is HealthState.HEALTHY
    assert status.details["catalog_check"] == "not_configured"
    assert status.details["object_storage_check"] == "not_configured"


def test_health_check_distinguishes_catalog_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured health check reports catalog failures separately."""
    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"uri": "http://polaris:8181/api/catalog"}))
    plugin.startup()
    monkeypatch.setattr(plugin, "_check_catalog_reachable", lambda *_args, **_kwargs: "timeout")
    monkeypatch.setattr(plugin, "_check_object_storage_reachable", lambda *_args, **_kwargs: None)

    status = plugin.health_check()

    assert status.state is HealthState.UNHEALTHY
    assert status.details["reason"] == "catalog_unreachable"
    assert status.details["catalog_error"] == "timeout"


def test_health_check_distinguishes_object_storage_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured health check reports object storage failures separately."""
    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"uri": "http://polaris:8181/api/catalog", "bucket": "wh"}))
    plugin.startup()
    monkeypatch.setattr(plugin, "_check_catalog_reachable", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        plugin,
        "_check_object_storage_reachable",
        lambda *_args, **_kwargs: "connection refused",
    )

    status = plugin.health_check()

    assert status.state is HealthState.UNHEALTHY
    assert status.details["reason"] == "object_storage_unreachable"
    assert status.details["object_storage_error"] == "connection refused"
