"""Destination configuration tests for the dlt ingestion plugin."""

from __future__ import annotations

import os
import threading
from types import SimpleNamespace
from typing import Any

import pytest
from floe_core.plugin_metadata import HealthState
from floe_core.plugins.ingestion import IngestionConfig

import floe_ingestion_dlt.plugin as plugin_module
from floe_ingestion_dlt.config import DltIngestionConfig, IngestionSourceConfig
from floe_ingestion_dlt.errors import PipelineConfigurationError
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


def test_create_pipeline_passes_filesystem_destination_without_leaking_pyiceberg_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline creation wires dlt filesystem destination without mutating process env."""
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
    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME" not in os.environ
    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__TYPE" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__WAREHOUSE" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__S3__ENDPOINT" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__S3__ACCESS_KEY_ID" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__S3__SECRET_ACCESS_KEY" not in os.environ


def test_configured_create_pipeline_requires_catalog_config() -> None:
    """Configured dlt ingestion cannot create a pipeline without an Iceberg destination."""
    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({}))
    plugin.startup()

    with pytest.raises(PipelineConfigurationError, match="catalog_config is required"):
        plugin.create_pipeline(
            IngestionConfig(
                source_type="filesystem",
                source_config={},
                destination_table="bronze.orders",
            )
        )


def test_run_serializes_pyiceberg_env_for_concurrent_catalog_configs() -> None:
    """Concurrent dlt runs cannot observe each other's transient PyIceberg env."""
    first_entered = threading.Event()
    release_first = threading.Event()
    observations: dict[str, tuple[str | None, str | None]] = {}

    class FakePipeline:
        def __init__(self, name: str, catalog_config: dict[str, Any]) -> None:
            self.pipeline_name = name
            self._floe_iceberg_catalog_config = catalog_config

        def run(self, _source: object, **_kwargs: Any) -> object:
            if self.pipeline_name == "first":
                first_entered.set()
                release_first.wait(1.5)
            observations[self.pipeline_name] = (
                os.environ.get("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"),
                os.environ.get("PYICEBERG_CATALOG__POLARIS__URI"),
            )
            return SimpleNamespace(metrics={})

    plugin = DltIngestionPlugin()
    plugin.startup()

    first = FakePipeline(
        "first",
        {
            "catalog_name": "polaris",
            "uri": "http://polaris-one:8181/api/catalog",
        },
    )
    second = FakePipeline(
        "second",
        {
            "catalog_name": "polaris",
            "uri": "http://polaris-two:8181/api/catalog",
        },
    )

    first_thread = threading.Thread(
        target=lambda: plugin.run(first, source=object(), table_name="orders"),
        name="first-run",
    )
    second_thread = threading.Thread(
        target=lambda: plugin.run(second, source=object(), table_name="orders"),
        name="second-run",
    )

    first_thread.start()
    assert first_entered.wait(0.75)
    second_thread.start()
    threading.Event().wait(0.2)

    assert "second" not in observations

    release_first.set()
    first_thread.join(0.75)
    second_thread.join(0.75)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert observations == {
        "first": ("polaris", "http://polaris-one:8181/api/catalog"),
        "second": ("polaris", "http://polaris-two:8181/api/catalog"),
    }
    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_create_pipeline_preserves_plugin_env_when_existing_value_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline creation does not overwrite caller-owned PyIceberg env values."""
    import dlt
    import dlt.destinations

    monkeypatch.setenv("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME", "caller-catalog")
    monkeypatch.setattr(dlt.destinations, "filesystem", lambda **_kwargs: object())
    monkeypatch.setattr(dlt, "pipeline", lambda **kwargs: SimpleNamespace(**kwargs))

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"uri": "http://polaris:8181/api/catalog", "bucket": "wh"}))
    plugin.startup()

    plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={},
            destination_table="bronze.orders",
        )
    )

    assert os.environ["ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"] == "caller-catalog"
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_create_pipeline_restores_plugin_env_when_destination_creation_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Destination setup failures do not leave plugin-owned PyIceberg env behind."""
    import dlt.destinations

    def raise_destination(**_kwargs: Any) -> object:
        raise RuntimeError("destination failed")

    monkeypatch.setattr(dlt.destinations, "filesystem", raise_destination)

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"uri": "http://polaris:8181/api/catalog", "bucket": "wh"}))
    plugin.startup()

    with pytest.raises(RuntimeError, match="destination failed"):
        plugin.create_pipeline(
            IngestionConfig(
                source_type="filesystem",
                source_config={},
                destination_table="bronze.orders",
            )
        )

    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_create_pipeline_restores_plugin_env_when_pipeline_creation_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dlt.pipeline failures do not leave plugin-owned PyIceberg env behind."""
    import dlt
    import dlt.destinations

    monkeypatch.setattr(dlt.destinations, "filesystem", lambda **_kwargs: object())

    def raise_pipeline(**_kwargs: Any) -> object:
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(dlt, "pipeline", raise_pipeline)

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"uri": "http://polaris:8181/api/catalog", "bucket": "wh"}))
    plugin.startup()

    with pytest.raises(RuntimeError, match="pipeline failed"):
        plugin.create_pipeline(
            IngestionConfig(
                source_type="filesystem",
                source_config={},
                destination_table="bronze.orders",
            )
        )

    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


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


def test_health_check_uses_single_timeout_budget_across_catalog_and_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catalog and object-storage probes share one health_check wall-clock budget."""
    catalog_timeouts: list[float] = []
    object_storage_timeouts: list[float] = []
    release_object_storage = threading.Event()

    def slow_catalog_check(_catalog_config: dict[str, Any], timeout: float) -> None:
        catalog_timeouts.append(timeout)
        threading.Event().wait(0.16)
        return None

    def blocking_object_storage_check(
        _catalog_config: dict[str, Any],
        timeout: float,
    ) -> str | None:
        object_storage_timeouts.append(timeout)
        release_object_storage.wait(1.5)
        return f"TimeoutError: object_storage health check exceeded {timeout}s"

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"uri": "http://polaris:8181/api/catalog", "bucket": "wh"}))
    plugin.startup()
    monkeypatch.setattr(plugin, "_check_catalog_reachable", slow_catalog_check)
    monkeypatch.setattr(plugin, "_check_object_storage_reachable", blocking_object_storage_check)

    start = plugin_module.time.perf_counter()
    status = plugin.health_check(timeout=0.2)
    elapsed = plugin_module.time.perf_counter() - start

    release_object_storage.set()

    assert elapsed < 0.3
    assert status.state is HealthState.UNHEALTHY
    assert status.details["reason"] == "object_storage_unreachable"
    assert len(catalog_timeouts) == 1
    assert 0.19 <= catalog_timeouts[0] <= 0.2
    assert len(object_storage_timeouts) == 1
    assert 0 < object_storage_timeouts[0] < 0.08


