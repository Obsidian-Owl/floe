"""Destination configuration tests for the dlt ingestion plugin."""

from __future__ import annotations

import os
import threading
from types import SimpleNamespace
from typing import Any

import pytest
from floe_core.plugin_metadata import HealthState
from floe_core.plugins.ingestion import IngestionConfig
from floe_core.schemas.compiled_artifacts import DltIngestionBinding

import floe_ingestion_dlt.plugin as plugin_module
from floe_ingestion_dlt.config import DltIngestionConfig, IngestionSourceConfig
from floe_ingestion_dlt.errors import PipelineConfigurationError
from floe_ingestion_dlt.plugin import DltIngestionPlugin


def _plugin_config() -> DltIngestionConfig:
    return DltIngestionConfig(
        sources=[
            IngestionSourceConfig(
                name="orders",
                source_type="filesystem",
                destination_table="bronze.orders",
            )
        ]
    )


def _runtime_binding() -> dict[str, Any]:
    return {
        "destination": "filesystem",
        "source": "filesystem",
        "destination_filesystem": {
            "bucket_url": "s3://runtime-warehouse",
            "credentials": {
                "endpoint_url": "http://runtime-minio:9000",
                "region_name": "us-east-1",
                "s3_url_style": "path",
            },
        },
        "source_filesystem": {
            "endpoint_url": "http://runtime-minio:9000",
            "region_name": "us-east-1",
            "s3_url_style": "path",
        },
        "iceberg_catalog_env": {
            "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": "polaris",
            "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
            "PYICEBERG_CATALOG__POLARIS__TYPE": "rest",
            "PYICEBERG_CATALOG__POLARIS__URI": "http://runtime-polaris:8181/api/catalog",
        },
        "env_refs": {
            "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
            "PYICEBERG_CATALOG__POLARIS__CREDENTIAL": "POLARIS_CREDENTIAL",
            "PYICEBERG_CATALOG__POLARIS__SCOPE": "POLARIS_SCOPE",
            "PYICEBERG_CATALOG__POLARIS__OAUTH2_SERVER_URI": ("POLARIS_OAUTH2_SERVER_URI"),
        },
    }


def _runtime_binding_model() -> DltIngestionBinding:
    binding = _runtime_binding()
    return DltIngestionBinding(
        plugin_name="dlt",
        destination="filesystem",
        table_format="iceberg",
        source_filesystem=binding["source_filesystem"],
        destination_filesystem=binding["destination_filesystem"],
        iceberg_catalog_env=binding["iceberg_catalog_env"],
        env_refs=binding["env_refs"],
    )


def _partial_runtime_binding_model() -> DltIngestionBinding:
    binding = _runtime_binding()
    return DltIngestionBinding(
        plugin_name="dlt",
        destination="filesystem",
        table_format="iceberg",
        source_filesystem=binding["source_filesystem"],
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


def test_create_pipeline_passes_runtime_filesystem_destination_without_leaking_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline creation wires runtime binding destination without mutating process env."""
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
    plugin.configure(_plugin_config())
    plugin.startup()

    binding = _runtime_binding()
    pipeline = plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={},
            destination_table="bronze.orders",
            runtime_binding=binding,
        )
    )

    assert pipeline.pipeline_name == "ingest_orders"
    assert destination_calls == [binding["destination_filesystem"]]
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


def test_create_pipeline_ignores_configured_plugin_state_when_binding_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime binding destination config is the only dlt runtime destination source."""
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

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config())
    plugin.startup()

    binding = _runtime_binding()
    pipeline = plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={},
            destination_table="bronze.orders",
            runtime_binding=binding,
        )
    )

    assert destination_calls == [binding["destination_filesystem"]]
    assert pipeline_calls == [
        {
            "pipeline_name": "ingest_orders",
            "dataset_name": "bronze",
            "destination": fake_destination,
        }
    ]
    assert pipeline.pipeline_name == "ingest_orders"
    assert pipeline._floe_dlt_runtime_binding == binding


