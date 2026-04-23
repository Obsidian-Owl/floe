"""Unit tests for Polaris/Iceberg namespace reset semantics."""

from __future__ import annotations

import sys
from types import ModuleType
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import dbt_utils


def test_clear_catalog_cache_drops_cached_catalog() -> None:
    dbt_utils._catalog_cache["catalog"] = object()

    dbt_utils._clear_catalog_cache()

    assert dbt_utils._catalog_cache == {}


def test_get_polaris_catalog_uses_env_endpoints_without_eager_service_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_catalog = object()
    pyiceberg_module = ModuleType("pyiceberg")
    load_calls: list[dict[str, object]] = []

    def _load_catalog(name: str, **kwargs: object) -> object:
        assert name == "polaris"
        load_calls.append(kwargs)
        return fake_catalog

    def _unexpected_service_endpoint(*args: object, **kwargs: object) -> object:
        raise AssertionError("ServiceEndpoint should not be evaluated")

    pyiceberg_module.catalog = SimpleNamespace(load_catalog=_load_catalog)

    monkeypatch.setitem(sys.modules, "pyiceberg", pyiceberg_module)
    monkeypatch.setenv("POLARIS_URI", "http://example.test/api/catalog")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio.test:9000")
    monkeypatch.setattr(dbt_utils, "ServiceEndpoint", _unexpected_service_endpoint)
    monkeypatch.setattr(dbt_utils, "get_polaris_credentials", lambda: ("id", "secret"))
    monkeypatch.setattr(dbt_utils, "get_minio_credentials", lambda: ("access", "secret"))
    dbt_utils._clear_catalog_cache()

    catalog = dbt_utils._get_polaris_catalog(fresh=True)

    assert catalog is fake_catalog
    assert load_calls == [
        {
            "type": "rest",
            "uri": "http://example.test/api/catalog",
            "credential": "id:secret",
            "scope": "PRINCIPAL_ROLE:ALL",
            "warehouse": "floe-e2e",
            "s3.endpoint": "http://minio.test:9000",
            "s3.access-key-id": "access",
            "s3.secret-access-key": "secret",
            "s3.region": "us-east-1",
            "s3.path-style-access": "true",
        }
    ]


def test_get_polaris_catalog_returns_none_when_service_endpoint_resolution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pyiceberg_module = ModuleType("pyiceberg")
    pyiceberg_module.catalog = SimpleNamespace(load_catalog=lambda *args, **kwargs: object())

    def _failing_service_endpoint(*args: object, **kwargs: object) -> object:
        raise RuntimeError("service lookup failed")

    monkeypatch.setitem(sys.modules, "pyiceberg", pyiceberg_module)
    monkeypatch.delenv("POLARIS_URI", raising=False)
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.setattr(dbt_utils, "ServiceEndpoint", _failing_service_endpoint)
    monkeypatch.setattr(dbt_utils, "get_polaris_credentials", lambda: ("id", "secret"))
    monkeypatch.setattr(dbt_utils, "get_minio_credentials", lambda: ("access", "secret"))
    dbt_utils._clear_catalog_cache()

    assert dbt_utils._get_polaris_catalog(fresh=True) is None


def test_purge_namespace_raises_when_namespace_still_contains_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_catalog = Mock()
    fake_catalog.list_tables.return_value = [("customer_360", "stg_customers")]

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", lambda fresh=False: fake_catalog)
    monkeypatch.setattr(dbt_utils, "_delete_s3_prefix", lambda *args, **kwargs: 0)
    monkeypatch.setattr(dbt_utils.boto3, "client", lambda *args, **kwargs: Mock())

    with pytest.raises(dbt_utils.NamespaceResetError, match="Namespace reset incomplete"):
        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)


def test_purge_namespace_raises_when_verified_s3_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_catalog = Mock()
    purge_catalog.list_tables.return_value = [("customer_360", "stg_customers")]
    table = Mock()
    table.metadata.location = "s3://warehouse/customer_360/stg_customers"
    purge_catalog.load_table.return_value = table
    verify_catalog = Mock()
    verify_catalog.list_tables.return_value = []
    catalogs = [purge_catalog, verify_catalog]
    s3_client = Mock()
    paginator = Mock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "customer_360/stg_customers/data/file.parquet"}]}
    ]
    s3_client.get_paginator.return_value = paginator
    s3_client.delete_objects.return_value = {
        "Errors": [{"Key": "customer_360/stg_customers/data/file.parquet"}]
    }

    def _get_catalog(*, fresh: bool = False) -> Mock:
        return catalogs.pop(0)

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)
    monkeypatch.setattr(dbt_utils.boto3, "client", lambda *args, **kwargs: s3_client)

    with pytest.raises(dbt_utils.NamespaceResetError, match="delete_objects reported errors"):
        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)


def test_purge_namespace_raises_when_storage_endpoint_cannot_be_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_catalog = Mock()
    purge_catalog.list_tables.return_value = [("customer_360", "stg_customers")]
    table = Mock()
    table.metadata.location = "s3://warehouse/customer_360/stg_customers"
    purge_catalog.load_table.return_value = table
    verify_catalog = Mock()
    verify_catalog.list_tables.return_value = []
    catalogs = [purge_catalog, verify_catalog]

    def _get_catalog(*, fresh: bool = False) -> Mock:
        return catalogs.pop(0)

    def _failing_service_endpoint(*args: object, **kwargs: object) -> object:
        raise RuntimeError("endpoint lookup failed")

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.setattr(dbt_utils, "ServiceEndpoint", _failing_service_endpoint)

    with pytest.raises(
        dbt_utils.NamespaceResetError,
        match="Could not resolve storage endpoint for cleanup in customer_360: RuntimeError",
    ):
        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)