def test_health_check_reports_non_s3_object_storage_as_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-S3 bucket URL is not reported as reachable when no storage probe runs."""
    plugin = DltIngestionPlugin()
    plugin.configure(
        _plugin_config(
            {
                "uri": "http://polaris:8181/api/catalog",
                "bucket_url": "file:///tmp/floe-warehouse",
            }
        )
    )
    plugin.startup()
    monkeypatch.setattr(plugin, "_check_catalog_reachable", lambda *_args, **_kwargs: None)

    status = plugin.health_check()

    assert status.state is HealthState.HEALTHY
    assert status.details["catalog_check"] == "reachable"
    assert status.details["object_storage_check"] == "skipped_non_s3"


def test_catalog_health_check_wall_clock_timeout_does_not_accumulate_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocking catalog probe returns within timeout without unbounded workers."""
    release_probe = threading.Event()

    class BlockingClient:
        def __init__(self, *, timeout: float) -> None:
            assert 0 < timeout <= 0.1

        def __enter__(self) -> BlockingClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, _url: str) -> SimpleNamespace:
            release_probe.wait(1.5)
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(plugin_module.httpx, "Client", BlockingClient)
    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config({"uri": "http://polaris:8181/api/catalog"}))
    plugin.startup()

    start = plugin_module.time.perf_counter()
    status = plugin.health_check(timeout=0.1)
    elapsed = plugin_module.time.perf_counter() - start
    release_probe.set()

    assert elapsed < 0.75
    assert status.state is HealthState.UNHEALTHY
    assert status.details["reason"] == "catalog_unreachable"
    assert "catalog health check exceeded" in status.details["catalog_error"]
    assert (
        len([thread for thread in threading.enumerate() if thread.name.startswith("dlt-health")])
        <= 2
    )
    slot = DltIngestionPlugin._health_check_slot("catalog")
    assert slot.acquire(timeout=0.75)
    slot.release()
    budget_slot = DltIngestionPlugin._health_check_slot("catalog_budget")
    assert budget_slot.acquire(timeout=0.75)
    budget_slot.release()


def test_catalog_health_check_timeout_applies_from_worker_thread() -> None:
    """Worker-thread health checks still have a deterministic wall-clock timeout."""
    result: list[str] = []
    release_probe = threading.Event()

    def worker_call() -> None:
        try:
            DltIngestionPlugin._run_health_check_with_timeout(
                lambda: release_probe.wait(1.5),
                0.1,
                check_name="catalog_worker",
            )
        except Exception as exc:  # noqa: BLE001 - verifying surfaced error type/message
            result.append(f"{type(exc).__name__}: {exc}")

    thread = threading.Thread(target=worker_call, name="health-caller")
    start = plugin_module.time.perf_counter()
    thread.start()
    thread.join(0.75)
    elapsed = plugin_module.time.perf_counter() - start

    assert not thread.is_alive()
    assert elapsed < 0.75
    assert result == ["TimeoutError: catalog_worker health check exceeded 0.1s"]
    assert (
        len([thread for thread in threading.enumerate() if thread.name.startswith("dlt-health")])
        <= 1
    )
    release_probe.set()
    slot = DltIngestionPlugin._health_check_slot("catalog_worker")
    assert slot.acquire(timeout=0.75)
    slot.release()


