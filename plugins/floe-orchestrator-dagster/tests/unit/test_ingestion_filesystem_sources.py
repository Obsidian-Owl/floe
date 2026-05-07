"""Unit tests for JSON-safe dlt filesystem source construction."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


class FakeDltResource:
    """Small dlt-like resource double that records composition."""

    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.kwargs = kwargs
        self.parent: FakeDltResource | None = None
        self.table_name: str | None = None

    def __or__(self, other: FakeDltResource) -> FakeDltResource:
        other.parent = self
        return other

    def with_name(self, name: str) -> FakeDltResource:
        self.name = name
        return self

    def apply_hints(self, *, table_name: str) -> FakeDltResource:
        self.table_name = table_name
        return self


class FakeFilesystemModule(ModuleType):
    """Typed fake module with call recording for dlt filesystem APIs."""

    calls: list[tuple[str, dict[str, Any]]]


def _source_config(
    *,
    format_: str = "csv",
    path: str = "./data/customers.csv",
    source_type: str = "filesystem",
    destination_table: str = "bronze.raw_customers",
    extra_source_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nested_config: dict[str, Any] = {"format": format_, "path": path}
    if extra_source_config:
        nested_config.update(extra_source_config)
    return {
        "name": "raw-customers",
        "source_type": source_type,
        "source_config": nested_config,
        "destination_table": destination_table,
        "write_mode": "replace",
        "schema_contract": "evolve",
    }


def _source_config_with_option_key(key: str) -> dict[str, Any]:
    return _source_config(extra_source_config={key: "placeholder"})


def _source_config_with_reader_option_key(key: str) -> dict[str, Any]:
    return _source_config(extra_source_config={"reader_options": {key: "placeholder"}})


@pytest.fixture
def fake_filesystem_module(monkeypatch: pytest.MonkeyPatch) -> FakeFilesystemModule:
    """Install a fake dlt filesystem module and return it for assertions."""
    calls: list[tuple[str, dict[str, Any]]] = []
    module = FakeFilesystemModule("dlt.sources.filesystem")
    module.calls = calls

    def filesystem(**kwargs: Any) -> FakeDltResource:
        calls.append(("filesystem", kwargs))
        return FakeDltResource("filesystem", **kwargs)

    def _reader(name: str) -> Any:
        def reader(**kwargs: Any) -> FakeDltResource:
            calls.append((name, kwargs))
            return FakeDltResource(name, **kwargs)

        return reader

    module.filesystem = filesystem  # type: ignore[attr-defined]
    module.read_csv = _reader("read_csv")  # type: ignore[attr-defined]
    module.read_jsonl = _reader("read_jsonl")  # type: ignore[attr-defined]
    module.read_parquet = _reader("read_parquet")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "dlt.sources.filesystem", module)
    return module


def test_importing_ingestion_module_does_not_import_dlt_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter module should be importable without importing dlt."""
    monkeypatch.delitem(sys.modules, "dlt.sources.filesystem", raising=False)
    sys.modules.pop("floe_orchestrator_dagster.ingestion", None)

    importlib.import_module("floe_orchestrator_dagster.ingestion")

    assert "dlt.sources.filesystem" not in sys.modules


@pytest.mark.parametrize(
    ("format_", "reader_name"),
    [
        ("csv", "read_csv"),
        ("jsonl", "read_jsonl"),
        ("parquet", "read_parquet"),
    ],
)
def test_build_filesystem_source_builds_runnable_dlt_resource_for_supported_formats(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
    format_: str,
    reader_name: str,
) -> None:
    """Supported file formats compose filesystem listing with the matching reader."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    source = build_filesystem_source(
        _source_config(
            format_=format_,
            path="./data/",
            extra_source_config={"file_glob": "*.data", "reader_options": {"chunksize": 7}},
        ),
        project_dir=tmp_path,
    )

    assert isinstance(source, FakeDltResource)
    assert source.name == "raw_customers"
    assert source.table_name == "raw_customers"
    assert source.parent is not None
    assert source.parent.kwargs == {
        "bucket_url": str(tmp_path / "data"),
        "file_glob": "*.data",
    }
    assert fake_filesystem_module.calls == [
        ("filesystem", source.parent.kwargs),
        (reader_name, {"chunksize": 7}),
    ]


def test_build_filesystem_source_normalizes_local_paths_relative_to_project_dir(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
) -> None:
    """Relative local source paths are resolved below the supplied project dir."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    source = build_filesystem_source(
        _source_config(path="data/customers.csv"),
        project_dir=tmp_path,
    )

    assert source.parent is not None
    assert source.parent.kwargs["bucket_url"] == str(tmp_path / "data")
    assert source.parent.kwargs["file_glob"] == "customers.csv"
    assert fake_filesystem_module.calls[0][0] == "filesystem"


