from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from floe_core.plugin_errors import PluginStartupError
from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata
from floe_core.plugin_types import PluginType
from floe_core.plugins.lifecycle import PluginLifecycle
from floe_core.telemetry.lifecycle import (
    lifecycle_metric_labels,
    observe_plugin_lifecycle,
    plugin_lifecycle_attributes,
)


def test_plugin_lifecycle_attributes_are_secret_free() -> None:
    attrs = plugin_lifecycle_attributes(
        plugin_type="SECRETS",
        plugin_name="k8s",
        plugin_version="0.1.0",
        floe_api_version="0.1",
        phase="health_check",
        status="unhealthy",
        error_type="SecretBackendUnavailableError",
        extra={"token": "must-not-leak", "backend": "kubernetes"},
    )

    assert attrs["floe.plugin.type"] == "SECRETS"
    assert attrs["floe.plugin.name"] == "k8s"
    assert attrs["floe.plugin.version"] == "0.1.0"
    assert attrs["floe.plugin.floe_api_version"] == "0.1"
    assert attrs["floe.plugin.lifecycle.phase"] == "health_check"
    assert attrs["floe.plugin.lifecycle.status"] == "unhealthy"
    assert attrs["floe.error.type"] == "SecretBackendUnavailableError"
    assert attrs["backend"] == "kubernetes"
    assert "token" not in attrs


def test_lifecycle_metric_labels_are_low_cardinality() -> None:
    labels = lifecycle_metric_labels(
        plugin_type="COMPUTE",
        plugin_name="duckdb",
        phase="startup",
        status="success",
    )

    assert labels == {
        "floe.plugin.type": "COMPUTE",
        "floe.plugin.name": "duckdb",
        "floe.plugin.lifecycle.phase": "startup",
        "floe.plugin.lifecycle.status": "success",
    }