def test_catalog_health_check_passes_timeout_to_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Catalog reachability uses bounded HTTP client timeouts."""
    client_timeouts: list[float] = []
    requests: list[tuple[str, str]] = []

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            client_timeouts.append(timeout)

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, url: str) -> SimpleNamespace:
            requests.append(("GET", url))
            return SimpleNamespace(status_code=401)

    monkeypatch.setattr(plugin_module.httpx, "Client", FakeClient)

    plugin = DltIngestionPlugin()
    error = plugin._check_catalog_reachable(
        {"uri": "http://polaris:8181/api/catalog", "warehouse": "floe"},
        timeout=0.25,
    )

    assert error is None
    assert client_timeouts == [0.25]
    assert requests == [("GET", "http://polaris:8181/api/catalog/v1/config?warehouse=floe")]


def test_object_storage_health_check_passes_timeout_to_s3fs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Object storage reachability configures bounded S3 client timeouts."""
    calls: list[dict[str, Any]] = []

    class FakeFilesystem:
        def ls(self, path: str, *, detail: bool, max_items: int) -> list[str]:
            assert path == "bucket"
            assert detail is False
            assert max_items == 1
            return []

    def fake_get_fs_token_paths(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[FakeFilesystem, None, list[str]]:
        calls.append({"args": args, "kwargs": kwargs})
        return FakeFilesystem(), None, ["bucket"]

    monkeypatch.setattr(plugin_module.fsspec, "get_fs_token_paths", fake_get_fs_token_paths)

    plugin = DltIngestionPlugin()
    error = plugin._check_object_storage_reachable(
        {
            "bucket": "bucket",
            "s3_endpoint": "http://minio:9000",
            "s3_region": "us-east-1",
        },
        timeout=0.75,
    )

    assert error is None
    assert calls == [
        {
            "args": ("s3://bucket",),
            "kwargs": {
                "key": os.environ.get("AWS_ACCESS_KEY_ID"),
                "secret": os.environ.get("AWS_SECRET_ACCESS_KEY"),
                "client_kwargs": {
                    "endpoint_url": "http://minio:9000",
                    "region_name": os.environ.get("AWS_REGION") or "us-east-1",
                },
                "config_kwargs": {
                    "connect_timeout": 0.75,
                    "read_timeout": 0.75,
                    "s3": {"addressing_style": "path"},
                },
            },
        }
    ]


def test_object_storage_health_check_has_wall_clock_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocking object-storage probe returns within the requested timeout."""
    release_probe = threading.Event()

    def blocking_get_fs_token_paths(*_args: Any, **_kwargs: Any) -> tuple[object, None, list[str]]:
        release_probe.wait(1.5)
        return object(), None, ["bucket"]

    monkeypatch.setattr(plugin_module.fsspec, "get_fs_token_paths", blocking_get_fs_token_paths)

    plugin = DltIngestionPlugin()
    start = plugin_module.time.perf_counter()
    error = plugin._check_object_storage_reachable(
        {"bucket": "bucket", "s3_endpoint": "http://minio:9000"},
        timeout=0.1,
    )
    elapsed = plugin_module.time.perf_counter() - start

    assert elapsed < 0.75
    assert error == "TimeoutError: object_storage health check exceeded 0.1s"
    release_probe.set()
    slot = DltIngestionPlugin._health_check_slot("object_storage")
    assert slot.acquire(timeout=0.75)
    slot.release()


def test_object_storage_health_check_timeout_applies_from_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Object-storage probes keep wall-clock timeout behavior in worker hosts."""
    release_probe = threading.Event()

    def blocking_get_fs_token_paths(*_args: Any, **_kwargs: Any) -> tuple[object, None, list[str]]:
        release_probe.wait(1.5)
        return object(), None, ["bucket"]

    monkeypatch.setattr(plugin_module.fsspec, "get_fs_token_paths", blocking_get_fs_token_paths)
    plugin = DltIngestionPlugin()
    result: list[str | None] = []

    def worker_call() -> None:
        result.append(
            plugin._check_object_storage_reachable(
                {"bucket": "bucket", "s3_endpoint": "http://minio:9000"},
                timeout=0.1,
            )
        )

    thread = threading.Thread(target=worker_call, name="object-storage-health-caller")
    start = plugin_module.time.perf_counter()
    thread.start()
    thread.join(0.75)
    elapsed = plugin_module.time.perf_counter() - start

    assert not thread.is_alive()
    assert elapsed < 0.75
    assert result == ["TimeoutError: object_storage health check exceeded 0.1s"]
    release_probe.set()
    slot = DltIngestionPlugin._health_check_slot("object_storage")
    assert slot.acquire(timeout=0.75)
    slot.release()
