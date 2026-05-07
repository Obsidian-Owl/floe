"""dlt filesystem format matrix E2E against Polaris and MinIO."""

from __future__ import annotations

import csv
import io
import json
import uuid
from pathlib import Path
from typing import Any, NamedTuple, cast
from urllib.parse import urlsplit

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from floe_core.plugins.ingestion import IngestionConfig, IngestionResult
from floe_ingestion_dlt.config import DltIngestionConfig, IngestionSourceConfig
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
    pytest.mark.platform_blackbox,
    pytest.mark.requirement("4F-E2E-DLT-FORMAT-MATRIX"),
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_MANIFEST = PROJECT_ROOT / "demo" / "manifest.yaml"


class FormatCase(NamedTuple):
    """Expected data shape for one filesystem source format."""

    file_format: str
    filename: str
    expected_rows: int
    representative_row: dict[str, Any]


FORMAT_CASES = (
    FormatCase(
        file_format="csv",
        filename="customers.csv",
        expected_rows=2,
        representative_row={"customer_id": "C001", "name": "Ada Lovelace", "segment": "smb"},
    ),
    FormatCase(
        file_format="jsonl",
        filename="events.jsonl",
        expected_rows=2,
        representative_row={"event_id": "E001", "user_id": "U001", "campaign": "spring"},
    ),
    FormatCase(
        file_format="parquet",
        filename="orders.parquet",
        expected_rows=2,
        representative_row={"order_id": "O001", "customer_id": "C001", "amount": 42.5},
    ),
)


def _safe_namespace(e2e_namespace: str, suffix: str) -> str:
    """Return a PyIceberg-safe isolated namespace for one test case."""
    safe_session = e2e_namespace.replace("-", "_")
    return f"dlt_matrix_{safe_session}_{suffix}_{uuid.uuid4().hex[:8]}"


def _host_minio_endpoint_for_client() -> str:
    """Return the MinIO endpoint in the host:port form expected by minio-py."""
    minio_url = ServiceEndpoint("minio").url
    parsed = urlsplit(minio_url)
    return parsed.netloc if parsed.scheme else minio_url


def _catalog_config() -> dict[str, Any]:
    """Build host-reachable Polaris and MinIO catalog config for dlt."""
    polaris_catalog_url = f"{ServiceEndpoint('polaris').url}/api/catalog"
    minio_url = ServiceEndpoint("minio").url
    polaris_client_id, polaris_client_secret = get_polaris_credentials(DEMO_MANIFEST)

    return {
        "uri": polaris_catalog_url,
        "warehouse": get_polaris_warehouse(DEMO_MANIFEST),
        "credential": f"{polaris_client_id}:{polaris_client_secret}",  # pragma: allowlist secret
        "scope": get_polaris_scope(DEMO_MANIFEST),
        "oauth2_server_uri": get_polaris_oauth2_server_uri(
            DEMO_MANIFEST,
            catalog_endpoint=polaris_catalog_url,
        ),
        "bucket": "floe-iceberg",
        "s3_endpoint": minio_url,
        "s3_region": "us-east-1",
        "s3_path_style_access": True,
    }


def _runtime_binding(catalog_config: dict[str, Any]) -> dict[str, Any]:
    """Build binding-shaped runtime config from legacy E2E catalog config."""
    return {
        "plugin_name": "dlt",
        "destination": "filesystem",
        "table_format": "iceberg",
        "destination_filesystem": DltIngestionPlugin().get_destination_config(catalog_config),
        "source_filesystem": {
            "endpoint_url": catalog_config["s3_endpoint"],
            "region_name": catalog_config["s3_region"],
            "s3_url_style": "path" if catalog_config["s3_path_style_access"] else "virtual",
        },
        "iceberg_catalog_env": DltIngestionPlugin()._iceberg_environment(catalog_config),
        "env_refs": {
            "accessKeyId": "AWS_ACCESS_KEY_ID",
            "secretAccessKey": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
        },
    }


def _configure_s3_environment(
    monkeypatch: pytest.MonkeyPatch,
    catalog_config: dict[str, Any],
) -> None:
    """Expose MinIO credentials to dlt through the runtime AWS environment."""
    access_key, secret_key = get_minio_credentials()
    endpoint = str(catalog_config["s3_endpoint"])
    region = str(catalog_config["s3_region"])

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", access_key)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", secret_key)
    monkeypatch.setenv("AWS_REGION", region)
    monkeypatch.setenv("AWS_ENDPOINT_URL", endpoint)


