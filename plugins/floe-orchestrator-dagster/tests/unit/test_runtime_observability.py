"""Unit tests for Dagster runtime observability envelope."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import structlog
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

    with structlog.testing.capture_logs() as logs:
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
    assert logs[-1]["event"] == "floe_asset_completed"
    assert logs[-1]["floe.product.name"] == "customer-360"
    assert logs[-1]["floe.run.id"] == "run-123"
    assert logs[-1]["floe.asset.key"] == "orders_daily"
    assert logs[-1]["floe.plugin.type"] == "orchestrator"
    assert logs[-1]["floe.status"] == "success"


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

    with structlog.testing.capture_logs() as logs:
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
    assert logs[-1]["event"] == "floe_asset_completed"
    assert logs[-1]["floe.product.name"] == "customer-360"
    assert logs[-1]["floe.product.version"] == "2.0.0"
    assert logs[-1]["floe.environment"] == "staging"
    assert logs[-1]["floe.namespace"] == "finance"
    assert logs[-1]["floe.run.id"] == "dagster-run-456"
    assert logs[-1]["floe.asset.key"] == "analytics.orders_daily"
    assert logs[-1]["floe.stage"] == "transform"
    assert logs[-1]["floe.table.name"] == "analytics.orders_daily"


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

    error = RuntimeError("dbt failed")

    with structlog.testing.capture_logs() as logs:
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
    span.record_exception.assert_called_once_with(error)
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
    assert logs[-1]["event"] == "floe_asset_failed"
    assert logs[-1]["floe.product.name"] == "customer-360"
    assert logs[-1]["floe.run.id"] == "run-123"
    assert logs[-1]["floe.asset.key"] == "orders_daily"
    assert logs[-1]["floe.plugin.type"] == "orchestrator"
    assert logs[-1]["floe.status"] == "failure"
    assert logs[-1]["error_type"] == "RuntimeError"
