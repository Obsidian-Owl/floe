"""Customer 360 dlt ingestion E2E against Polaris and MinIO.

This test exercises the same filesystem source construction and
``DltIngestionPlugin`` execution path used by Dagster ingestion assets, then
validates the raw Iceberg tables directly through PyIceberg.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from floe_core.compilation.stages import compile_pipeline
from floe_core.plugins.ingestion import IngestionConfig
from floe_core.schemas.compiled_artifacts import CompiledArtifacts
from floe_ingestion_dlt.config import DltIngestionConfig
from floe_ingestion_dlt.plugin import DltIngestionPlugin
from floe_orchestrator_dagster.ingestion import build_dlt_source

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.credentials import (
    get_minio_credentials,
    get_polaris_credentials,
    get_polaris_oauth2_server_uri,
    get_polaris_scope,
    get_polaris_warehouse,
)
from testing.fixtures.minio import MinIOConfig, ensure_bucket, minio_client_context
from testing.fixtures.polaris import rewrite_table_io_for_host_access
from testing.fixtures.services import ServiceEndpoint

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.developer_workflow,
    pytest.mark.requirement("4F-E2E-CUSTOMER360-DLT"),
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CUSTOMER_360_DIR = PROJECT_ROOT / "demo" / "customer-360"
CUSTOMER_360_SPEC = CUSTOMER_360_DIR / "floe.yaml"
DEMO_MANIFEST = PROJECT_ROOT / "demo" / "manifest.yaml"
LOGICAL_RAW_TABLES = (
    "bronze.raw_customers",
    "bronze.raw_transactions",
    "bronze.raw_support_tickets",
)


def _isolated_bronze_namespace(e2e_namespace: str) -> str:
    """Return a PyIceberg-safe namespace derived from the E2E session id."""
    return f"bronze_{e2e_namespace.replace('-', '_')}"


def _load_customer360_artifacts(tmp_path: Path) -> CompiledArtifacts:
    """Compile Customer 360 and reload the JSON artifact from tmp_path."""
    artifacts_path = tmp_path / "compiled_artifacts.json"
    artifacts = compile_pipeline(
        CUSTOMER_360_SPEC,
        DEMO_MANIFEST,
        emit_lineage=False,
    )
    artifacts.to_json_file(artifacts_path)
    return CompiledArtifacts.from_json_file(artifacts_path)


def _host_minio_endpoint_for_client() -> str:
    """Return the MinIO endpoint in the host:port form expected by minio-py."""
    minio_url = ServiceEndpoint("minio").url
    parsed = urlsplit(minio_url)
    return parsed.netloc if parsed.scheme else minio_url


def _host_catalog_config(base_config: dict[str, Any]) -> dict[str, Any]:
    """Rewrite compiled catalog config to host-reachable Polaris and MinIO."""
    polaris_catalog_url = f"{ServiceEndpoint('polaris').url}/api/catalog"
    minio_url = ServiceEndpoint("minio").url
    minio_access_key, minio_secret_key = get_minio_credentials()
    polaris_client_id, polaris_client_secret = get_polaris_credentials(DEMO_MANIFEST)

    return {
        **base_config,
        "uri": polaris_catalog_url,
        "warehouse": get_polaris_warehouse(DEMO_MANIFEST),
        "credential": f"{polaris_client_id}:{polaris_client_secret}",  # pragma: allowlist secret
        "scope": get_polaris_scope(DEMO_MANIFEST),
        "oauth2_server_uri": get_polaris_oauth2_server_uri(
            DEMO_MANIFEST,
            catalog_endpoint=polaris_catalog_url,
        ),
        "s3_endpoint": minio_url,
        "s3_region": base_config.get("s3_region", "us-east-1"),
        "s3_path_style_access": True,
        "s3_access_key": minio_access_key,
        "s3_secret_key": minio_secret_key,  # pragma: allowlist secret
    }


def _isolated_ingestion_config(
    artifacts: CompiledArtifacts,
    *,
    namespace: str,
) -> DltIngestionConfig:
    """Build dlt config with Customer 360 sources targeting an isolated namespace."""
    ingestion_ref = artifacts.plugins.ingestion
    assert ingestion_ref is not None, "Customer 360 artifacts should include dlt ingestion"
    assert ingestion_ref.config is not None, "dlt ingestion config should be resolved"

    config = dict(ingestion_ref.config)
    config["catalog_config"] = _host_catalog_config(dict(config.get("catalog_config") or {}))
    config["sources"] = [
        {
            **dict(source),
            "destination_table": str(source["destination_table"]).replace(
                "bronze.",
                f"{namespace}.",
                1,
            ),
        }
        for source in config["sources"]
    ]
    return DltIngestionConfig.model_validate(config)


def _table_identifier(raw_identifier: Any) -> str:
    """Normalize PyIceberg table identifiers into namespace.table strings."""
    if isinstance(raw_identifier, tuple):
        return ".".join(str(part) for part in raw_identifier)
    return str(raw_identifier)


def _table_names(catalog: Any, namespace: str) -> set[str]:
    """List physical table names in an Iceberg namespace."""
    return {
        _table_identifier(identifier).rsplit(".", 1)[-1]
        for identifier in catalog.list_tables(namespace)
    }


def _purge_namespace(catalog: Any, namespace: str) -> None:
    """Purge all tables in a namespace and drop the namespace if it exists."""
    try:
        table_identifiers = list(catalog.list_tables(namespace))
    except Exception as exc:  # noqa: BLE001
        if exc.__class__.__name__ == "NoSuchNamespaceError":
            return
        raise

    for identifier in table_identifiers:
        fqn = _table_identifier(identifier)
        try:
            catalog.purge_table(fqn)
        except AttributeError:
            catalog.drop_table(fqn, purge_requested=True)
        except Exception as exc:  # noqa: BLE001
            if exc.__class__.__name__ != "NoSuchTableError":
                raise

    try:
        catalog.drop_namespace(namespace)
    except Exception as exc:  # noqa: BLE001
        if exc.__class__.__name__ != "NoSuchNamespaceError":
            raise


def _row_count(catalog: Any, table_identifier: str) -> int:
    """Return a PyIceberg row count using host-reachable MinIO table IO."""
    table = catalog.load_table(table_identifier)
    rewrite_table_io_for_host_access(table)
    return len(table.scan().to_arrow())


def _table_name(destination_table: str) -> str:
    """Extract the physical table name from a namespace-qualified table."""
    return destination_table.rsplit(".", 1)[-1]


def _ingest_sources(
    plugin: DltIngestionPlugin,
    ingestion_config: DltIngestionConfig,
) -> None:
    """Execute each Customer 360 source through the dlt ingestion plugin."""
    for source in ingestion_config.sources:
        source_config = source.model_dump(mode="python")
        pipeline_config = IngestionConfig(
            source_type=source.source_type,
            source_config=source.source_config,
            destination_table=source.destination_table,
            write_mode=source.write_mode,
            schema_contract=source.schema_contract,
        )
        dlt_source = build_dlt_source(source_config, project_dir=CUSTOMER_360_DIR)
        pipeline = plugin.create_pipeline(pipeline_config)

        result = plugin.run(
            pipeline,
            source=dlt_source,
            write_disposition=source.write_mode,
            table_name=_table_name(source.destination_table),
            schema_contract=source.schema_contract,
            cursor_field=source.cursor_field,
            primary_key=source.primary_key,
        )

        assert result.success, (
            f"dlt ingestion failed for {source.name} -> {source.destination_table}: {result.errors}"
        )


class TestCustomer360DltIngestion(IntegrationTestBase):
    """Customer 360 raw ingestion E2E using Polaris and MinIO."""

    required_services = ["polaris", "minio"]

    def test_customer360_dlt_ingestion_creates_raw_iceberg_tables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        e2e_namespace: str,
        polaris_with_write_grants: Any,
    ) -> None:
        """Run Customer 360 dlt ingestion and validate raw Iceberg outputs."""
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        namespace = _isolated_bronze_namespace(e2e_namespace)
        artifacts = _load_customer360_artifacts(tmp_path)
        ingestion_config = _isolated_ingestion_config(artifacts, namespace=namespace)
        bucket = str(ingestion_config.catalog_config["bucket"])

        minio_access_key, minio_secret_key = get_minio_credentials()
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", minio_access_key)
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", minio_secret_key)
        monkeypatch.setenv("AWS_REGION", str(ingestion_config.catalog_config["s3_region"]))

        with minio_client_context(MinIOConfig(endpoint=_host_minio_endpoint_for_client())) as minio:
            ensure_bucket(minio, bucket)

        _purge_namespace(polaris_with_write_grants, namespace)
        polaris_with_write_grants.create_namespace(namespace)

        plugin = DltIngestionPlugin()
        plugin.configure(ingestion_config)
        plugin.startup()
        try:
            _ingest_sources(plugin, ingestion_config)

            available_tables = _table_names(polaris_with_write_grants, namespace)
            for logical_table in LOGICAL_RAW_TABLES:
                table_name = _table_name(logical_table)
                assert table_name in available_tables, (
                    f"Expected Customer 360 raw table {namespace}.{table_name} "
                    f"for logical table {logical_table}; available tables: {available_tables}"
                )

                count = _row_count(polaris_with_write_grants, f"{namespace}.{table_name}")
                assert count > 0, (
                    f"Expected {namespace}.{table_name} for logical table "
                    f"{logical_table} to contain rows"
                )
        finally:
            plugin.shutdown()
            _purge_namespace(polaris_with_write_grants, namespace)
