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
            path=f"./data/customers.{format_}",
            extra_source_config={"file_glob": "*.data", "reader_options": {"chunksize": 7}},
        ),
        project_dir=tmp_path,
    )

    assert isinstance(source, FakeDltResource)
    assert source.name == "raw_customers"
    assert source.table_name == "raw_customers"
    assert source.parent is not None
    assert source.parent.kwargs == {
        "bucket_url": str(tmp_path / f"data/customers.{format_}"),
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
    assert source.parent.kwargs["bucket_url"] == str(tmp_path / "data/customers.csv")
    assert fake_filesystem_module.calls[0][0] == "filesystem"


def test_build_filesystem_source_leaves_object_store_paths_unchanged(
    tmp_path: Path,
    fake_filesystem_module: FakeFilesystemModule,
) -> None:
    """Object-store URIs remain environment-provided dlt filesystem locations."""
    from floe_orchestrator_dagster.ingestion import build_filesystem_source

    source = build_filesystem_source(
        _source_config(path="s3://raw/customers/*.csv"),
        project_dir=tmp_path,
    )

    assert source.parent is not None
    assert source.parent.kwargs["bucket_url"] == "s3://raw/customers/*.csv"
    assert fake_filesystem_module.calls[0][0] == "filesystem"


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
        (_source_config(path="/var/data/customers.csv"), "absolute.*raw-customers"),
        (
            _source_config(extra_source_config={"credentials": {"token": "secret"}}),
            "credentials.*raw-customers",
        ),
        (_source_config(extra_source_config={"host": "localhost"}), "host.*raw-customers"),
        (_source_config(extra_source_config={"unknown": "value"}), "unknown.*raw-customers"),
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