def test_build_filesystem_source_uses_directory_path_as_bucket_url(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
) -> None:
    """Directory local source paths keep the directory as bucket_url."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    source = build_filesystem_source(
        _source_config(path="data/", extra_source_config={"file_glob": "*.csv"}),
        project_dir=tmp_path,
    )

    assert source.parent is not None
    assert source.parent.kwargs == {
        "bucket_url": str(tmp_path / "data"),
        "file_glob": "*.csv",
    }


def test_build_filesystem_source_rejects_file_path_with_explicit_glob(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
) -> None:
    """A file path plus explicit glob is ambiguous and rejected before dlt import."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    with pytest.raises(ValueError, match="file path.*file_glob.*raw-customers"):
        build_filesystem_source(
            _source_config(path="data/customers.csv", extra_source_config={"file_glob": "*.csv"}),
            project_dir=tmp_path,
        )

    assert fake_filesystem_module.calls == []


def test_build_filesystem_source_leaves_object_store_paths_unchanged_without_config(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
) -> None:
    """Object-store URIs remain unchanged when no platform filesystem config is present."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    source = build_filesystem_source(
        _source_config(path="s3://raw/customers/*.csv"),
        project_dir=tmp_path,
    )

    assert source.parent is not None
    assert source.parent.kwargs["bucket_url"] == "s3://raw/customers/*.csv"
    assert fake_filesystem_module.calls[0][0] == "filesystem"


def test_build_filesystem_source_wires_s3_config_from_platform_and_env(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3/MinIO filesystem reads receive endpoint config without product-owned secrets."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "env-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "env-secret")  # pragma: allowlist secret

    source = build_filesystem_source(
        _source_config(path="s3://raw/customers/", extra_source_config={"file_glob": "*.csv"}),
        project_dir=tmp_path,
        filesystem_config={
            "s3_endpoint": "http://minio:9000",
            "s3_region": "us-east-1",
            "s3_path_style_access": True,
        },
    )

    assert source.parent is not None
    assert source.parent.kwargs == {
        "bucket_url": "s3://raw/customers/",
        "file_glob": "*.csv",
        "credentials": {
            "aws_access_key_id": "env-access",
            "aws_secret_access_key": "env-secret",  # pragma: allowlist secret
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
            "s3_url_style": "path",
        },
    }
    assert fake_filesystem_module.calls[0] == ("filesystem", source.parent.kwargs)


def test_build_filesystem_source_uses_binding_source_filesystem_config(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compiled dlt source filesystem binding config is accepted by the adapter."""
    from floe_orchestrator_dagster.ingestion import build_dlt_source

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "env-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "env-secret")  # pragma: allowlist secret

    source = build_dlt_source(
        _source_config(path="s3://raw/customers/", extra_source_config={"file_glob": "*.csv"}),
        project_dir=tmp_path,
        filesystem_config={
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
            "s3_url_style": "path",
        },
    )

    assert source.parent is not None
    assert source.parent.kwargs == {
        "bucket_url": "s3://raw/customers/",
        "file_glob": "*.csv",
        "credentials": {
            "aws_access_key_id": "env-access",
            "aws_secret_access_key": "env-secret",  # pragma: allowlist secret
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
            "s3_url_style": "path",
        },
    }
    assert fake_filesystem_module.calls[0] == ("filesystem", source.parent.kwargs)


