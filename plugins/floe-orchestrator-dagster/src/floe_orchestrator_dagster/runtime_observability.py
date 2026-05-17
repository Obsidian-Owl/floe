"""Runtime observability envelope for Dagster asset execution."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any, TypeVar, cast

import structlog
from floe_core.telemetry.context import ObservabilityContext
from floe_core.telemetry.conventions import FLOE_STATUS
from floe_core.telemetry.metrics import MetricRecorder
from floe_core.telemetry.sanitization import sanitize_error_message
from floe_core.telemetry.tracer_factory import get_tracer
from opentelemetry.trace import Status, StatusCode

T = TypeVar("T")

TRACER_NAME = "floe.orchestrator.dagster.runtime"
METER_NAME = "floe.orchestrator.dagster.runtime"
ASSET_MATERIALIZATIONS_METRIC = "floe.asset.materializations"
ASSET_FAILURES_METRIC = "floe.asset.failures"

logger = structlog.get_logger(__name__)


def run_observed_asset(
    context: ObservabilityContext,
    operation_name: str,
    fn: Callable[[], T],
    *,
    yield_events: bool = False,
    telemetry_initializer: Callable[[], None] | None = None,
    telemetry_finalizer: Callable[[], None] | None = None,
) -> T:
    """Run a Dagster asset body inside a shared Floe observability envelope."""
    if yield_events:
        return cast(
            T,
            _run_observed_asset_events(
                context,
                operation_name,
                fn,
                telemetry_initializer=telemetry_initializer,
                telemetry_finalizer=telemetry_finalizer,
            ),
        )

    if telemetry_initializer is not None:
        telemetry_initializer()
    try:
        with _observe_asset(context, operation_name):
            return fn()
    finally:
        if telemetry_finalizer is not None:
            telemetry_finalizer()


def _run_observed_asset_events(
    context: ObservabilityContext,
    operation_name: str,
    fn: Callable[[], T],
    *,
    telemetry_initializer: Callable[[], None] | None = None,
    telemetry_finalizer: Callable[[], None] | None = None,
) -> Iterator[Any]:
    """Yield generator asset events while observing the full iteration."""
    if telemetry_initializer is not None:
        telemetry_initializer()
    try:
        with _observe_asset(context, operation_name):
            # Dagster exhausts or closes generator asset iterators, so this
            # finally block flushes telemetry before the run pod exits.
            yield from cast(Iterator[Any], fn())
    finally:
        if telemetry_finalizer is not None:
            telemetry_finalizer()


@contextmanager
def _observe_asset(
    context: ObservabilityContext,
    operation_name: str,
) -> Iterator[None]:
    """Observe one asset execution, recording final status once."""
    tracer = get_tracer(TRACER_NAME)
    metrics = MetricRecorder(name=METER_NAME)
    span_attributes = context.to_span_attributes()

    with tracer.start_as_current_span(
        operation_name,
        attributes=span_attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        logger.info("floe_asset_started", **context.to_log_fields())
        try:
            yield
        except Exception as exc:
            sanitized_message = sanitize_error_message(str(exc))
            span.set_attribute(FLOE_STATUS, "failure")
            span.set_attribute("exception.type", type(exc).__name__)
            span.set_attribute("exception.message", sanitized_message)
            span.add_event(
                "exception",
                {
                    "exception.type": type(exc).__name__,
                    "exception.message": sanitized_message,
                    "exception.escaped": True,
                },
            )
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            _record_metric(
                metrics,
                ASSET_FAILURES_METRIC,
                labels=context.to_metric_labels(status="failure"),
                description="Dagster asset failures",
            )
            logger.error(
                "floe_asset_failed",
                **context.to_log_fields(),
                **{FLOE_STATUS: "failure"},
                error_type=type(exc).__name__,
            )
            raise

        span.set_attribute(FLOE_STATUS, "success")
        _record_metric(
            metrics,
            ASSET_MATERIALIZATIONS_METRIC,
            labels=context.to_metric_labels(status="success"),
            description="Dagster asset materializations",
        )
        logger.info(
            "floe_asset_completed",
            **context.to_log_fields(),
            **{FLOE_STATUS: "success"},
        )


def observability_context_from_dagster(
    dagster_context: Any,
    *,
    asset_key: str,
    stage: str,
    product_name: str | None = None,
    product_version: str | None = None,
    environment: str | None = None,
    namespace: str | None = None,
    table_name: str | None = None,
    plugin_type: str = "orchestrator",
    plugin_name: str = "dagster",
    lineage_namespace: str | None = None,
) -> ObservabilityContext:
    """Build secret-free runtime context from Dagster run metadata."""
    tags = _run_tags(dagster_context)
    resolved_asset_key = asset_key or _dagster_asset_key(dagster_context) or "unknown"

    return ObservabilityContext(
        product_name=(
            product_name
            or _first_tag(tags, "floe.product.name", "floe_product_name", "product_name")
            or _env("FLOE_PRODUCT_NAME", "OTEL_SERVICE_NAME")
            or resolved_asset_key
        ),
        product_version=(
            product_version
            or _first_tag(tags, "floe.product.version", "floe_product_version", "product_version")
            or _env("FLOE_PRODUCT_VERSION")
            or "unknown"
        ),
        environment=(
            environment
            or _first_tag(tags, "floe.environment", "deployment.environment", "environment")
            or _env("FLOE_ENVIRONMENT", "DEPLOYMENT_ENVIRONMENT")
            or "dev"
        ),
        namespace=(
            namespace
            or _first_tag(tags, "floe.namespace", "floe_namespace", "namespace")
            or _env("FLOE_NAMESPACE")
            or "default"
        ),
        run_id=_dagster_run_id(dagster_context),
        asset_key=resolved_asset_key,
        stage=stage,
        table_name=table_name,
        plugin_type=plugin_type,
        plugin_name=plugin_name,
        lineage_namespace=lineage_namespace,
    )


def _record_metric(
    metrics: MetricRecorder,
    name: str,
    *,
    labels: dict[str, str],
    description: str,
) -> None:
    """Record a runtime metric without letting telemetry fail asset work."""
    try:
        metrics.increment(
            name,
            labels=labels,
            description=description,
            unit="1",
        )
    except Exception as exc:  # pragma: no cover - defensive telemetry isolation
        logger.debug(
            "floe_asset_metric_failed",
            metric_name=name,
            error_type=type(exc).__name__,
        )


def _run_tags(dagster_context: Any) -> Mapping[str, str]:
    try:
        run = getattr(dagster_context, "run", None)
        tags = getattr(run, "tags", None)
    except Exception:
        return {}
    if isinstance(tags, Mapping):
        return tags
    return {}


def _first_tag(tags: Mapping[str, str], *keys: str) -> str | None:
    for key in keys:
        value = tags.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _env(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def _dagster_run_id(dagster_context: Any) -> str | None:
    try:
        run = getattr(dagster_context, "run", None)
        run_id = getattr(run, "run_id", None)
    except Exception:
        return None
    return run_id if isinstance(run_id, str) and run_id else None


def _dagster_asset_key(dagster_context: Any) -> str | None:
    try:
        raw_asset_key = getattr(dagster_context, "asset_key", None)
    except Exception:
        return None
    path = getattr(raw_asset_key, "path", None)
    if isinstance(path, list | tuple) and path:
        return ".".join(str(part) for part in path)
    if isinstance(raw_asset_key, str) and raw_asset_key:
        return raw_asset_key
    return None


__all__ = [
    "ASSET_FAILURES_METRIC",
    "ASSET_MATERIALIZATIONS_METRIC",
    "METER_NAME",
    "TRACER_NAME",
    "observability_context_from_dagster",
    "run_observed_asset",
]