def test_purge_namespace_raises_when_storage_location_cannot_be_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_catalog = Mock()
    purge_catalog.list_tables.return_value = [("customer_360", "stg_customers")]
    purge_catalog.load_table.side_effect = RuntimeError("load failed")
    verify_catalog = Mock()
    verify_catalog.list_tables.return_value = []
    catalogs = [purge_catalog, verify_catalog]

    def _get_catalog(*, fresh: bool = False) -> Mock:
        return catalogs.pop(0)

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)

    with pytest.raises(
        dbt_utils.NamespaceResetError,
        match="Could not resolve storage location for customer_360.stg_customers",
    ):
        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)


def test_purge_namespace_raises_when_purge_phase_table_enumeration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_catalog = Mock()
    purge_catalog.list_tables.side_effect = RuntimeError("catalog boom")
    verify_catalog = Mock()
    verify_catalog.list_tables.return_value = []
    catalogs = [purge_catalog, verify_catalog]

    def _get_catalog(*, fresh: bool = False) -> Mock:
        return catalogs.pop(0)

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)

    with pytest.raises(
        dbt_utils.NamespaceResetError,
        match="Could not enumerate tables for storage cleanup in customer_360: RuntimeError",
    ):
        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)


def test_purge_namespace_uses_fresh_catalog_for_purge_and_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_catalog = Mock()
    purge_catalog.list_tables.return_value = []
    verify_catalog = Mock()
    verify_catalog.list_tables.return_value = []
    fresh_calls: list[bool] = []

    def _get_catalog(*, fresh: bool = False) -> Mock:
        fresh_calls.append(fresh)
        return purge_catalog if len(fresh_calls) == 1 else verify_catalog

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)

    dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=2)

    assert fresh_calls == [True, True]


def test_purge_namespace_raises_when_fresh_catalog_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _get_catalog(*, fresh: bool = False) -> None:
        return None

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)

    with pytest.raises(dbt_utils.NamespaceResetError, match="verification catalog unavailable"):
        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=2)


def test_purge_namespace_raises_on_verification_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_catalog = Mock()
    purge_catalog.list_tables.return_value = []
    verification_catalog = Mock()
    verification_catalog.list_tables.side_effect = RuntimeError("boom")
    catalogs = [purge_catalog, verification_catalog, verification_catalog]

    def _get_catalog(*, fresh: bool = False) -> Mock:
        return catalogs.pop(0)

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)

    with pytest.raises(dbt_utils.NamespaceResetError, match="verification failed: RuntimeError"):
        dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=2)


def test_purge_namespace_treats_missing_namespace_as_reset_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeNoSuchNamespaceError(Exception):
        """Test-only stand-in for PyIceberg's missing namespace exception."""

    fake_catalog = Mock()
    fake_catalog.list_tables.side_effect = FakeNoSuchNamespaceError("customer_360")

    monkeypatch.setattr(
        dbt_utils,
        "PyIcebergNoSuchNamespaceError",
        FakeNoSuchNamespaceError,
    )
    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", lambda fresh=False: fake_catalog)

    dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)


def test_purge_namespace_initial_missing_namespace_returns_without_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeNoSuchNamespaceError(Exception):
        """Test-only stand-in for PyIceberg's missing namespace exception."""

    purge_catalog = Mock()
    purge_catalog.list_tables.side_effect = FakeNoSuchNamespaceError("customer_360")
    fresh_calls: list[bool] = []

    def _get_catalog(*, fresh: bool = False) -> Mock | None:
        fresh_calls.append(fresh)
        return purge_catalog if len(fresh_calls) == 1 else None

    monkeypatch.setattr(
        dbt_utils,
        "PyIcebergNoSuchNamespaceError",
        FakeNoSuchNamespaceError,
    )
    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)

    dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)

    assert fresh_calls == [True]


def test_purge_namespace_drop_failure_still_succeeds_when_verification_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purge_catalog = Mock()
    purge_catalog.list_tables.return_value = []
    purge_catalog.drop_namespace.side_effect = RuntimeError("drop failed")
    verify_catalog = Mock()
    verify_catalog.list_tables.return_value = []
    catalogs = [purge_catalog, verify_catalog]

    def _get_catalog(*, fresh: bool = False) -> Mock:
        return catalogs.pop(0)

    monkeypatch.setattr(dbt_utils, "_get_polaris_catalog", _get_catalog)

    dbt_utils._purge_iceberg_namespace("customer_360", verify_empty=True, retries=1)


def test_run_dbt_resets_raw_namespace_before_seed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "customer-360"
    project_dir.mkdir()

    purge_calls: list[tuple[str, bool]] = []

    def _record(namespace: str, verify_empty: bool = False, retries: int = 3) -> None:
        purge_calls.append((namespace, verify_empty))

    monkeypatch.setattr(dbt_utils, "_purge_iceberg_namespace", _record)
    monkeypatch.setattr(
        dbt_utils.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    dbt_utils.run_dbt(["seed"], project_dir)

    assert purge_calls == [("customer_360_raw", True)]


def test_run_dbt_resets_model_namespace_before_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "customer-360"
    project_dir.mkdir()

    purge_calls: list[tuple[str, bool]] = []

    def _record(namespace: str, verify_empty: bool = False, retries: int = 3) -> None:
        purge_calls.append((namespace, verify_empty))

    monkeypatch.setattr(dbt_utils, "_purge_iceberg_namespace", _record)
    monkeypatch.setattr(
        dbt_utils.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    dbt_utils.run_dbt(["run"], project_dir)

    assert purge_calls == [("customer_360", True)]