def test_create_pipeline_normalizes_pydantic_runtime_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compiled DltIngestionBinding models are normalized before pipeline creation."""
    destination_calls: list[dict[str, Any]] = []
    fake_destination = object()

    def fake_filesystem(**kwargs: Any) -> object:
        destination_calls.append(kwargs)
        return fake_destination

    import dlt
    import dlt.destinations

    monkeypatch.setattr(dlt.destinations, "filesystem", fake_filesystem)
    monkeypatch.setattr(dlt, "pipeline", lambda **kwargs: SimpleNamespace(**kwargs))

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config())
    plugin.startup()

    binding = _runtime_binding_model()
    pipeline = plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={},
            destination_table="bronze.orders",
            runtime_binding=binding,
        )
    )

    expected_binding = binding.model_dump(mode="python")
    assert destination_calls == [expected_binding["destination_filesystem"]]
    assert pipeline.destination is fake_destination
    assert pipeline._floe_dlt_runtime_binding == expected_binding


def test_configured_create_pipeline_requires_runtime_binding() -> None:
    """Configured dlt ingestion cannot create a pipeline without runtime binding."""
    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config())
    plugin.startup()

    with pytest.raises(PipelineConfigurationError, match="dlt runtime binding is required"):
        plugin.create_pipeline(
            IngestionConfig(
                source_type="filesystem",
                source_config={},
                destination_table="bronze.orders",
            )
        )


def test_run_serializes_pyiceberg_env_for_concurrent_runtime_bindings() -> None:
    """Concurrent dlt runs cannot observe each other's runtime PyIceberg env."""
    first_entered = threading.Event()
    release_first = threading.Event()
    observations: dict[str, tuple[str | None, str | None]] = {}

    class FakePipeline:
        def __init__(self, name: str, uri: str) -> None:
            self.pipeline_name = name
            binding = _runtime_binding()
            binding["iceberg_catalog_env"] = {
                "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": "polaris",
                "PYICEBERG_CATALOG__POLARIS__URI": uri,
            }
            self._floe_dlt_runtime_binding = binding

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

    first = FakePipeline("first", "http://polaris-one:8181/api/catalog")
    second = FakePipeline("second", "http://polaris-two:8181/api/catalog")

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


def test_run_applies_runtime_binding_catalog_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime binding catalog env is applied only while dlt executes the pipeline."""
    observations: dict[str, tuple[str | None, str | None]] = {}

    class FakePipeline:
        pipeline_name = "runtime"
        _floe_dlt_runtime_binding = _runtime_binding()

        def run(self, _source: object, **_kwargs: Any) -> object:
            observations["during_run"] = (
                os.environ.get("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"),
                os.environ.get("PYICEBERG_CATALOG__POLARIS__URI"),
            )
            return SimpleNamespace(metrics={})

    monkeypatch.setenv("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME", "caller-catalog")
    monkeypatch.delenv("PYICEBERG_CATALOG__POLARIS__URI", raising=False)

    plugin = DltIngestionPlugin()
    plugin.startup()

    plugin.run(FakePipeline(), source=object(), table_name="orders")

    assert observations == {"during_run": ("polaris", "http://runtime-polaris:8181/api/catalog")}
    assert os.environ["ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"] == "caller-catalog"
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_run_resolves_runtime_binding_env_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime env refs map source process env vars into dlt PyIceberg env names."""
    observations: dict[str, tuple[str | None, str | None, str | None]] = {}

    class FakePipeline:
        pipeline_name = "runtime-env-refs"
        _floe_dlt_runtime_binding = _runtime_binding()

        def run(self, _source: object, **_kwargs: Any) -> object:
            observations["during_run"] = (
                os.environ.get("PYICEBERG_CATALOG__POLARIS__CREDENTIAL"),
                os.environ.get("PYICEBERG_CATALOG__POLARIS__SCOPE"),
                os.environ.get("PYICEBERG_CATALOG__POLARIS__OAUTH2_SERVER_URI"),
            )
            return SimpleNamespace(metrics={})

    monkeypatch.setenv("POLARIS_CREDENTIAL", "runtime-client:runtime-secret")
    monkeypatch.setenv("POLARIS_SCOPE", "PRINCIPAL_ROLE:ALL")
    monkeypatch.setenv(
        "POLARIS_OAUTH2_SERVER_URI",
        "http://runtime-polaris:8181/api/catalog/v1/oauth/tokens",
    )
    monkeypatch.delenv("PYICEBERG_CATALOG__POLARIS__CREDENTIAL", raising=False)
    monkeypatch.delenv("PYICEBERG_CATALOG__POLARIS__SCOPE", raising=False)
    monkeypatch.delenv("PYICEBERG_CATALOG__POLARIS__OAUTH2_SERVER_URI", raising=False)

    plugin = DltIngestionPlugin()
    plugin.startup()

    plugin.run(FakePipeline(), source=object(), table_name="orders")

    assert observations == {
        "during_run": (
            "runtime-client:runtime-secret",
            "PRINCIPAL_ROLE:ALL",
            "http://runtime-polaris:8181/api/catalog/v1/oauth/tokens",
        )
    }
    assert "PYICEBERG_CATALOG__POLARIS__CREDENTIAL" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__SCOPE" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__OAUTH2_SERVER_URI" not in os.environ