def test_observe_plugin_lifecycle_records_startup_success_span_and_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans: list[_FakeSpan] = []
    metrics = _FakeMetricRecorder()

    @contextmanager
    def fake_create_span(
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[_FakeSpan]:
        span = _FakeSpan(name=name, attributes=attributes or {})
        spans.append(span)
        yield span

    monkeypatch.setattr("floe_core.telemetry.lifecycle.create_span", fake_create_span)

    with observe_plugin_lifecycle(
        plugin_type="COMPUTE",
        plugin_name="duckdb",
        plugin_version="0.1.0",
        floe_api_version="0.1",
        phase="startup",
        metrics=metrics,
    ) as observation:
        observation.finish(status="success")

    assert spans[0].name == "floe.plugin.lifecycle.startup"
    assert spans[0].attributes["floe.plugin.lifecycle.status"] == "success"
    assert metrics.histograms[0]["name"] == "floe.plugin.lifecycle.duration"
    assert metrics.histograms[0]["labels"] == {
        "floe.plugin.type": "COMPUTE",
        "floe.plugin.name": "duckdb",
        "floe.plugin.lifecycle.phase": "startup",
        "floe.plugin.lifecycle.status": "success",
    }
    assert metrics.counters == []


def test_observe_plugin_lifecycle_records_exception_failure_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans: list[_FakeSpan] = []
    metrics = _FakeMetricRecorder()

    @contextmanager
    def fake_create_span(
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[_FakeSpan]:
        span = _FakeSpan(name=name, attributes=attributes or {})
        spans.append(span)
        yield span

    monkeypatch.setattr("floe_core.telemetry.lifecycle.create_span", fake_create_span)

    with pytest.raises(ValueError, match="boom"):
        with observe_plugin_lifecycle(
            plugin_type="COMPUTE",
            plugin_name="duckdb",
            plugin_version="0.1.0",
            floe_api_version="0.1",
            phase="startup",
            metrics=metrics,
        ):
            raise ValueError("boom")

    assert spans[0].attributes["floe.plugin.lifecycle.status"] == "failure"
    assert spans[0].attributes["floe.error.type"] == "ValueError"
    assert metrics.counters[0]["name"] == "floe.plugin.lifecycle.failures"
    assert metrics.counters[0]["labels"]["floe.plugin.lifecycle.status"] == "failure"


def test_plugin_lifecycle_startup_success_uses_telemetry_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations: list[_FakeLifecycleObservation] = []

    monkeypatch.setattr(
        "floe_core.plugins.lifecycle.observe_plugin_lifecycle",
        _fake_observe_plugin_lifecycle(observations),
    )

    lifecycle = PluginLifecycle(_FakeLoader({(PluginType.COMPUTE, "startup"): _StartupPlugin()}))

    lifecycle.activate_plugin(PluginType.COMPUTE, "startup")

    assert observations[0].call == {
        "plugin_type": "COMPUTE",
        "plugin_name": "startup",
        "plugin_version": "1.0.0",
        "floe_api_version": "1.0",
        "phase": "startup",
        "extra": {"timeout": 30.0},
    }
    assert observations[0].finishes == [{"status": "success"}]


def test_plugin_lifecycle_startup_failure_records_failure_and_preserves_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations: list[_FakeLifecycleObservation] = []

    monkeypatch.setattr(
        "floe_core.plugins.lifecycle.observe_plugin_lifecycle",
        _fake_observe_plugin_lifecycle(observations),
    )

    lifecycle = PluginLifecycle(
        _FakeLoader({(PluginType.COMPUTE, "failing"): _FailingStartupPlugin()})
    )

    with pytest.raises(PluginStartupError) as exc_info:
        lifecycle.activate_plugin(PluginType.COMPUTE, "failing")

    assert isinstance(exc_info.value.cause, ValueError)
    assert observations[0].call == {
        "plugin_type": "COMPUTE",
        "plugin_name": "failing",
        "plugin_version": "1.0.0",
        "floe_api_version": "1.0",
        "phase": "startup",
        "extra": {"timeout": 30.0},
    }
    assert observations[0].finishes == [{"status": "failure", "error_type": "ValueError"}]


def test_plugin_lifecycle_health_check_degraded_records_actual_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations: list[_FakeLifecycleObservation] = []

    monkeypatch.setattr(
        "floe_core.plugins.lifecycle.observe_plugin_lifecycle",
        _fake_observe_plugin_lifecycle(observations),
    )

    lifecycle = PluginLifecycle(
        _FakeLoader({(PluginType.COMPUTE, "degraded"): _DegradedHealthPlugin()})
    )

    results = lifecycle.health_check_all()

    assert results["COMPUTE:degraded"].state == HealthState.DEGRADED
    assert observations[0].call == {
        "plugin_type": "COMPUTE",
        "plugin_name": "degraded",
        "plugin_version": "1.0.0",
        "floe_api_version": "1.0",
        "phase": "health_check",
        "extra": {"timeout": 5.0},
    }
    assert observations[0].finishes == [{"status": "degraded"}]


def test_plugin_lifecycle_shutdown_failure_records_failure_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations: list[_FakeLifecycleObservation] = []

    monkeypatch.setattr(
        "floe_core.plugins.lifecycle.observe_plugin_lifecycle",
        _fake_observe_plugin_lifecycle(observations),
    )

    failing = _FailingShutdownPlugin()
    healthy = _ShutdownPlugin("healthy")
    lifecycle = PluginLifecycle(
        _FakeLoader(
            {
                (PluginType.COMPUTE, "failing-shutdown"): failing,
                (PluginType.CATALOG, "healthy"): healthy,
            }
        )
    )
    lifecycle.activate_plugin(PluginType.COMPUTE, "failing-shutdown")
    lifecycle.activate_plugin(PluginType.CATALOG, "healthy")

    results = lifecycle.shutdown_all()

    assert isinstance(results["COMPUTE:failing-shutdown"], RuntimeError)
    assert results["CATALOG:healthy"] is None
    shutdown_observations = [obs for obs in observations if obs.call["phase"] == "shutdown"]
    assert {
        "plugin_type": "COMPUTE",
        "plugin_name": "failing-shutdown",
        "plugin_version": "1.0.0",
        "floe_api_version": "1.0",
        "phase": "shutdown",
        "extra": {"timeout": 30.0},
    } in [obs.call for obs in shutdown_observations]
    assert {"status": "failure", "error_type": "RuntimeError"} in [
        finish for obs in shutdown_observations for finish in obs.finishes
    ]


class _FakeSpan:
    def __init__(self, *, name: str, attributes: dict[str, Any]) -> None:
        self.name = name
        self.attributes = attributes.copy()

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        self.attributes[key] = value


class _FakeMetricRecorder:
    def __init__(self) -> None:
        self.histograms: list[dict[str, Any]] = []
        self.counters: list[dict[str, Any]] = []

    def record_histogram(
        self,
        name: str,
        value: int | float,
        *,
        labels: dict[str, Any] | None = None,
        description: str | None = None,
        unit: str | None = None,
    ) -> None:
        self.histograms.append(
            {
                "name": name,
                "value": value,
                "labels": labels,
                "description": description,
                "unit": unit,
            }
        )

    def increment(
        self,
        name: str,
        value: int = 1,
        *,
        labels: dict[str, Any] | None = None,
        description: str | None = None,
        unit: str | None = None,
    ) -> None:
        self.counters.append(
            {
                "name": name,
                "value": value,
                "labels": labels,
                "description": description,
                "unit": unit,
            }
        )


class _FakeLifecycleObservation:
    def __init__(self, call: dict[str, Any]) -> None:
        self.call = call
        self.finishes: list[dict[str, str]] = []

    def finish(
        self,
        *,
        status: str,
        error_type: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        finish = {"status": status}
        if error_type is not None:
            finish["error_type"] = error_type
        self.finishes.append(finish)


def _fake_observe_plugin_lifecycle(
    observations: list[_FakeLifecycleObservation],
) -> Any:
    @contextmanager
    def fake_observe_plugin_lifecycle(**kwargs: Any) -> Iterator[_FakeLifecycleObservation]:
        observation = _FakeLifecycleObservation(kwargs)
        observations.append(observation)
        yield observation

    return fake_observe_plugin_lifecycle


class _FakeLoader:
    def __init__(self, loaded: dict[tuple[PluginType, str], PluginMetadata]) -> None:
        self._loaded = loaded

    def get(self, plugin_type: PluginType, name: str) -> PluginMetadata:
        return self._loaded[(plugin_type, name)]

    def get_loaded(self) -> dict[tuple[PluginType, str], PluginMetadata]:
        return self._loaded


class _BasePlugin(PluginMetadata):
    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"


class _StartupPlugin(_BasePlugin):
    @property
    def name(self) -> str:
        return "startup"


class _FailingStartupPlugin(_BasePlugin):
    @property
    def name(self) -> str:
        return "failing"

    def startup(self) -> None:
        raise ValueError("startup failed")


class _DegradedHealthPlugin(_BasePlugin):
    @property
    def name(self) -> str:
        return "degraded"

    def health_check(self, timeout: float | None = None) -> HealthStatus:
        return HealthStatus(state=HealthState.DEGRADED, message="Connection pool low")


class _ShutdownPlugin(_BasePlugin):
    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    @property
    def name(self) -> str:
        return self._name


class _FailingShutdownPlugin(_BasePlugin):
    @property
    def name(self) -> str:
        return "failing-shutdown"

    def shutdown(self) -> None:
        raise RuntimeError("shutdown failed")