def _put_object(minio: Any, *, bucket: str, object_name: str, payload: bytes) -> None:
    """Upload one object to MinIO from in-memory bytes."""
    minio.put_object(
        bucket,
        object_name,
        io.BytesIO(payload),
        length=len(payload),
        content_type="application/octet-stream",
    )


def _csv_payload(rows: list[dict[str, Any]]) -> bytes:
    """Serialize rows to a UTF-8 CSV payload with a header."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _jsonl_payload(rows: list[dict[str, Any]]) -> bytes:
    """Serialize rows to newline-delimited JSON bytes."""
    return ("\n".join(json.dumps(row) for row in rows) + "\n").encode("utf-8")


def _parquet_payload(rows: list[dict[str, Any]]) -> bytes:
    """Serialize rows to Parquet bytes using pyarrow."""
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist(rows), sink)
    return bytes(sink.getvalue().to_pybytes())


def _seed_payload(case: FormatCase) -> bytes:
    """Return the seed payload for one happy-path format case."""
    if case.file_format == "csv":
        return _csv_payload(
            [
                {"customer_id": "C001", "name": "Ada Lovelace", "segment": "smb"},
                {"customer_id": "C002", "name": "Grace Hopper", "segment": "enterprise"},
            ]
        )
    if case.file_format == "jsonl":
        return _jsonl_payload(
            [
                {"event_id": "E001", "user_id": "U001", "campaign": "spring"},
                {"event_id": "E002", "user_id": "U002"},
            ]
        )
    if case.file_format == "parquet":
        return _parquet_payload(
            [
                {"order_id": "O001", "customer_id": "C001", "amount": 42.5},
                {"order_id": "O002", "customer_id": "C002", "amount": 84.0},
            ]
        )
    raise AssertionError(f"Unexpected format case {case.file_format!r}")


def _source_config(
    *,
    name: str,
    file_format: str,
    bucket: str,
    prefix: str,
    filename: str,
    destination_table: str,
    write_mode: str = "replace",
    schema_contract: str = "evolve",
) -> IngestionSourceConfig:
    """Build a compiled-style filesystem ingestion source config."""
    return IngestionSourceConfig(
        name=name,
        source_type="filesystem",
        source_config={
            "format": file_format,
            "path": f"s3://{bucket}/{prefix}/",
            "include_glob": filename,
        },
        destination_table=destination_table,
        write_mode=write_mode,
        schema_contract=schema_contract,
    )


def _configure_plugin(
    source: IngestionSourceConfig,
    catalog_config: dict[str, Any],
) -> DltIngestionPlugin:
    """Configure and start a dlt ingestion plugin for one source."""
    plugin = DltIngestionPlugin()
    plugin.configure(DltIngestionConfig(sources=[source], catalog_config=catalog_config))
    plugin.startup()
    return plugin


def _run_source(
    plugin: DltIngestionPlugin,
    source: IngestionSourceConfig,
    *,
    runtime_binding: dict[str, Any],
) -> IngestionResult:
    """Run one filesystem source through Dagster source construction and dlt."""
    source_dict = source.model_dump(mode="python")
    pipeline = plugin.create_pipeline(
        IngestionConfig(
            source_type=source.source_type,
            source_config=source.source_config,
            destination_table=source.destination_table,
            write_mode=source.write_mode,
            schema_contract=source.schema_contract,
            runtime_binding=runtime_binding,
        )
    )
    dlt_source = build_dlt_source(
        source_dict,
        project_dir=PROJECT_ROOT,
        filesystem_config=runtime_binding["source_filesystem"],
    )
    return plugin.run(
        pipeline,
        source=dlt_source,
        write_disposition=source.write_mode,
        table_name=_table_name(source.destination_table),
        schema_contract=source.schema_contract,
        source_name=source.name,
        source_path=str(source.source_config["path"]),
    )


def _table_name(destination_table: str) -> str:
    """Extract the physical table name from a namespace-qualified table."""
    return destination_table.rsplit(".", 1)[-1]


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


def _table_rows(catalog: Any, table_identifier: str) -> list[dict[str, Any]]:
    """Return PyIceberg rows using host-reachable MinIO table IO."""
    table = catalog.load_table(table_identifier)
    rewrite_table_io_for_host_access(table)
    return cast("list[dict[str, Any]]", table.scan().to_arrow().to_pylist())


def _table_column_names(catalog: Any, table_identifier: str) -> set[str]:
    """Return column names from the committed Iceberg table schema."""
    table = catalog.load_table(table_identifier)
    schema = table.schema()
    return {str(field.name) for field in schema.fields}


def _assert_expected_columns(
    catalog: Any,
    table_identifier: str,
    expected_columns: set[str],
) -> None:
    """Assert representative source columns exist in the Iceberg schema."""
    column_names = _table_column_names(catalog, table_identifier)
    assert expected_columns.issubset(column_names), (
        f"Expected {table_identifier} schema to include {sorted(expected_columns)}; "
        f"actual columns: {sorted(column_names)}"
    )


def _assert_representative_row(
    rows: list[dict[str, Any]],
    representative_row: dict[str, Any],
) -> None:
    """Assert a representative row subset exists in the loaded table."""
    assert any(
        all(row.get(column) == value for column, value in representative_row.items())
        for row in rows
    ), f"Expected row subset {representative_row}; sample rows: {rows[:3]}"


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


def _cleanup_prefix(minio: Any, *, bucket: str, prefix: str) -> int:
    """Remove leftover MinIO objects under an isolated prefix."""
    if not minio.bucket_exists(bucket):
        return 0

    from minio.deleteobjects import DeleteObject

    objects = list(minio.list_objects(bucket, prefix=prefix, recursive=True))
    delete_objects = [DeleteObject(obj.object_name) for obj in objects]
    if not delete_objects:
        return 0

    errors = list(minio.remove_objects(bucket, delete_objects))
    if errors:
        pytest.fail(f"Failed to delete MinIO objects for prefix {prefix}: {errors}")
    return len(delete_objects)


def _shutdown_plugin(plugin: DltIngestionPlugin | None) -> Exception | None:
    """Shutdown a plugin, returning the error so cleanup can still run."""
    if plugin is None:
        return None
    try:
        plugin.shutdown()
    except Exception as exc:  # noqa: BLE001
        return exc
    return None


def _assert_no_table_or_rows(catalog: Any, namespace: str, table_identifier: str) -> None:
    """Assert a failed ingestion did not commit table rows."""
    table_name = _table_name(table_identifier)
    if table_name not in _table_names(catalog, namespace):
        return
    rows = _table_rows(catalog, table_identifier)
    assert rows == [], f"Expected failed ingestion not to commit rows to {table_identifier}"


def _assert_failed_with(result: IngestionResult, *expected_fragments: str) -> None:
    """Assert an ingestion result failed with all expected error fragments."""
    assert not result.success, "Expected ingestion to fail"
    error_text = "\n".join(result.errors or [])
    for fragment in expected_fragments:
        assert fragment in error_text, f"Expected {fragment!r} in ingestion errors: {error_text}"


class TestDltIngestionFormatMatrix(IntegrationTestBase):
    """Filesystem format matrix E2E using Polaris and MinIO."""

    required_services = ["polaris", "minio"]

    @pytest.mark.parametrize(
        ("case"),
        FORMAT_CASES,
        ids=[case.file_format for case in FORMAT_CASES],
    )
    def test_filesystem_format_happy_path_matrix(
        self,
        case: FormatCase,
        monkeypatch: pytest.MonkeyPatch,
        e2e_namespace: str,
        polaris_with_write_grants: Any,
    ) -> None:
        """Ingest CSV, JSONL, and Parquet landed files into Iceberg tables."""
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        catalog_config = _catalog_config()
        runtime_binding = _runtime_binding(catalog_config)
        _configure_s3_environment(monkeypatch, catalog_config)
        bucket = str(catalog_config["bucket"])
        namespace = _safe_namespace(e2e_namespace, case.file_format)
        prefix = f"{namespace}/landing/{case.file_format}"
        table_identifier = f"{namespace}.{case.file_format}_rows"
        source = _source_config(
            name=f"{case.file_format}_source",
            file_format=case.file_format,
            bucket=bucket,
            prefix=prefix,
            filename=case.filename,
            destination_table=table_identifier,
        )

        with minio_client_context(MinIOConfig(endpoint=_host_minio_endpoint_for_client())) as minio:
            ensure_bucket(minio, bucket)
            plugin: DltIngestionPlugin | None = None
            try:
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                _purge_namespace(polaris_with_write_grants, namespace)
                polaris_with_write_grants.create_namespace(namespace)
                _put_object(
                    minio,
                    bucket=bucket,
                    object_name=f"{prefix}/{case.filename}",
                    payload=_seed_payload(case),
                )

                plugin = _configure_plugin(source, catalog_config)
                result = _run_source(plugin, source, runtime_binding=runtime_binding)
                assert result.success, result.errors

                assert _table_name(table_identifier) in _table_names(
                    polaris_with_write_grants,
                    namespace,
                )
                rows = _table_rows(polaris_with_write_grants, table_identifier)
                assert len(rows) == case.expected_rows
                _assert_expected_columns(
                    polaris_with_write_grants,
                    table_identifier,
                    set(case.representative_row),
                )
                _assert_representative_row(rows, case.representative_row)
                if case.file_format == "jsonl":
                    assert any(row.get("campaign") is None for row in rows)
            finally:
                shutdown_error = _shutdown_plugin(plugin)
                _purge_namespace(polaris_with_write_grants, namespace)
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                if shutdown_error is not None:
                    raise shutdown_error

    def test_missing_object_path_returns_failed_ingestion_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
        e2e_namespace: str,
        polaris_with_write_grants: Any,
    ) -> None:
        """A missing landed object fails with a source/path-specific result."""
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        catalog_config = _catalog_config()
        runtime_binding = _runtime_binding(catalog_config)
        _configure_s3_environment(monkeypatch, catalog_config)
        bucket = str(catalog_config["bucket"])
        namespace = _safe_namespace(e2e_namespace, "missing")
        prefix = f"{namespace}/landing/missing"
        table_identifier = f"{namespace}.missing_rows"
        source = _source_config(
            name="missing_object_source",
            file_format="csv",
            bucket=bucket,
            prefix=prefix,
            filename="does-not-exist.csv",
            destination_table=table_identifier,
        )

        with minio_client_context(MinIOConfig(endpoint=_host_minio_endpoint_for_client())) as minio:
            ensure_bucket(minio, bucket)
            plugin: DltIngestionPlugin | None = None
            try:
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                _purge_namespace(polaris_with_write_grants, namespace)
                polaris_with_write_grants.create_namespace(namespace)

                plugin = _configure_plugin(source, catalog_config)
                result = _run_source(plugin, source, runtime_binding=runtime_binding)

                _assert_failed_with(result, "missing_object_source", f"s3://{bucket}/{prefix}/")
                _assert_no_table_or_rows(polaris_with_write_grants, namespace, table_identifier)
            finally:
                shutdown_error = _shutdown_plugin(plugin)
                _purge_namespace(polaris_with_write_grants, namespace)
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                if shutdown_error is not None:
                    raise shutdown_error

    def test_malformed_jsonl_fails_with_source_name_and_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        e2e_namespace: str,
        polaris_with_write_grants: Any,
    ) -> None:
        """Malformed JSONL reports the source name and landed object path."""
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        catalog_config = _catalog_config()
        runtime_binding = _runtime_binding(catalog_config)
        _configure_s3_environment(monkeypatch, catalog_config)
        bucket = str(catalog_config["bucket"])
        namespace = _safe_namespace(e2e_namespace, "bad_jsonl")
        prefix = f"{namespace}/landing/bad_jsonl"
        filename = "bad_events.jsonl"
        table_identifier = f"{namespace}.bad_jsonl_source"
        source = _source_config(
            name="bad_jsonl_source",
            file_format="jsonl",
            bucket=bucket,
            prefix=prefix,
            filename=filename,
            destination_table=table_identifier,
        )

        with minio_client_context(MinIOConfig(endpoint=_host_minio_endpoint_for_client())) as minio:
            ensure_bucket(minio, bucket)
            plugin: DltIngestionPlugin | None = None
            try:
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                _purge_namespace(polaris_with_write_grants, namespace)
                polaris_with_write_grants.create_namespace(namespace)
                _put_object(
                    minio,
                    bucket=bucket,
                    object_name=f"{prefix}/{filename}",
                    payload=b'{"event_id": "E001"}\n{"event_id": ',
                )

                plugin = _configure_plugin(source, catalog_config)
                result = _run_source(plugin, source, runtime_binding=runtime_binding)

                _assert_failed_with(
                    result,
                    "bad_jsonl_source",
                    f"s3://{bucket}/{prefix}/",
                )
                _assert_no_table_or_rows(polaris_with_write_grants, namespace, table_identifier)
            finally:
                shutdown_error = _shutdown_plugin(plugin)
                _purge_namespace(polaris_with_write_grants, namespace)
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                if shutdown_error is not None:
                    raise shutdown_error

    def test_schema_freeze_rejects_added_column_on_second_load(
        self,
        monkeypatch: pytest.MonkeyPatch,
        e2e_namespace: str,
        polaris_with_write_grants: Any,
    ) -> None:
        """Freeze mode rejects a new column after the initial table schema exists."""
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        catalog_config = _catalog_config()
        runtime_binding = _runtime_binding(catalog_config)
        _configure_s3_environment(monkeypatch, catalog_config)
        bucket = str(catalog_config["bucket"])
        namespace = _safe_namespace(e2e_namespace, "freeze")
        prefix = f"{namespace}/landing/freeze"
        table_identifier = f"{namespace}.freeze_rows"
        source = _source_config(
            name="freeze_source",
            file_format="csv",
            bucket=bucket,
            prefix=prefix,
            filename="*.csv",
            destination_table=table_identifier,
            write_mode="append",
            schema_contract="freeze",
        )

        with minio_client_context(MinIOConfig(endpoint=_host_minio_endpoint_for_client())) as minio:
            ensure_bucket(minio, bucket)
            plugin: DltIngestionPlugin | None = None
            try:
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                _purge_namespace(polaris_with_write_grants, namespace)
                polaris_with_write_grants.create_namespace(namespace)
                _put_object(
                    minio,
                    bucket=bucket,
                    object_name=f"{prefix}/first.csv",
                    payload=_csv_payload(
                        [
                            {"id": 1, "name": "one"},
                            {"id": 2, "name": "two"},
                        ]
                    ),
                )

                plugin = _configure_plugin(source, catalog_config)
                first_result = _run_source(plugin, source, runtime_binding=runtime_binding)
                assert first_result.success, first_result.errors

                _put_object(
                    minio,
                    bucket=bucket,
                    object_name=f"{prefix}/second.csv",
                    payload=_csv_payload(
                        [
                            {"id": 3, "name": "three", "new_column": "unexpected"},
                        ]
                    ),
                )
                second_result = _run_source(plugin, source, runtime_binding=runtime_binding)

                _assert_failed_with(second_result, "schema", "contract", "new_column")
            finally:
                shutdown_error = _shutdown_plugin(plugin)
                _purge_namespace(polaris_with_write_grants, namespace)
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                if shutdown_error is not None:
                    raise shutdown_error

    def test_unsupported_format_fails_before_empty_table_is_created(
        self,
        monkeypatch: pytest.MonkeyPatch,
        e2e_namespace: str,
        polaris_with_write_grants: Any,
    ) -> None:
        """Unsupported formats fail during source construction, before table creation."""
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        catalog_config = _catalog_config()
        runtime_binding = _runtime_binding(catalog_config)
        _configure_s3_environment(monkeypatch, catalog_config)
        bucket = str(catalog_config["bucket"])
        namespace = _safe_namespace(e2e_namespace, "unsupported")
        prefix = f"{namespace}/landing/unsupported"
        table_identifier = f"{namespace}.unsupported_rows"
        source_dict = {
            "name": "unsupported_format_source",
            "source_type": "filesystem",
            "source_config": {
                "format": "xml",
                "path": f"s3://{bucket}/{prefix}/",
                "include_glob": "rows.xml",
            },
            "destination_table": table_identifier,
            "write_mode": "replace",
            "schema_contract": "evolve",
        }

        with minio_client_context(MinIOConfig(endpoint=_host_minio_endpoint_for_client())) as minio:
            ensure_bucket(minio, bucket)
            try:
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
                _purge_namespace(polaris_with_write_grants, namespace)
                polaris_with_write_grants.create_namespace(namespace)
                _put_object(
                    minio,
                    bucket=bucket,
                    object_name=f"{prefix}/rows.xml",
                    payload=b"<rows><row id='1'/></rows>",
                )

                with pytest.raises(ValueError, match="Unsupported filesystem format.*xml"):
                    build_dlt_source(
                        source_dict,
                        project_dir=PROJECT_ROOT,
                        filesystem_config=runtime_binding["source_filesystem"],
                    )

                assert _table_names(polaris_with_write_grants, namespace) == set()
            finally:
                _purge_namespace(polaris_with_write_grants, namespace)
                _cleanup_prefix(minio, bucket=bucket, prefix=namespace)