def test_run_normalizes_pydantic_runtime_binding_catalog_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compiled DltIngestionBinding models apply catalog env during pipeline execution."""
    observations: dict[str, tuple[str | None, str | None]] = {}

    class FakePipeline:
        pipeline_name = "runtime-model"
        _floe_dlt_runtime_binding = _runtime_binding_model()

        def run(self, _source: object, **_kwargs: Any) -> object:
            observations["during_run"] = (
                os.environ.get("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"),
                os.environ.get("PYICEBERG_CATALOG__POLARIS__URI"),
            )
            return SimpleNamespace(metrics={})

    monkeypatch.setenv("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME", "caller-catalog")
    monkeypatch.delenv("PYICEBERG_CATALOG__POLARIS__URI", raising=False)

    plugin = DltIngestionPlugin()
    plugin.startup()

    plugin.run(FakePipeline(), source=object(), table_name="orders")

    assert observations == {"during_run": ("polaris", "http://runtime-polaris:8181/api/catalog")}
    assert os.environ["ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"] == "caller-catalog"
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_incomplete_runtime_catalog_env_does_not_use_legacy_catalog_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incomplete runtime catalog env is applied as-is without catalog_config fallback."""
    observations: dict[str, tuple[str | None, str | None, str | None, str | None]] = {}

    class FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            self.pipeline_name = kwargs["pipeline_name"]

        def run(self, _source: object, **_kwargs: Any) -> object:
            observations["during_run"] = (
                os.environ.get("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"),
                os.environ.get("ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE"),
                os.environ.get("PYICEBERG_CATALOG__POLARIS__TYPE"),
                os.environ.get("PYICEBERG_CATALOG__POLARIS__URI"),
            )
            return SimpleNamespace(metrics={})

    import dlt
    import dlt.destinations

    monkeypatch.setattr(dlt.destinations, "filesystem", lambda **_kwargs: object())
    monkeypatch.setattr(dlt, "pipeline", FakePipeline)
    monkeypatch.setenv("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME", "caller-catalog")

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config())
    plugin.startup()

    runtime_binding = _runtime_binding()
    runtime_binding["iceberg_catalog_env"] = {
        "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": "polaris",
    }
    pipeline = plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={},
            destination_table="bronze.orders",
            runtime_binding=runtime_binding,
        )
    )
    plugin.run(pipeline, source=object(), table_name="orders")

    assert observations == {
        "during_run": (
            "polaris",
            None,
            None,
            None,
        )
    }
    assert os.environ["ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"] == "caller-catalog"
    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__TYPE" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_create_pipeline_preserves_caller_env_when_existing_value_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline creation does not overwrite caller-owned PyIceberg env values."""
    import dlt
    import dlt.destinations

    monkeypatch.setenv("ICEBERG_CATALOG__ICEBERG_CATALOG_NAME", "caller-catalog")
    monkeypatch.setattr(dlt.destinations, "filesystem", lambda **_kwargs: object())
    monkeypatch.setattr(dlt, "pipeline", lambda **kwargs: SimpleNamespace(**kwargs))

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config())
    plugin.startup()

    plugin.create_pipeline(
        IngestionConfig(
            source_type="filesystem",
            source_config={},
            destination_table="bronze.orders",
            runtime_binding=_runtime_binding(),
        )
    )

    assert os.environ["ICEBERG_CATALOG__ICEBERG_CATALOG_NAME"] == "caller-catalog"
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_create_pipeline_restores_caller_env_when_destination_creation_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Destination setup failures do not leave caller-owned PyIceberg env changed."""
    import dlt.destinations

    def raise_destination(**_kwargs: Any) -> object:
        raise RuntimeError("destination failed")

    monkeypatch.setattr(dlt.destinations, "filesystem", raise_destination)

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config())
    plugin.startup()

    with pytest.raises(RuntimeError, match="destination failed"):
        plugin.create_pipeline(
            IngestionConfig(
                source_type="filesystem",
                source_config={},
                destination_table="bronze.orders",
                runtime_binding=_runtime_binding(),
            )
        )

    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_create_pipeline_restores_caller_env_when_pipeline_creation_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dlt.pipeline failures do not leave caller-owned PyIceberg env changed."""
    import dlt
    import dlt.destinations

    monkeypatch.setattr(dlt.destinations, "filesystem", lambda **_kwargs: object())

    def raise_pipeline(**_kwargs: Any) -> object:
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(dlt, "pipeline", raise_pipeline)

    plugin = DltIngestionPlugin()
    plugin.configure(_plugin_config())
    plugin.startup()

    with pytest.raises(RuntimeError, match="pipeline failed"):
        plugin.create_pipeline(
            IngestionConfig(
                source_type="filesystem",
                source_config={},
                destination_table="bronze.orders",
                runtime_binding=_runtime_binding(),
            )
        )

    assert "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME" not in os.environ
    assert "PYICEBERG_CATALOG__POLARIS__URI" not in os.environ


def test_health_check_stays_fast_without_catalog_config() -> None:
    """Unconfigured health check remains import-only and non-networked."""
    plugin = DltIngestionPlugin()
    plugin.startup()

    status = plugin.health_check()

    assert status.state is HealthState.HEALTHY
    assert status.details["catalog_check"] == "not_configured"
    assert status.details["object_storage_check"] == "not_configured"


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
