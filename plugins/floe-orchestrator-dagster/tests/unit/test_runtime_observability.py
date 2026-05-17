"""Unit tests for Dagster runtime observability envelope."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from floe_core.telemetry.context import ObservabilityContext
from opentelemetry.trace import StatusCode


def _context() -> ObservabilityContext:
    return ObservabilityContext(
        product_name="customer-360",
        product_version="1.2.3",
        environment="dev",
        namespace="analytics",
        run_id="run-123",
        asset_key="orders_daily",
        plugin_type="orchestrator",
        plugin_name="dagster",
    )


def _captured_span_attrs(span: MagicMock) -> dict[str, Any]:
    return {call.args[0]: call.args[1] for call in span.set_attribute.call_args_list}


def _run_fake_dagster_asset(fake_context: Any) -> str:
    from floe_orchestrator_dagster.runtime_observability import (
        observability_context_from_dagster,
        run_observed_asset,
    )

    return run_observed_asset(
        observability_context_from_dagster(
            fake_context,
            asset_key="",
            stage="transform",
            table_name="analytics.orders_daily",
        ),
        "materialize_orders",
        lambda: "ok",
    )


def test_observed_asset_success_records_context_span_logs_and_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from floe_orchestrator_dagster.runtime_observability import run_observed_asset

    span = MagicMock()
    tracer = MagicMock()
    tracer.start_as_current_span.return_value.__enter__.return_value = span
    tracer.start_as_current_span.return_value.__exit__.return_value = None
    monkeypatch.setattr(
        "floe_orchestrator_dagster.runtime_observability.get_tracer",
        lambda _name: tracer,
    )

    metric_recorder = MagicMock()
    metric_recorder_cls = MagicMock(return_value=metric_recorder)
    monkeypatch.setattr(
        "floe_orchestrator_dagster.runtime_observability.MetricRecorder",
        metric_recorder_cls,
    )
    log = MagicMock()
    monkeypatch.setattr("floe_orchestrator_dagster.runtime_observability.logger", log)

    result = run_observed_asset(_context(), "materialize_orders", lambda: "ok")

    assert result == "ok"
    tracer.start_as_current_span.assert_called_once_with(
        "materialize_orders",
        attributes={
            "floe.product.name": "customer-360",
            "floe.product.version": "1.2.3",
            "floe.environment": "dev",
            "floe.namespace": "analytics",
            "floe.run.id": "run-123",
            "floe.asset.key": "orders_daily",
            "floe.plugin.type": "orchestrator",
            "floe.plugin.name": "dagster",
        },
        record_exception=False,
        set_status_on_exception=False,
    )
    attrs = _captured_span_attrs(span)
    assert attrs["floe.product.name"] == "customer-360"
    assert attrs["floe.run.id"] == "run-123"
    assert attrs["floe.asset.key"] == "orders_daily"
    assert attrs["floe.plugin.type"] == "orchestrator"
    assert attrs["floe.status"] == "success"
    span.set_status.assert_not_called()
    metric_recorder.increment.assert_called_once_with(
        "floe.asset.materializations",
        labels={
            "floe.product.name": "customer-360",
            "floe.environment": "dev",
            "floe.namespace": "analytics",
            "floe.plugin.type": "orchestrator",
            "floe.plugin.name": "dagster",
            "floe.status": "success",
        },
        description="Dagster asset materializations",
        unit="1",
    )
    completed_log = log.info.call_args_list[-1]
    assert completed_log.args == ("floe_asset_completed",)
    assert completed_log.kwargs["floe.product.name"] == "customer-360"
    assert completed_log.kwargs["floe.run.id"] == "run-123"
    assert completed_log.kwargs["floe.asset.key"] == "orders_daily"
    assert completed_log.kwargs["floe.plugin.type"] == "orchestrator"
    assert completed_log.kwargs["floe.status"] == "success"


def test_fake_dagster_context_fields_flow_through_observed_asset_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    span = MagicMock()
    tracer = MagicMock()
    tracer.start_as_current_span.return_value.__enter__.return_value = span
    tracer.start_as_current_span.return_value.__exit__.return_value = None
    monkeypatch.setattr(
        "floe_orchestrator_dagster.runtime_observability.get_tracer",
        lambda _name: tracer,
    )

    metric_recorder = MagicMock()
    monkeypatch.setattr(
        "floe_orchestrator_dagster.runtime_observability.MetricRecorder",
        MagicMock(return_value=metric_recorder),
    )
    log = MagicMock()
    monkeypatch.setattr("floe_orchestrator_dagster.runtime_observability.logger", log)

    fake_context = SimpleNamespace(
        run=SimpleNamespace(
            run_id="dagster-run-456",
            tags={
                "floe.product.name": "customer-360",
                "floe.product.version": "2.0.0",
                "deployment.environment": "staging",
                "floe.namespace": "finance",
            },
        ),
        asset_key=SimpleNamespace(path=["analytics", "orders_daily"]),
    )

    result = _run_fake_dagster_asset(fake_context)

    assert result == "ok"
    attrs = _captured_span_attrs(span)
    assert attrs["floe.product.name"] == "customer-360"
    assert attrs["floe.product.version"] == "2.0.0"
    assert attrs["floe.environment"] == "staging"
    assert attrs["floe.namespace"] == "finance"
    assert attrs["floe.run.id"] == "dagster-run-456"
    assert attrs["floe.asset.key"] == "analytics.orders_daily"
    assert attrs["floe.stage"] == "transform"
    assert attrs["floe.table.name"] == "analytics.orders_daily"
    assert attrs["floe.plugin.type"] == "orchestrator"
    assert attrs["floe.plugin.name"] == "dagster"
    assert attrs["floe.status"] == "success"
    metric_recorder.increment.assert_called_once_with(
        "floe.asset.materializations",
        labels={
            "floe.product.name": "customer-360",
            "floe.environment": "staging",
            "floe.namespace": "finance",
            "floe.stage": "transform",
            "floe.plugin.type": "orchestrator",
            "floe.plugin.name": "dagster",
            "floe.status": "success",
        },
        description="Dagster asset materializations",
        unit="1",
    )
    completed_log = log.info.call_args_list[-1]
    assert completed_log.args == ("floe_asset_completed",)
    assert completed_log.kwargs["floe.product.name"] == "customer-360"
    assert completed_log.kwargs["floe.product.version"] == "2.0.0"
    assert completed_log.kwargs["floe.environment"] == "staging"
    assert completed_log.kwargs["floe.namespace"] == "finance"
    assert completed_log.kwargs["floe.run.id"] == "dagster-run-456"
    assert completed_log.kwargs["floe.asset.key"] == "analytics.orders_daily"
    assert completed_log.kwargs["floe.stage"] == "transform"
    assert completed_log.kwargs["floe.table.name"] == "analytics.orders_daily"


def test_observed_asset_failure_records_context_span_logs_and_failure_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from floe_orchestrator_dagster.runtime_observability import run_observed_asset

    span = MagicMock()
    tracer = MagicMock()
    tracer.start_as_current_span.return_value.__enter__.return_value = span
    tracer.start_as_current_span.return_value.__exit__.return_value = None
    monkeypatch.setattr(
        "floe_orchestrator_dagster.runtime_observability.get_tracer",
        lambda _name: tracer,
    )

    metric_recorder = MagicMock()
    monkeypatch.setattr(
        "floe_orchestrator_dagster.runtime_observability.MetricRecorder",
        MagicMock(return_value=metric_recorder),
    )
    log = MagicMock()
    monkeypatch.setattr("floe_orchestrator_dagster.runtime_observability.logger", log)

    error = RuntimeError("dbt failed")

    with pytest.raises(RuntimeError, match="dbt failed"):
        run_observed_asset(
            _context(),
            "materialize_orders",
            lambda: (_ for _ in ()).throw(error),
        )

    attrs = _captured_span_attrs(span)
    assert attrs["floe.product.name"] == "customer-360"
    assert attrs["floe.run.id"] == "run-123"
    assert attrs["floe.asset.key"] == "orders_daily"
    assert attrs["floe.plugin.type"] == "orchestrator"
    assert attrs["floe.status"] == "failure"
    span.record_exception.assert_not_called()
    span.add_event.assert_called_once_with(
        "exception",
        {
            "exception.type": "RuntimeError",
            "exception.message": "dbt failed",
            "exception.escaped": True,
        },
    )
    status = span.set_status.call_args.args[0]
    assert status.status_code is StatusCode.ERROR
    metric_recorder.increment.assert_called_once_with(
        "floe.asset.failures",
        labels={
            "floe.product.name": "customer-360",
            "floe.environment": "dev",
            "floe.namespace": "analytics",
            "floe.plugin.type": "orchestrator",
            "floe.plugin.name": "dagster",
            "floe.status": "failure",
        },
        description="Dagster asset failures",
        unit="1",
    )
    failed_log = log.error.call_args
    assert failed_log.args == ("floe_asset_failed",)
    assert failed_log.kwargs["floe.product.name"] == "customer-360"
    assert failed_log.kwargs["floe.run.id"] == "run-123"
    assert failed_log.kwargs["floe.asset.key"] == "orders_daily"
    assert failed_log.kwargs["floe.plugin.type"] == "orchestrator"
    assert failed_log.kwargs["floe.status"] == "failure"
    assert failed_log.kwargs["error_type"] == "RuntimeError"


def test_observed_asset_failure_sanitizes_exception_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from floe_orchestrator_dagster.runtime_observability import run_observed_asset

    span = MagicMock()
    tracer = MagicMock()
    tracer.start_as_current_span.return_value.__enter__.return_value = span
    tracer.start_as_current_span.return_value.__exit__.return_value = None
    monkeypatch.setattr(
        "floe_orchestrator_dagster.runtime_observability.get_tracer",
        lambda _name: tracer,
    )
    monkeypatch.setattr(
        "floe_orchestrator_dagster.runtime_observability.MetricRecorder",
        MagicMock(return_value=MagicMock()),
    )
    log = MagicMock()
    monkeypatch.setattr("floe_orchestrator_dagster.runtime_observability.logger", log)

    error = RuntimeError("dbt failed password=secret123")  # pragma: allowlist secret

    with pytest.raises(RuntimeError, match="password=secret123"):  # pragma: allowlist secret
        run_observed_asset(
            _context(),
            "materialize_orders",
            lambda: (_ for _ in ()).throw(error),
        )

    span.record_exception.assert_not_called()
    emitted_values = repr(
        {
            "events": span.add_event.call_args_list,
            "attributes": span.set_attribute.call_args_list,
            "status": span.set_status.call_args_list,
            "logs": log.method_calls,
        }
    )
    assert "secret123" not in emitted_values  # pragma: allowlist secret
    assert "password=secret123" not in emitted_values  # pragma: allowlist secret
    assert "RuntimeError" in emitted_values