def test_build_filesystem_source_respects_binding_virtual_url_style(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit non-path URL style must not be overridden by endpoint presence."""
    from floe_orchestrator_dagster.ingestion import build_dlt_source

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "env-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "env-secret")  # pragma: allowlist secret

    source = build_dlt_source(
        _source_config(path="s3://raw/customers/", extra_source_config={"file_glob": "*.csv"}),
        project_dir=tmp_path,
        filesystem_config={
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
            "s3_url_style": "virtual",
        },
    )

    assert source.parent is not None
    assert source.parent.kwargs == {
        "bucket_url": "s3://raw/customers/",
        "file_glob": "*.csv",
        "credentials": {
            "aws_access_key_id": "env-access",
            "aws_secret_access_key": "env-secret",  # pragma: allowlist secret
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
        },
    }
    assert fake_filesystem_module.calls[0] == ("filesystem", source.parent.kwargs)


@pytest.mark.parametrize("flag_name", ["s3_path_style_access", "path_style_access"])
@pytest.mark.parametrize("flag_value", ["false", "no", "0", "off"])
def test_build_filesystem_source_respects_false_path_style_strings(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
    monkeypatch: pytest.MonkeyPatch,
    flag_name: str,
    flag_value: str,
) -> None:
    """Explicit false path-style strings must suppress endpoint path-style default."""
    from floe_orchestrator_dagster.ingestion import build_dlt_source

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "env-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "env-secret")  # pragma: allowlist secret

    source = build_dlt_source(
        _source_config(path="s3://raw/customers/", extra_source_config={"file_glob": "*.csv"}),
        project_dir=tmp_path,
        filesystem_config={
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
            flag_name: flag_value,
        },
    )

    assert source.parent is not None
    assert source.parent.kwargs == {
        "bucket_url": "s3://raw/customers/",
        "file_glob": "*.csv",
        "credentials": {
            "aws_access_key_id": "env-access",
            "aws_secret_access_key": "env-secret",  # pragma: allowlist secret
            "endpoint_url": "http://minio:9000",
            "region_name": "us-east-1",
        },
    }
    assert fake_filesystem_module.calls[0] == ("filesystem", source.parent.kwargs)


def test_build_filesystem_source_reads_real_local_csv_file(tmp_path: Path) -> None:
    """Real dlt construction reads rows when product path points at a local file."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "customers.csv").write_text("id,name\n1,Ada\n2,Lin\n", encoding="utf-8")

    source = build_filesystem_source(
        _source_config(path="data/customers.csv"),
        project_dir=tmp_path,
    )

    assert list(source) == [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Lin"}]


def test_build_filesystem_source_rejects_unsupported_source_type_before_dlt_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported source_type errors include the source name and avoid dlt import."""
    monkeypatch.delitem(sys.modules, "dlt.sources.filesystem", raising=False)
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    with pytest.raises(ValueError, match="sql_database.*raw-customers"):
        build_filesystem_source(
            _source_config(source_type="sql_database"),
            project_dir=tmp_path,
        )

    assert "dlt.sources.filesystem" not in sys.modules


def test_build_filesystem_source_rejects_unsupported_format_with_source_name(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
) -> None:
    """Only design-approved file formats are supported."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    with pytest.raises(ValueError, match="xml.*raw-customers"):
        build_filesystem_source(
            _source_config(format_="xml"),
            project_dir=tmp_path,
        )

    assert fake_filesystem_module.calls == []


@pytest.mark.parametrize(
    ("config", "error_match"),
    [
        (_source_config(path=""), "path.*raw-customers"),
        (
            {
                "name": "raw-customers",
                "source_type": "filesystem",
                "source_config": {"format": "csv"},
                "destination_table": "bronze.raw_customers",
            },
            "path.*raw-customers",
        ),
        (
            {
                "name": "raw-customers",
                "source_type": "filesystem",
                "source_config": {"path": "data/customers.csv"},
                "destination_table": "bronze.raw_customers",
            },
            "format.*raw-customers",
        ),
        (
            {
                "name": "raw-customers",
                "source_type": "filesystem",
                "source_config": [],
                "destination_table": "bronze.raw_customers",
            },
            "source_config.*raw-customers",
        ),
        (_source_config(destination_table="bronze.raw.customers"), "destination_table"),
        (_source_config(destination_table="bronze."), "destination_table"),
        (_source_config(destination_table="bronze/raw_customers"), "destination_table"),
        (_source_config(path="../outside.csv"), "escapes project_dir.*raw-customers"),
        (_source_config(path="data/../../outside.csv"), "escapes project_dir.*raw-customers"),
        (_source_config(path="/var/data/customers.csv"), "absolute.*raw-customers"),
        (
            _source_config_with_option_key("api" + "_key"),
            "api.*key.*raw-customers",
        ),
        (
            _source_config_with_option_key("connection" + "String"),
            "connectionString.*raw-customers",
        ),
        (
            _source_config_with_option_key("access" + "Key"),
            "accessKey.*raw-customers",
        ),
        (
            _source_config_with_option_key("secret" + "AccessKey"),
            "secretAccessKey.*raw-customers",
        ),
        (
            _source_config_with_reader_option_key("api" + "Key"),
            "apiKey.*raw-customers",
        ),
        (
            _source_config_with_reader_option_key("connection" + "_string"),
            "connection.*string.*raw-customers",
        ),
        (_source_config(extra_source_config={"host": "localhost"}), "host.*raw-customers"),
        (_source_config(extra_source_config={"unknown": "value"}), "unknown.*raw-customers"),
        (
            _source_config(format_="jsonl", extra_source_config={"reader_options": {"sep": ","}}),
            "sep.*jsonl.*raw-customers",
        ),
        (
            _source_config(
                format_="parquet",
                extra_source_config={"reader_options": {"encoding": "utf-8"}},
            ),
            "encoding.*parquet.*raw-customers",
        ),
    ],
)
def test_build_filesystem_source_rejects_unsafe_config_before_dlt_runs(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
    config: dict[str, Any],
    error_match: str,
) -> None:
    """Validation catches non-portable config before constructing dlt resources."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    with pytest.raises(ValueError, match=error_match):
        build_filesystem_source(config, project_dir=tmp_path)

    assert fake_filesystem_module.calls == []


def test_build_dlt_source_dispatches_filesystem_sources(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
) -> None:
    """The public dispatcher routes filesystem configs to the filesystem adapter."""
    from floe_orchestrator_dagster.ingestion import build_dlt_source

    source = build_dlt_source(_source_config(), project_dir=tmp_path)

    assert isinstance(source, FakeDltResource)
    assert fake_filesystem_module.calls[0][0] == "filesystem"


def test_build_dlt_source_rejects_other_source_types(tmp_path: Path) -> None:
    """Non-filesystem sources remain intentionally unsupported."""
    from floe_orchestrator_dagster.ingestion import build_dlt_source

    with pytest.raises(ValueError, match="rest_api.*raw-customers"):
        build_dlt_source(
            _source_config(source_type="rest_api"),
            project_dir=tmp_path,
        )
