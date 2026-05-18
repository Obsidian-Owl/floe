"""Customer 360 observability proof helpers.

The helpers in this module query backend APIs directly and classify evidence
against an explicit product/run/table context. They are intentionally backend
oriented so data product code does not need to know how Jaeger, Loki,
Prometheus, or Marquez expose evidence.
"""

from __future__ import annotations

import json
import os
import re
import signal
import threading
import time
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from floe_core.telemetry.conventions import FLOE_PRODUCT_NAME, FLOE_RUN_ID

from testing.fixtures.polling import wait_for_condition

ASSET_MATERIALIZATIONS_METRIC = "floe_asset_materializations_total"
ASSET_FAILURES_METRIC = "floe_asset_failures_total"
METRIC_ASSET_KEY_LABEL = "floe_asset_key"
METRIC_PLUGIN_NAME_LABEL = "floe_plugin_name"
METRIC_PRODUCT_NAME_LABEL = "floe_product_name"
METRIC_STATUS_LABEL = "floe_status"


class EvidenceStatus(str, Enum):
    """Classification for backend evidence checks."""

    PASS = "pass"
    PLATFORM_SERVICE_FAILURE = "platform_service_failure"
    BACKEND_UNREACHABLE = "backend_unreachable"
    NO_FRESH_EVIDENCE = "no_fresh_evidence"
    STALE_EVIDENCE = "stale_evidence"
    WRONG_CONTEXT = "wrong_context"
    PRODUCT_FAILURE = "product_failure"
    DASHBOARD_DATASOURCE_DRIFT = "dashboard_datasource_drift"
    CONTRACT_GAP = "contract_gap"


FAILURE_STATUSES = {"FAILURE", "FAILED", "ERROR", "CANCELED", "CANCELLED"}
SUCCESS_STATUSES = {"SUCCESS", "SUCCEEDED", "COMPLETED", "OK", "PASS", "PASSED"}


def _env_url(
    primary_env: str,
    *,
    fallback_env: str | None = None,
    host_env: str | None = None,
    default_port: int | None = None,
    default: str,
) -> str:
    """Resolve a backend URL from explicit demo env or in-cluster service env."""
    explicit = _blank_to_none(os.environ.get(primary_env))
    if explicit:
        return explicit

    if fallback_env:
        fallback = _blank_to_none(os.environ.get(fallback_env))
        if fallback:
            return fallback

    if host_env and default_port is not None:
        host = _blank_to_none(os.environ.get(host_env))
        if host:
            if host.startswith(("http://", "https://")):
                return host
            return f"http://{host}:{default_port}"

    return default


@dataclass(frozen=True)
class ObservabilityContext:
    """Context used to classify backend evidence."""

    product: str
    run_id: str
    table: str | None = None
    freshness_window_seconds: float = 1_800.0
    now_epoch_seconds: float | None = None

    @property
    def freshness_cutoff_epoch_seconds(self) -> float:
        """Return the oldest timestamp accepted as fresh."""
        now = self.now_epoch_seconds if self.now_epoch_seconds is not None else time.time()
        return now - self.freshness_window_seconds


@dataclass(frozen=True)
class EvidenceRecord:
    """Single observability backend record."""

    payload: Mapping[str, Any]
    timestamp_epoch_seconds: float | None = None


@dataclass(frozen=True)
class EvidenceResult:
    """Classified backend evidence."""

    backend: str
    status: EvidenceStatus
    query: str
    message: str
    records: tuple[EvidenceRecord, ...] = ()
    url: str | None = None
    diagnostics: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return whether the backend produced fresh evidence for the context."""
        return self.status is EvidenceStatus.PASS

    @property
    def evidence_count(self) -> int:
        """Return the number of records considered by this check."""
        return len(self.records)


@dataclass(frozen=True)
class Customer360ObservabilityConfig:
    """Configuration for Customer 360 observability proof validation."""

    product: str = "customer-360"
    service: str = "customer-360"
    table: str = "mart_customer_360"
    namespace: str = "customer-360"
    job_name: str = "customer-360"
    metric_status: str = "success"
    metric_plugin: str = ".+"
    dagster_url: str = "http://localhost:3100"
    jaeger_url: str = "http://localhost:16686"
    loki_url: str = "http://localhost:3101"
    prometheus_url: str = "http://localhost:9090"
    marquez_url: str = "http://localhost:5100"
    run_id: str | None = None
    run_evidence_file: Path | None = Path(".customer360-run.env")
    freshness_window_seconds: float = 1_800.0
    timeout_seconds: float = 30.0
    evidence_poll_timeout_seconds: float = 30.0
    evidence_poll_interval_seconds: float = 2.0

    @classmethod
    def from_env(cls) -> Customer360ObservabilityConfig:
        """Build config from the demo validation environment."""
        return cls(
            product=os.environ.get("FLOE_DEMO_PRODUCT", "customer-360"),
            service=os.environ.get("FLOE_DEMO_TRACE_SERVICE", "customer-360"),
            table=os.environ.get("FLOE_DEMO_CUSTOMER360_TABLE", "mart_customer_360"),
            namespace=os.environ.get("FLOE_DEMO_LINEAGE_NAMESPACE", "customer-360"),
            job_name=os.environ.get("FLOE_DEMO_LINEAGE_JOB", "customer-360"),
            metric_status=os.environ.get("FLOE_DEMO_METRIC_STATUS", "success"),
            metric_plugin=os.environ.get("FLOE_DEMO_METRIC_PLUGIN", ".+"),
            dagster_url=_env_url(
                "FLOE_DEMO_DAGSTER_URL",
                fallback_env="DAGSTER_URL",
                default="http://localhost:3100",
            ),
            jaeger_url=_env_url(
                "FLOE_DEMO_JAEGER_URL",
                fallback_env="JAEGER_URL",
                default="http://localhost:16686",
            ),
            loki_url=_env_url(
                "FLOE_DEMO_LOKI_URL",
                host_env="LOKI_HOST",
                default_port=3100,
                default="http://localhost:3101",
            ),
            prometheus_url=os.environ.get("FLOE_DEMO_PROMETHEUS_URL")
            or _env_url(
                "PROMETHEUS_URL",
                host_env="PROMETHEUS_HOST",
                default_port=9090,
                default="http://localhost:9090",
            ),
            marquez_url=_env_url(
                "FLOE_DEMO_MARQUEZ_URL",
                fallback_env="MARQUEZ_URL",
                host_env="MARQUEZ_HOST",
                default_port=5000,
                default="http://localhost:5100",
            ),
            run_id=_blank_to_none(os.environ.get("FLOE_DEMO_RUN_ID")),
            run_evidence_file=Path(
                os.environ.get("FLOE_DEMO_RUN_EVIDENCE_FILE", ".customer360-run.env")
            ),
            freshness_window_seconds=float(
                os.environ.get("FLOE_DEMO_OBSERVABILITY_FRESHNESS_SECONDS", "1800")
            ),
            timeout_seconds=float(os.environ.get("FLOE_DEMO_COMMAND_TIMEOUT_SECONDS", "30")),
            evidence_poll_timeout_seconds=float(
                os.environ.get("FLOE_DEMO_OBSERVABILITY_POLL_TIMEOUT_SECONDS", "30")
            ),
            evidence_poll_interval_seconds=float(
                os.environ.get("FLOE_DEMO_OBSERVABILITY_POLL_INTERVAL_SECONDS", "2")
            ),
        )


@dataclass(frozen=True)
class ObservabilityProofResult:
    """Aggregate Customer 360 observability proof result."""

    run_id: str | None
    evidence: dict[str, str]
    failures: list[str]
    backend_results: tuple[EvidenceResult, ...]

    @property
    def ok(self) -> bool:
        """Return whether every required backend produced fresh evidence."""
        return not self.failures


TRACE_CATEGORY_TERMS: dict[str, tuple[tuple[str, ...], ...]] = {
    "run_root_span": (("customer-360", "run"), ("customer_360", "run")),
    "dagster_asset_spans": (("dagster", "asset"), ("__asset_job",)),
    "dbt_model_spans": (("dbt", "model"), ("mart_customer_360",)),
    "ingestion_spans": (("ingestion",), ("dlt",), ("raw_customers",), ("raw_transactions",)),
    "catalog_storage_iceberg_spans": (("iceberg",), ("catalog",), ("storage",)),
}


def classify_evidence_records(
    *,
    backend: str,
    query: str,
    context: ObservabilityContext,
    records: Sequence[EvidenceRecord] | None,
    backend_error: str | None = None,
    url: str | None = None,
) -> EvidenceResult:
    """Classify backend records against a product/run/table context."""
    if backend_error:
        return EvidenceResult(
            backend=backend,
            status=EvidenceStatus.BACKEND_UNREACHABLE,
            query=query,
            url=url,
            message=f"{backend} backend is unreachable: {backend_error}",
        )

    record_tuple = tuple(records or ())
    if not record_tuple:
        return EvidenceResult(
            backend=backend,
            status=EvidenceStatus.NO_FRESH_EVIDENCE,
            query=query,
            url=url,
            message=(
                f"{backend} backend returned no evidence for {context.product}/{context.run_id}"
            ),
            records=record_tuple,
        )

    matching_context = [
        record for record in record_tuple if _record_matches_context(record, context)
    ]
    if not matching_context:
        expected = [context.product, context.run_id]
        if context.table:
            expected.append(context.table)
        return EvidenceResult(
            backend=backend,
            status=EvidenceStatus.WRONG_CONTEXT,
            query=query,
            url=url,
            message=(
                f"{backend} backend returned evidence, but none matched context "
                f"{' / '.join(expected)}"
            ),
            records=record_tuple,
            diagnostics={"expected_context": " / ".join(expected)},
        )

    failed_records = [record for record in matching_context if _record_has_failure_status(record)]
    if failed_records:
        return EvidenceResult(
            backend=backend,
            status=EvidenceStatus.PRODUCT_FAILURE,
            query=query,
            url=url,
            message=f"Product execution failed according to {backend} evidence",
            records=tuple(failed_records),
        )

    fresh_records = [
        record
        for record in matching_context
        if record.timestamp_epoch_seconds is None
        or record.timestamp_epoch_seconds >= context.freshness_cutoff_epoch_seconds
    ]
    if not fresh_records:
        newest = max(
            (
                record.timestamp_epoch_seconds
                for record in matching_context
                if record.timestamp_epoch_seconds is not None
            ),
            default=None,
        )
        diagnostics = {}
        if newest is not None:
            diagnostics["newest_epoch_seconds"] = f"{newest:.3f}"
            diagnostics["freshness_cutoff_epoch_seconds"] = (
                f"{context.freshness_cutoff_epoch_seconds:.3f}"
            )
        return EvidenceResult(
            backend=backend,
            status=EvidenceStatus.STALE_EVIDENCE,
            query=query,
            url=url,
            message=f"{backend} backend returned only stale evidence for {context.run_id}",
            records=tuple(matching_context),
            diagnostics=diagnostics,
        )

    return EvidenceResult(
        backend=backend,
        status=EvidenceStatus.PASS,
        query=query,
        url=url,
        message=f"{backend} backend returned fresh evidence for {context.run_id}",
        records=tuple(fresh_records),
    )


def read_run_id_from_evidence_file(path: Path | None) -> str | None:
    """Read ``dagster.run_id`` from the Customer 360 run evidence file."""
    if path is None or not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() in {"dagster.run_id", "run_id", "FLOE_DEMO_RUN_ID"}:
            run_id = value.strip()
            if run_id:
                return run_id
    return None


def query_dagster_run(
    *,
    dagster_url: str,
    product: str,
    job_name: str,
    run_id: str | None,
    freshness_window_seconds: float,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> EvidenceResult:
    """Query Dagster for the Customer 360 run used as proof context."""
    url = _join_url(dagster_url, "graphql")
    query = f"dagster run product={product} job={job_name} run_id={run_id or '<latest>'}"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        if run_id:
            response = http_client.post(
                url,
                json={"query": _DAGSTER_RUN_QUERY, "variables": {"runId": run_id}},
            )
            response.raise_for_status()
            payload = response.json()
            run = payload.get("data", {}).get("runOrError")
        else:
            response = http_client.post(url, json={"query": _DAGSTER_RECENT_RUNS_QUERY})
            response.raise_for_status()
            payload = response.json()
            runs = payload.get("data", {}).get("runsOrError", {}).get("results", [])
            run = _select_latest_product_run(runs, product=product, job_name=job_name)
        if not isinstance(run, dict):
            records: list[EvidenceRecord] = []
        else:
            records = [_dagster_run_record(run, product=product)]
    except Exception as exc:  # noqa: BLE001 - validation must report backend failure.
        context = ObservabilityContext(
            product=product,
            run_id=run_id or "<unknown>",
            freshness_window_seconds=freshness_window_seconds,
        )
        return classify_evidence_records(
            backend="dagster",
            query=query,
            context=context,
            records=None,
            backend_error=str(exc),
            url=url,
        )
    finally:
        if owns_client:
            http_client.close()

    effective_run_id = run_id
    if effective_run_id is None and isinstance(run, Mapping):
        effective_run_id = _extract_run_id(run)
    if effective_run_id is None:
        effective_run_id = "<unknown>"
    context = ObservabilityContext(
        product=product,
        run_id=effective_run_id,
        freshness_window_seconds=freshness_window_seconds,
    )
    result = classify_evidence_records(
        backend="dagster",
        query=query,
        context=context,
        records=records,
        url=url,
    )
    if effective_run_id == "<unknown>":
        return result
    return EvidenceResult(
        backend=result.backend,
        status=result.status,
        query=result.query,
        message=result.message,
        records=result.records,
        url=result.url,
        diagnostics={**result.diagnostics, "run_id": effective_run_id},
    )


def query_trace_backend(
    *,
    jaeger_url: str,
    service: str,
    context: ObservabilityContext,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> EvidenceResult:
    """Query Jaeger traces by service/product/run context."""
    tags = {
        FLOE_PRODUCT_NAME: context.product,
        FLOE_RUN_ID: context.run_id,
    }
    tags_json = json.dumps(tags, separators=(",", ":"))
    params = {"service": service, "limit": "50", "tags": tags_json}
    url = _join_url(jaeger_url, "api/traces")
    query = f"service={service} product={context.product} run_id={context.run_id}"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        response = http_client.get(url, params=params)
        response.raise_for_status()
        records = _jaeger_records(response.json())
    except Exception as exc:  # noqa: BLE001
        return classify_evidence_records(
            backend="traces",
            query=query,
            context=context,
            records=None,
            backend_error=str(exc),
            url=url,
        )
    finally:
        if owns_client:
            http_client.close()

    return classify_evidence_records(
        backend="traces",
        query=query,
        context=context,
        records=records,
        url=url,
    )


def query_loki_logs(
    *,
    loki_url: str,
    product: str,
    run_id: str,
    context: ObservabilityContext,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> EvidenceResult:
    """Query Loki structured logs by product/run context."""
    # The OTLP-to-Loki path maps OTel ``service.name`` to the Loki
    # ``service_name`` label.  Do not depend on a Promtail-style ``job`` label;
    # the alpha chart sends runtime logs directly through the collector.
    loki_query = f'{{service_name=~".+"}} |= "{product}" |= "{run_id}"'
    url = _join_url(loki_url, "loki/api/v1/query_range")
    ready_url = _join_url(loki_url, "ready")
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        ready_response = http_client.get(ready_url)
        ready_response.raise_for_status()
        response = http_client.get(url, params={"query": loki_query, "limit": "100"})
        response.raise_for_status()
        records = _loki_records(response.json())
    except Exception as exc:  # noqa: BLE001
        return classify_evidence_records(
            backend="logs",
            query=loki_query,
            context=context,
            records=None,
            backend_error=str(exc),
            url=url,
        )
    finally:
        if owns_client:
            http_client.close()

    # Loki log proof is run-scoped. Drop table from the shared context so a
    # valid run-level log stream is not rejected for missing table text.
    log_context = ObservabilityContext(
        product=context.product,
        run_id=context.run_id,
        freshness_window_seconds=context.freshness_window_seconds,
        now_epoch_seconds=context.now_epoch_seconds,
    )
    return classify_evidence_records(
        backend="logs",
        query=loki_query,
        context=log_context,
        records=records,
        url=url,
    )


def query_prometheus_instant_metrics(
    *,
    prometheus_url: str,
    product: str,
    status: str,
    plugin: str,
    context: ObservabilityContext,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> EvidenceResult:
    """Query Prometheus instant metrics by product/status/plugin context."""
    metric_name = (
        ASSET_FAILURES_METRIC
        if status.lower() in {"failure", "error"}
        else ASSET_MATERIALIZATIONS_METRIC
    )
    prom_query = (
        f'{metric_name}{{{METRIC_PRODUCT_NAME_LABEL}="{product}",'
        f'{METRIC_STATUS_LABEL}="{status}",{METRIC_PLUGIN_NAME_LABEL}=~"{plugin}"}}'
    )
    url = _join_url(prometheus_url, "api/v1/query")
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        response = http_client.get(url, params={"query": prom_query})
        response.raise_for_status()
        records = _prometheus_records(response.json())
    except Exception as exc:  # noqa: BLE001
        return classify_evidence_records(
            backend="metrics",
            query=prom_query,
            context=context,
            records=None,
            backend_error=str(exc),
            url=url,
        )
    finally:
        if owns_client:
            http_client.close()

    return _classify_metric_records(
        query=prom_query,
        context=context,
        records=records,
        status=status,
        plugin=plugin,
        url=url,
    )


def query_prometheus_metrics(
    *,
    prometheus_url: str,
    product: str,
    status: str,
    plugin: str,
    context: ObservabilityContext,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> EvidenceResult:
    """Query Prometheus metrics by product/status/plugin context."""
    metric_name = (
        ASSET_FAILURES_METRIC
        if status.lower() in {"failure", "error"}
        else ASSET_MATERIALIZATIONS_METRIC
    )
    prom_query = (
        f'{metric_name}{{{METRIC_PRODUCT_NAME_LABEL}="{product}",'
        f'{METRIC_STATUS_LABEL}="{status}",{METRIC_PLUGIN_NAME_LABEL}=~"{plugin}"}}'
    )
    url = _join_url(prometheus_url, "api/v1/query_range")
    end = context.now_epoch_seconds if context.now_epoch_seconds is not None else time.time()
    start = max(0.0, context.freshness_cutoff_epoch_seconds)
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        response = http_client.get(
            url,
            params={
                "query": prom_query,
                "start": f"{start:.3f}",
                "end": f"{end:.3f}",
                "step": "15s",
            },
        )
        response.raise_for_status()
        records = _prometheus_records(response.json())
    except Exception as exc:  # noqa: BLE001
        return classify_evidence_records(
            backend="metrics",
            query=prom_query,
            context=context,
            records=None,
            backend_error=str(exc),
            url=url,
        )
    finally:
        if owns_client:
            http_client.close()

    return _classify_metric_records(
        query=prom_query,
        context=context,
        records=records,
        status=status,
        plugin=plugin,
        url=url,
    )


def query_marquez_lineage(
    *,
    marquez_url: str,
    namespace: str,
    job_name: str,
    context: ObservabilityContext,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> EvidenceResult:
    """Query Marquez lineage by namespace/job/run context."""
    encoded_namespace = quote(namespace, safe="")
    encoded_job = quote(job_name, safe="")
    namespace_url = _join_url(marquez_url, f"api/v1/namespaces/{encoded_namespace}")
    runs_url = _join_url(
        marquez_url,
        f"api/v1/namespaces/{encoded_namespace}/jobs/{encoded_job}/runs",
    )
    jobs_url = _join_url(marquez_url, f"api/v1/namespaces/{encoded_namespace}/jobs")
    datasets_url = _join_url(marquez_url, f"api/v1/namespaces/{encoded_namespace}/datasets")
    graph_url = build_marquez_graph_query_url(marquez_url)
    query = f"namespace={namespace} job={job_name} run_id={context.run_id}"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    active_url = runs_url
    try:
        active_url = namespace_url
        namespace_response = http_client.get(namespace_url)
        if _response_status_code(namespace_response) == 404:
            return _marquez_wrong_context_result(
                query=query,
                context=context,
                url=namespace_url,
                message=f"lineage namespace {namespace!r} was not found in Marquez",
            )
        namespace_response.raise_for_status()

        active_url = runs_url
        runs_response = http_client.get(runs_url)
        if _response_status_code(runs_response) == 404:
            return _marquez_wrong_context_result(
                query=query,
                context=context,
                url=runs_url,
                message=(
                    f"lineage job {job_name!r} was not found in Marquez namespace {namespace!r}"
                ),
            )
        runs_response.raise_for_status()
        run_records = _marquez_records(
            runs_response.json(),
            namespace=namespace,
            job_name=job_name,
        )

        active_url = jobs_url
        jobs_response = http_client.get(jobs_url)
        jobs_response.raise_for_status()
        job_records = _marquez_job_records(jobs_response.json(), namespace=namespace)

        active_url = datasets_url
        datasets_response = http_client.get(datasets_url)
        datasets_response.raise_for_status()
        dataset_records = _marquez_dataset_records(
            datasets_response.json(),
            namespace=namespace,
        )

        model_run_records: list[EvidenceRecord] = []
        for model_job_name in _marquez_model_table_job_names(job_records, context):
            model_runs_url = _join_url(
                marquez_url,
                (
                    f"api/v1/namespaces/{encoded_namespace}/jobs/"
                    f"{quote(model_job_name, safe='')}/runs"
                ),
            )
            active_url = model_runs_url
            model_runs_response = http_client.get(model_runs_url)
            model_runs_response.raise_for_status()
            for record in _marquez_records(
                model_runs_response.json(),
                namespace=namespace,
                job_name=model_job_name,
            ):
                model_run_records.append(
                    _marquez_model_record_with_parent_run(
                        record,
                        http_client=http_client,
                        marquez_url=marquez_url,
                    )
                )
        graph_records: list[EvidenceRecord] = []
        for dataset_name in _marquez_dataset_names(dataset_records, context, namespace=namespace):
            lineage_url = graph_url
            active_url = lineage_url
            lineage_response = http_client.get(
                lineage_url,
                params={
                    "nodeId": f"dataset:{namespace}:{dataset_name}",
                    "depth": "3",
                },
            )
            lineage_response.raise_for_status()
            graph_records.append(
                _marquez_lineage_graph_record(
                    lineage_response.json(),
                    namespace=namespace,
                    dataset_name=dataset_name,
                    requested_depth=3,
                )
            )
    except Exception as exc:  # noqa: BLE001
        return classify_evidence_records(
            backend="lineage",
            query=query,
            context=context,
            records=None,
            backend_error=str(exc),
            url=active_url,
        )
    finally:
        if owns_client:
            http_client.close()

    return _classify_marquez_lineage_records(
        query=query,
        context=context,
        namespace=namespace,
        run_records=run_records,
        model_run_records=model_run_records,
        dataset_records=dataset_records,
        graph_records=graph_records,
        url=runs_url,
        dataset_url=datasets_url,
        lineage_url=graph_url,
    )


def build_marquez_graph_node_id(*, node_type: str, namespace: str, name: str) -> str:
    """Build the Marquez lineage graph node id for a namespace-scoped object."""
    return f"{node_type.lower()}:{namespace}:{name}"


def build_marquez_graph_query_url(marquez_url: str) -> str:
    """Return the Marquez lineage graph query URL."""
    return _join_url(marquez_url, "api/v1/lineage")


def extract_grafana_panel_queries(dashboard: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    """Extract datasource/query pairs from Grafana dashboard panels."""
    dashboard_body = dashboard.get("dashboard", dashboard)
    if not isinstance(dashboard_body, Mapping):
        return ()
    panels = dashboard_body.get("panels", [])
    if not isinstance(panels, list):
        return ()

    queries: list[dict[str, str]] = []
    for panel in panels:
        if not isinstance(panel, Mapping):
            continue
        panel_title = str(panel.get("title") or "<untitled>")
        panel_datasource_uid = _grafana_datasource_uid(panel.get("datasource"))
        targets = panel.get("targets", [])
        if not isinstance(targets, list):
            continue
        for target in targets:
            if not isinstance(target, Mapping):
                continue
            query = target.get("expr") or target.get("query") or target.get("refId")
            if not query:
                continue
            datasource_uid = _grafana_datasource_uid(target.get("datasource"))
            datasource_uid = datasource_uid or panel_datasource_uid
            if not datasource_uid:
                continue
            queries.append(
                {
                    "panel_title": panel_title,
                    "datasource_uid": datasource_uid,
                    "query": str(query),
                    "backend": _grafana_backend_from_query_or_uid(
                        query=str(query),
                        datasource_uid=datasource_uid,
                    ),
                }
            )
    return tuple(queries)


def query_grafana_dashboard_panels(
    *,
    grafana_url: str,
    dashboard: Mapping[str, Any],
    backend_results: Mapping[str, bool],
    context: ObservabilityContext,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> EvidenceResult:
    """Validate Grafana datasource and panel queries against backend truth."""
    panel_queries = extract_grafana_panel_queries(dashboard)
    query = "grafana dashboard panel queries"
    if not panel_queries:
        return EvidenceResult(
            backend="grafana",
            status=EvidenceStatus.CONTRACT_GAP,
            query=query,
            message="Grafana dashboard contains no extractable panel queries",
        )

    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        for panel_query in panel_queries:
            datasource_uid = panel_query["datasource_uid"]
            datasource_url = _join_url(grafana_url, f"api/datasources/uid/{datasource_uid}")
            datasource_response = http_client.get(datasource_url)
            datasource_response.raise_for_status()
            datasource_payload = datasource_response.json()
            backend = _grafana_backend_from_datasource(
                datasource_payload,
                fallback=panel_query["backend"],
            )
            query_url = _join_url(grafana_url, "api/ds/query")
            query_response = http_client.get(
                query_url,
                params={"query": panel_query["query"], "datasourceUid": datasource_uid},
            )
            query_response.raise_for_status()
            if backend_results.get(backend, False) and not _grafana_query_has_frames(
                query_response.json()
            ):
                return EvidenceResult(
                    backend="grafana",
                    status=EvidenceStatus.DASHBOARD_DATASOURCE_DRIFT,
                    query=panel_query["query"],
                    url=query_url,
                    message=(
                        "Grafana panel query returned no data through its configured "
                        "datasource while the backend query passed"
                    ),
                    diagnostics={
                        "datasource_uid": datasource_uid,
                        "panel_title": panel_query["panel_title"],
                        "backend": backend,
                    },
                )
    except Exception as exc:  # noqa: BLE001
        return classify_evidence_records(
            backend="grafana",
            query=query,
            context=context,
            records=None,
            backend_error=str(exc),
            url=_join_url(grafana_url, "api/ds/query"),
        )
    finally:
        if owns_client:
            http_client.close()

    return EvidenceResult(
        backend="grafana",
        status=EvidenceStatus.PASS,
        query=query,
        message="Grafana dashboard panel queries returned data through configured datasources",
        records=(
            EvidenceRecord(
                payload={"panel_queries": list(panel_queries), "product": context.product},
                timestamp_epoch_seconds=context.now_epoch_seconds,
            ),
        ),
    )


def validate_customer360_observability(
    config: Customer360ObservabilityConfig | None = None,
) -> ObservabilityProofResult:
    """Validate traces, logs, metrics, and lineage for one Customer 360 run."""
    config = config or Customer360ObservabilityConfig.from_env()
    run_id = config.run_id or read_run_id_from_evidence_file(config.run_evidence_file)
    dagster_result = query_dagster_run(
        dagster_url=config.dagster_url,
        product=config.product,
        job_name=config.job_name,
        run_id=run_id,
        freshness_window_seconds=config.freshness_window_seconds,
        timeout_seconds=config.timeout_seconds,
    )
    resolved_run_id = run_id or dagster_result.diagnostics.get("run_id")
    evidence = _result_evidence("dagster", dagster_result)
    failures = _result_failures(dagster_result)
    if not resolved_run_id:
        failures.append(
            "No Customer 360 run id is available; run make demo-customer-360-run first "
            "or set FLOE_DEMO_RUN_ID."
        )
        return ObservabilityProofResult(
            run_id=None,
            evidence=evidence,
            failures=failures,
            backend_results=(dagster_result,),
        )

    evidence["observability.run_id"] = resolved_run_id
    if dagster_result.status is EvidenceStatus.PRODUCT_FAILURE:
        return ObservabilityProofResult(
            run_id=resolved_run_id,
            evidence=evidence,
            failures=failures,
            backend_results=(dagster_result,),
        )

    trace_context = ObservabilityContext(
        product=config.product,
        run_id=resolved_run_id,
        freshness_window_seconds=config.freshness_window_seconds,
    )
    run_context = ObservabilityContext(
        product=config.product,
        run_id=resolved_run_id,
        freshness_window_seconds=config.freshness_window_seconds,
    )
    metric_context = ObservabilityContext(
        product=config.product,
        run_id=resolved_run_id,
        table=config.table,
        freshness_window_seconds=config.freshness_window_seconds,
    )
    lineage_context = ObservabilityContext(
        product=config.product,
        run_id=resolved_run_id,
        table=config.table,
        freshness_window_seconds=config.freshness_window_seconds,
    )
    last_result: ObservabilityProofResult | None = None

    def evidence_ready() -> bool:
        nonlocal last_result
        runtime_results = _query_runtime_observability_backends(
            config=config,
            trace_context=trace_context,
            run_context=run_context,
            metric_context=metric_context,
            lineage_context=lineage_context,
            resolved_run_id=resolved_run_id,
        )
        result = _build_proof_result(
            run_id=resolved_run_id,
            backend_results=(dagster_result, *runtime_results),
        )
        last_result = result
        return result.ok

    wait_for_condition(
        evidence_ready,
        timeout=max(0.0, config.evidence_poll_timeout_seconds),
        interval=max(0.1, config.evidence_poll_interval_seconds),
        description=f"Customer 360 observability evidence for run {resolved_run_id}",
        raise_on_timeout=False,
    )
    if last_result is None:
        runtime_results = _query_runtime_observability_backends(
            config=config,
            trace_context=trace_context,
            run_context=run_context,
            metric_context=metric_context,
            lineage_context=lineage_context,
            resolved_run_id=resolved_run_id,
        )
        last_result = _build_proof_result(
            run_id=resolved_run_id,
            backend_results=(dagster_result, *runtime_results),
        )
    return last_result


def _query_runtime_observability_backends(
    *,
    config: Customer360ObservabilityConfig,
    trace_context: ObservabilityContext,
    run_context: ObservabilityContext,
    metric_context: ObservabilityContext,
    lineage_context: ObservabilityContext,
    resolved_run_id: str,
) -> tuple[EvidenceResult, EvidenceResult, EvidenceResult, EvidenceResult]:
    """Query runtime backends that may ingest after Dagster reports success."""
    return (
        query_trace_backend(
            jaeger_url=config.jaeger_url,
            service=config.service,
            context=trace_context,
            timeout_seconds=config.timeout_seconds,
        ),
        query_loki_logs(
            loki_url=config.loki_url,
            product=config.product,
            run_id=resolved_run_id,
            context=run_context,
            timeout_seconds=config.timeout_seconds,
        ),
        query_prometheus_metrics(
            prometheus_url=config.prometheus_url,
            product=config.product,
            status=config.metric_status,
            plugin=config.metric_plugin,
            context=metric_context,
            timeout_seconds=config.timeout_seconds,
        ),
        query_marquez_lineage(
            marquez_url=config.marquez_url,
            namespace=config.namespace,
            job_name=config.job_name,
            context=lineage_context,
            timeout_seconds=config.timeout_seconds,
        ),
    )


def _build_proof_result(
    *,
    run_id: str,
    backend_results: tuple[EvidenceResult, ...],
) -> ObservabilityProofResult:
    """Build an aggregate proof result from backend checks."""
    evidence = {}
    failures = []
    for result in backend_results:
        evidence.update(_result_evidence(result.backend, result))
        failures.extend(_result_failures(result))
    evidence["observability.run_id"] = run_id
    if len(backend_results) > 1:
        failures.extend(_trace_category_failures(backend_results[1], evidence))

    return ObservabilityProofResult(
        run_id=run_id,
        evidence=evidence,
        failures=failures,
        backend_results=backend_results,
    )


def _marquez_wrong_context_result(
    *,
    query: str,
    context: ObservabilityContext,
    url: str,
    message: str,
) -> EvidenceResult:
    expected = f"{context.product} / {context.run_id}"
    return EvidenceResult(
        backend="lineage",
        status=EvidenceStatus.WRONG_CONTEXT,
        query=query,
        url=url,
        message=message,
        diagnostics={"expected_context": expected},
    )


def _result_evidence(prefix: str, result: EvidenceResult) -> dict[str, str]:
    evidence = {
        f"observability.{prefix}.status": result.status.value,
        f"observability.{prefix}.count": str(result.evidence_count),
        f"observability.{prefix}.query": result.query,
    }
    if result.url:
        evidence[f"observability.{prefix}.url"] = result.url
    for key, value in result.diagnostics.items():
        evidence[f"observability.{prefix}.{key}"] = value
    return evidence


def _result_failures(result: EvidenceResult) -> list[str]:
    if result.ok:
        return []
    location = f" url={result.url}" if result.url else ""
    return [
        f"{result.backend} evidence {result.status.value}: {result.message}; "
        f"query={result.query}{location}"
    ]


def _classify_metric_records(
    *,
    query: str,
    context: ObservabilityContext,
    records: Sequence[EvidenceRecord],
    status: str,
    plugin: str,
    url: str,
) -> EvidenceResult:
    record_tuple = tuple(records)
    if not record_tuple:
        return EvidenceResult(
            backend="metrics",
            status=EvidenceStatus.NO_FRESH_EVIDENCE,
            query=query,
            url=url,
            message=f"metrics backend returned no evidence for {context.product}/{status}/{plugin}",
        )

    matching_context = [
        record
        for record in record_tuple
        if _metric_record_matches_context(record, context, status=status, plugin=plugin)
    ]
    if not matching_context:
        expected = f"{context.product} / {status} / {plugin}"
        if context.table:
            expected = f"{expected} / {context.table}"
        return EvidenceResult(
            backend="metrics",
            status=EvidenceStatus.WRONG_CONTEXT,
            query=query,
            url=url,
            message=(
                "metrics backend returned evidence, but none matched bounded-cardinality "
                f"metric context {expected}"
            ),
            records=record_tuple,
            diagnostics={"expected_context": expected},
        )

    fresh_records = [
        record
        for record in matching_context
        if record.timestamp_epoch_seconds is None
        or record.timestamp_epoch_seconds >= context.freshness_cutoff_epoch_seconds
    ]
    if not fresh_records:
        newest = max(
            (
                record.timestamp_epoch_seconds
                for record in matching_context
                if record.timestamp_epoch_seconds is not None
            ),
            default=None,
        )
        diagnostics = {}
        if newest is not None:
            diagnostics["newest_epoch_seconds"] = f"{newest:.3f}"
            diagnostics["freshness_cutoff_epoch_seconds"] = (
                f"{context.freshness_cutoff_epoch_seconds:.3f}"
            )
        return EvidenceResult(
            backend="metrics",
            status=EvidenceStatus.STALE_EVIDENCE,
            query=query,
            url=url,
            message=f"metrics backend returned only stale evidence for {context.product}/{status}",
            records=tuple(matching_context),
            diagnostics=diagnostics,
        )

    return EvidenceResult(
        backend="metrics",
        status=EvidenceStatus.PASS,
        query=query,
        url=url,
        message=f"metrics backend returned fresh evidence for {context.product}/{status}",
        records=tuple(fresh_records),
    )


def _classify_marquez_lineage_records(
    *,
    query: str,
    context: ObservabilityContext,
    namespace: str,
    run_records: Sequence[EvidenceRecord],
    model_run_records: Sequence[EvidenceRecord],
    dataset_records: Sequence[EvidenceRecord],
    graph_records: Sequence[EvidenceRecord],
    url: str,
    dataset_url: str,
    lineage_url: str,
) -> EvidenceResult:
    product_context = ObservabilityContext(
        product=context.product,
        run_id=context.run_id,
        freshness_window_seconds=context.freshness_window_seconds,
        now_epoch_seconds=context.now_epoch_seconds,
    )
    product_result = classify_evidence_records(
        backend="lineage",
        query=query,
        context=product_context,
        records=run_records,
        url=url,
    )
    if not product_result.ok:
        return product_result

    table_result = _classify_marquez_model_table_run_records(
        query=f"{query} table={context.table or '<none>'}",
        context=context,
        records=model_run_records,
        url=url,
    )
    if not table_result.ok:
        return table_result

    dataset_result = _classify_marquez_dataset_records(
        query=f"{query} dataset={context.table or '<none>'}",
        context=context,
        namespace=namespace,
        records=dataset_records,
        url=dataset_url,
    )
    if not dataset_result.ok:
        return dataset_result

    graph_result = _classify_marquez_lineage_graph_records(
        query=f"{query} graph_depth=3 table={context.table or '<none>'}",
        context=context,
        namespace=namespace,
        records=graph_records,
        url=lineage_url,
    )
    if not graph_result.ok:
        return graph_result

    return EvidenceResult(
        backend="lineage",
        status=EvidenceStatus.PASS,
        query=query,
        url=url,
        message=(
            f"lineage backend returned product run evidence for {context.run_id} "
            f"and model/table evidence for {context.table}"
        ),
        records=(
            *product_result.records,
            *table_result.records,
            *dataset_result.records,
            *graph_result.records,
        ),
        diagnostics={
            "product_run_count": str(product_result.evidence_count),
            "model_table_count": str(table_result.evidence_count),
            "dataset_count": str(dataset_result.evidence_count),
            "lineage_graph_depth": graph_result.diagnostics.get(
                "lineage_graph_depth",
                "unknown",
            ),
            "lineage_graph_requested_depth": graph_result.diagnostics.get(
                "lineage_graph_requested_depth",
                "unknown",
            ),
            "lineage_graph_count": str(graph_result.evidence_count),
            "graph_count": str(len(graph_records)),
        },
    )


def _optional_marquez_dataset_records(
    *,
    http_client: httpx.Client,
    datasets_url: str,
    namespace: str,
) -> tuple[EvidenceRecord, ...]:
    """Return Marquez dataset records when the endpoint is available."""
    try:
        response = http_client.get(datasets_url)
        response.raise_for_status()
        return tuple(_marquez_dataset_records(response.json(), namespace=namespace))
    except Exception:  # noqa: BLE001 - older Marquez endpoints may omit datasets listing.
        return ()


def _query_optional_marquez_graph(
    *,
    http_client: httpx.Client,
    graph_url: str,
    node_id: str,
) -> tuple[EvidenceRecord, ...]:
    """Return Marquez lineage graph records when the endpoint is available."""
    try:
        response = http_client.get(graph_url, params={"nodeId": node_id, "depth": "2"})
        response.raise_for_status()
        return tuple(_marquez_graph_records(response.json(), node_id=node_id))
    except Exception:  # noqa: BLE001 - graph evidence is additive for this helper.
        return ()


def _classify_marquez_model_table_run_records(
    *,
    query: str,
    context: ObservabilityContext,
    records: Sequence[EvidenceRecord],
    url: str,
) -> EvidenceResult:
    record_tuple = tuple(records)
    if not record_tuple:
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.CONTRACT_GAP,
            query=query,
            url=url,
            message=(
                "lineage backend returned product run evidence but no model/table run evidence "
                "linked to "
                f"{context.product}/{context.run_id}/{context.table or '<none>'}"
            ),
            diagnostics={"contract_gap": "marquez_model_table_run_detail"},
        )

    matching_context = [
        record
        for record in record_tuple
        if _marquez_model_table_record_matches_context(record, context)
    ]
    if not matching_context:
        expected = f"{context.product} / {context.run_id} / {context.table or '<none>'}"
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.WRONG_CONTEXT,
            query=query,
            url=url,
            message=(
                "lineage backend returned model/table run evidence, but none matched "
                f"parent run context {expected}"
            ),
            records=record_tuple,
            diagnostics={"expected_context": expected},
        )

    failed_records = [record for record in matching_context if _record_has_failure_status(record)]
    if failed_records:
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.PRODUCT_FAILURE,
            query=query,
            url=url,
            message="Product execution failed according to lineage model/table evidence",
            records=tuple(failed_records),
        )

    fresh_records = [
        record
        for record in matching_context
        if record.timestamp_epoch_seconds is not None
        and record.timestamp_epoch_seconds >= context.freshness_cutoff_epoch_seconds
    ]
    if not fresh_records:
        newest = max(
            (
                record.timestamp_epoch_seconds
                for record in matching_context
                if record.timestamp_epoch_seconds is not None
            ),
            default=None,
        )
        diagnostics = {}
        if newest is not None:
            diagnostics["newest_epoch_seconds"] = f"{newest:.3f}"
            diagnostics["freshness_cutoff_epoch_seconds"] = (
                f"{context.freshness_cutoff_epoch_seconds:.3f}"
            )
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.STALE_EVIDENCE,
            query=query,
            url=url,
            message=(
                f"lineage backend returned only stale model/table run evidence for {context.run_id}"
            ),
            records=tuple(matching_context),
            diagnostics=diagnostics,
        )

    return EvidenceResult(
        backend="lineage",
        status=EvidenceStatus.PASS,
        query=query,
        url=url,
        message=(
            f"lineage backend returned fresh model/table run evidence linked to {context.run_id}"
        ),
        records=tuple(fresh_records),
    )


def _classify_marquez_dataset_records(
    *,
    query: str,
    context: ObservabilityContext,
    namespace: str,
    records: Sequence[EvidenceRecord],
    url: str,
) -> EvidenceResult:
    record_tuple = tuple(records)
    if not record_tuple:
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.CONTRACT_GAP,
            query=query,
            url=url,
            message=(
                "lineage backend returned product/model runs but no dataset API evidence "
                f"for {context.table or '<none>'}"
            ),
            diagnostics={"contract_gap": "marquez_dataset_detail"},
        )

    matching_context = [
        record
        for record in record_tuple
        if _marquez_dataset_record_matches_context(record, context, namespace=namespace)
    ]
    if not matching_context:
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.WRONG_CONTEXT,
            query=query,
            url=url,
            message=(
                "lineage backend returned dataset evidence, but none matched "
                f"namespace/table context {namespace}/{context.table or '<none>'}"
            ),
            records=record_tuple,
            diagnostics={
                "expected_context": (
                    f"{context.product} / {context.run_id} / {context.table or '<none>'}"
                )
            },
        )

    return EvidenceResult(
        backend="lineage",
        status=EvidenceStatus.PASS,
        query=query,
        url=url,
        message=f"lineage backend returned dataset evidence for {context.table}",
        records=tuple(matching_context),
    )


def _classify_marquez_lineage_graph_records(
    *,
    query: str,
    context: ObservabilityContext,
    namespace: str,
    records: Sequence[EvidenceRecord],
    url: str,
) -> EvidenceResult:
    record_tuple = tuple(records)
    if not record_tuple:
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.CONTRACT_GAP,
            query=query,
            url=url,
            message=(
                "lineage backend returned product/model/dataset evidence but no lineage "
                f"graph records for {context.table or '<none>'}"
            ),
            diagnostics={"contract_gap": "marquez_lineage_graph_detail"},
        )

    matching_context = [
        record
        for record in record_tuple
        if _marquez_lineage_graph_matches_context(record, context, namespace=namespace)
    ]
    if not matching_context:
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.WRONG_CONTEXT,
            query=query,
            url=url,
            message=(
                "lineage backend returned graph evidence, but none matched "
                f"namespace/table context {namespace}/{context.table or '<none>'}"
            ),
            records=record_tuple,
            diagnostics={
                "expected_context": (
                    f"{context.product} / {context.run_id} / {context.table or '<none>'}"
                )
            },
        )

    node_count = sum(_marquez_graph_node_count(record.payload) for record in matching_context)
    edge_count = sum(_marquez_graph_edge_count(record.payload) for record in matching_context)
    lineage_depth = max(
        (
            _marquez_graph_model_depth(record.payload, context, namespace=namespace)
            for record in matching_context
        ),
        default=0,
    )

    if node_count < 3 or lineage_depth < 2:
        return EvidenceResult(
            backend="lineage",
            status=EvidenceStatus.CONTRACT_GAP,
            query=query,
            url=url,
            message=(
                "lineage backend returned a shallow lineage graph without upstream "
                f"model/table depth for {context.table or '<none>'}"
            ),
            records=tuple(matching_context),
            diagnostics={
                "contract_gap": "marquez_lineage_graph_detail",
                "lineage_graph_node_count": str(node_count),
                "lineage_graph_edge_count": str(edge_count),
            },
        )

    return EvidenceResult(
        backend="lineage",
        status=EvidenceStatus.PASS,
        query=query,
        url=url,
        message=f"lineage backend returned graph evidence for {context.table}",
        records=tuple(matching_context),
        diagnostics={
            "lineage_graph_depth": str(lineage_depth),
            "lineage_graph_requested_depth": _marquez_requested_graph_depth(matching_context),
            "lineage_graph_node_count": str(node_count),
            "lineage_graph_edge_count": str(edge_count),
        },
    )


def _marquez_graph_node_count(payload: Mapping[str, Any]) -> int:
    graph = payload.get("graph")
    if isinstance(graph, Mapping):
        nodes = graph.get("nodes")
        if isinstance(nodes, list):
            return len(nodes)
        return 0
    if isinstance(graph, list):
        return len(graph)
    return 0


def _marquez_graph_edge_count(payload: Mapping[str, Any]) -> int:
    graph = payload.get("graph")
    if isinstance(graph, list):
        return len(_marquez_list_graph_edges(graph))
    if isinstance(graph, Mapping):
        edges = graph.get("edges")
        if isinstance(edges, list):
            return len(edges)
        return 0
    return 0


def _marquez_graph_model_depth(
    payload: Mapping[str, Any],
    context: ObservabilityContext,
    *,
    namespace: str,
) -> int:
    target_ids = _marquez_graph_target_dataset_ids(payload, context, namespace=namespace)
    if not target_ids:
        return 0

    node_ids = _marquez_graph_node_ids(payload)
    adjacency = _marquez_graph_adjacency(payload, node_ids)
    if not any(adjacency.values()):
        return 0

    distances = _marquez_graph_distances(target_ids, adjacency)
    has_job_or_run = any(
        _marquez_node_id_is_job_or_run_in_namespace(node_id, namespace=namespace) and distance >= 1
        for node_id, distance in distances.items()
    )
    if not has_job_or_run:
        return 0

    upstream_dataset_depths = [
        distance
        for node_id, distance in distances.items()
        if node_id not in target_ids
        and _marquez_node_id_is_dataset_in_namespace(node_id, namespace=namespace)
    ]
    return max(upstream_dataset_depths, default=0)


def _marquez_graph_target_dataset_ids(
    payload: Mapping[str, Any],
    context: ObservabilityContext,
    *,
    namespace: str,
) -> set[str]:
    if not context.table:
        return set()
    expected_dataset_name = _marquez_graph_expected_dataset_name(payload)
    if expected_dataset_name is None:
        return set()
    return {
        node_id
        for node_id in _marquez_graph_node_ids(payload)
        if _marquez_dataset_node_name(node_id, namespace=namespace) == expected_dataset_name
    }


def _marquez_graph_expected_dataset_name(payload: Mapping[str, Any]) -> str | None:
    name = payload.get("dataset_name") or payload.get("datasetName")
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()


def _marquez_dataset_node_name(node_id: str, *, namespace: str) -> str | None:
    prefix = f"dataset:{namespace}:"
    if not node_id.lower().startswith(prefix.lower()):
        return None
    return node_id[len(prefix) :]


def _marquez_graph_adjacency(
    payload: Mapping[str, Any],
    node_ids: set[str],
) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for origin, destination in _marquez_graph_edges(payload):
        if origin not in node_ids or destination not in node_ids:
            continue
        adjacency[destination].add(origin)
    return adjacency


def _marquez_graph_distances(
    start_ids: set[str],
    adjacency: Mapping[str, set[str]],
) -> dict[str, int]:
    distances = {node_id: 0 for node_id in start_ids if node_id in adjacency}
    frontier = deque(distances)
    while frontier:
        current = frontier.popleft()
        for neighbor in adjacency[current]:
            if neighbor in distances:
                continue
            distances[neighbor] = distances[current] + 1
            frontier.append(neighbor)
    return distances


def _marquez_node_id_is_dataset_in_namespace(
    node_id: str,
    *,
    namespace: str,
) -> bool:
    return node_id.lower().startswith(f"dataset:{namespace}:".lower())


def _marquez_graph_node_ids(payload: Mapping[str, Any]) -> set[str]:
    graph = payload.get("graph")
    if isinstance(graph, Mapping):
        nodes = graph.get("nodes")
        if isinstance(nodes, list):
            return {
                str(node.get("id") or node.get("name"))
                for node in nodes
                if isinstance(node, Mapping) and (node.get("id") or node.get("name"))
            }
    if isinstance(graph, list):
        return {
            str(node.get("id") or node.get("name"))
            for node in graph
            if isinstance(node, Mapping) and (node.get("id") or node.get("name"))
        }
    return set()


def _marquez_graph_edges(payload: Mapping[str, Any]) -> set[tuple[str, str]]:
    graph = payload.get("graph")
    if isinstance(graph, list):
        return _marquez_list_graph_edges(graph)
    if not isinstance(graph, Mapping):
        return set()
    edges = graph.get("edges")
    if not isinstance(edges, list):
        return set()
    return _marquez_edge_ids(edges)


def _marquez_list_graph_edges(graph: Sequence[object]) -> set[tuple[str, str]]:
    edge_ids: set[tuple[str, str]] = set()
    for node in graph:
        if not isinstance(node, Mapping):
            continue
        for key in ("inEdges", "outEdges"):
            edges = node.get(key)
            if not isinstance(edges, list):
                continue
            edge_ids.update(_marquez_edge_ids(edges))
    return edge_ids


def _marquez_edge_ids(edges: Sequence[object]) -> set[tuple[str, str]]:
    edge_ids: set[tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        origin = edge.get("origin") or edge.get("source") or edge.get("from")
        destination = edge.get("destination") or edge.get("target") or edge.get("to")
        if origin and destination:
            edge_ids.add((str(origin), str(destination)))
    return edge_ids


def _marquez_node_id_is_job_or_run(node_id: str) -> bool:
    lowered = node_id.lower()
    return lowered.startswith(("job:", "run:")) or ":job:" in lowered or ":run:" in lowered


def _marquez_node_id_is_job_or_run_in_namespace(
    node_id: str,
    *,
    namespace: str,
) -> bool:
    lowered = node_id.lower()
    namespace_prefixes = (f"job:{namespace}:".lower(), f"run:{namespace}:".lower())
    return lowered.startswith(namespace_prefixes) or (
        _marquez_node_id_is_job_or_run(node_id) and f":{namespace}:" in lowered
    )


def _marquez_requested_graph_depth(records: Sequence[EvidenceRecord]) -> str:
    depths = [
        int(record.payload["requested_depth"])
        for record in records
        if str(record.payload.get("requested_depth", "")).isdigit()
    ]
    return str(max(depths)) if depths else "unknown"


def _trace_category_failures(
    trace_result: EvidenceResult,
    evidence: dict[str, str],
) -> list[str]:
    if not trace_result.ok:
        for category in TRACE_CATEGORY_TERMS:
            evidence[f"observability.traces.{category}"] = "false"
        return []

    payload_text = "\n".join(_payload_text(record.payload) for record in trace_result.records)
    failures: list[str] = []
    for category, alternatives in TRACE_CATEGORY_TERMS.items():
        matched = any(all(term.lower() in payload_text for term in terms) for terms in alternatives)
        evidence[f"observability.traces.{category}"] = str(matched).lower()
        if not matched:
            failures.append(f"traces evidence missing required Customer 360 category: {category}")
    return failures


def _record_matches_context(record: EvidenceRecord, context: ObservabilityContext) -> bool:
    payload_text = _payload_text(record.payload)
    if not _contains_value(payload_text, context.product):
        return False
    if context.run_id != "<unknown>" and context.run_id not in payload_text:
        return False
    if context.table and not _contains_value(payload_text, context.table):
        return False
    return True


def _metric_record_matches_context(
    record: EvidenceRecord,
    context: ObservabilityContext,
    *,
    status: str,
    plugin: str,
) -> bool:
    metric = record.payload.get("metric")
    if not isinstance(metric, Mapping):
        return False
    if not _contains_value(str(metric.get(METRIC_PRODUCT_NAME_LABEL, "")).lower(), context.product):
        return False
    if str(metric.get(METRIC_STATUS_LABEL, "")).lower() != status.lower():
        return False
    plugin_name = str(metric.get(METRIC_PLUGIN_NAME_LABEL, ""))
    if not _regex_fullmatch(plugin, plugin_name):
        return False
    if (
        context.table
        and METRIC_ASSET_KEY_LABEL in metric
        and not _contains_value(
            str(metric.get(METRIC_ASSET_KEY_LABEL, "")).lower(),
            context.table,
        )
    ):
        return False
    return _metric_record_has_positive_value(record)


def _metric_record_has_positive_value(record: EvidenceRecord) -> bool:
    value = record.payload.get("value")
    if not isinstance(value, list) or len(value) < 2:
        return True
    sample = _parse_float(value[1])
    return sample is None or sample > 0


def _marquez_model_table_job_names(
    job_records: Sequence[EvidenceRecord],
    context: ObservabilityContext,
) -> tuple[str, ...]:
    if not context.table:
        return ()
    job_names: set[str] = set()
    for record in job_records:
        name = record.payload.get("name") or record.payload.get("job_name")
        if not name:
            continue
        job_name = str(name)
        if _marquez_dataset_name_matches_table(job_name, context.table):
            job_names.add(job_name)
    return tuple(sorted(job_names))


def _marquez_dataset_names(
    dataset_records: Sequence[EvidenceRecord],
    context: ObservabilityContext,
    *,
    namespace: str,
) -> tuple[str, ...]:
    if not context.table:
        return ()
    names: set[str] = set()
    for record in dataset_records:
        if not _marquez_dataset_record_matches_context(
            record,
            context,
            namespace=namespace,
        ):
            continue
        name = record.payload.get("name") or record.payload.get("dataset_name")
        if name:
            names.add(str(name))
    return tuple(sorted(names))


def _marquez_model_record_with_parent_run(
    record: EvidenceRecord,
    *,
    http_client: httpx.Client,
    marquez_url: str,
) -> EvidenceRecord:
    parent_run_id = _parent_run_id_from_marquez_payload(record.payload)
    if parent_run_id is None:
        parent_run_id = _parent_run_id_from_marquez_run_facets(
            http_client=http_client,
            marquez_url=marquez_url,
            run_payload=record.payload,
        )
    if parent_run_id is None:
        return record
    enriched = dict(record.payload)
    enriched["parent_run_id"] = parent_run_id
    return EvidenceRecord(
        payload=enriched,
        timestamp_epoch_seconds=record.timestamp_epoch_seconds,
    )


def _marquez_model_table_record_matches_context(
    record: EvidenceRecord,
    context: ObservabilityContext,
) -> bool:
    payload_text = _payload_text(record.payload)
    if not _contains_value(payload_text, context.product):
        return False
    if context.table and not _marquez_record_job_name_matches_table(record, context.table):
        return False
    if _parent_run_id_from_marquez_payload(record.payload) != context.run_id:
        return False
    return _marquez_record_is_completed(record)


def _marquez_record_job_name_matches_table(record: EvidenceRecord, table: str) -> bool:
    job_name = _marquez_record_job_name(record)
    return job_name is not None and _marquez_dataset_name_matches_table(job_name, table)


def _marquez_record_job_name(record: EvidenceRecord) -> str | None:
    job = record.payload.get("job")
    if isinstance(job, Mapping):
        name = job.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    name = (
        record.payload.get("job_name")
        or record.payload.get("jobName")
        or record.payload.get("name")
    )
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()


def _marquez_dataset_record_matches_context(
    record: EvidenceRecord,
    context: ObservabilityContext,
    *,
    namespace: str,
) -> bool:
    if not context.table:
        return False
    if str(record.payload.get("namespace", "")) != namespace:
        return False
    dataset_name = _marquez_dataset_record_name(record)
    return dataset_name is not None and _marquez_dataset_name_matches_table(
        dataset_name,
        context.table,
    )


def _marquez_dataset_record_name(record: EvidenceRecord) -> str | None:
    name = (
        record.payload.get("name")
        or record.payload.get("dataset_name")
        or record.payload.get("datasetName")
    )
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()


def _marquez_dataset_name_matches_table(dataset_name: str, table: str) -> bool:
    normalized_name = dataset_name.lower()
    exact_names = {normalized_name, re.split(r"[./:]", normalized_name)[-1]}
    return any(variant in exact_names for variant in _value_variants(table))


def _value_variants(value: str) -> set[str]:
    normalized = value.lower()
    return {normalized, normalized.replace("-", "_"), normalized.replace("_", "-")}


def _marquez_lineage_graph_matches_context(
    record: EvidenceRecord,
    context: ObservabilityContext,
    *,
    namespace: str,
) -> bool:
    if not context.table:
        return False
    target_ids = _marquez_graph_target_dataset_ids(record.payload, context, namespace=namespace)
    return bool(target_ids) and _marquez_graph_has_nodes(record.payload)


def _marquez_graph_has_nodes(payload: Mapping[str, Any]) -> bool:
    graph = payload.get("graph")
    if isinstance(graph, Mapping):
        nodes = graph.get("nodes")
        if isinstance(nodes, list):
            return bool(nodes)
        return bool(graph)
    return isinstance(graph, list) and bool(graph)


def _marquez_record_is_completed(record: EvidenceRecord) -> bool:
    statuses = [status.upper() for status in _iter_status_values(record.payload)]
    if not statuses:
        return False
    return any(status in SUCCESS_STATUSES for status in statuses)


def _parent_run_id_from_marquez_payload(payload: Mapping[str, Any]) -> str | None:
    for key in ("parent_run_id", "parentRunId", "parent_runId"):
        value = payload.get(key)
        if value:
            return str(value)

    facets = payload.get("facets")
    if not isinstance(facets, Mapping):
        return None

    parent_facet = _parent_facet_from_facets(facets)
    if not isinstance(parent_facet, Mapping):
        return None

    parent_run = parent_facet.get("run")
    if isinstance(parent_run, Mapping):
        parent_run_id = parent_run.get("runId") or parent_run.get("id")
        if parent_run_id:
            return str(parent_run_id)

    parent_run_id = parent_facet.get("runId") or parent_facet.get("id")
    return str(parent_run_id) if parent_run_id else None


def _parent_facet_from_facets(facets: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("parentRun", "parent"):
        value = facets.get(key)
        if isinstance(value, Mapping):
            return value

    run_facets = facets.get("run")
    if isinstance(run_facets, Mapping):
        for key in ("parentRun", "parent"):
            value = run_facets.get(key)
            if isinstance(value, Mapping):
                return value
    return None


def _parent_run_id_from_marquez_run_facets(
    *,
    http_client: httpx.Client,
    marquez_url: str,
    run_payload: Mapping[str, Any],
) -> str | None:
    for run_id in sorted(_marquez_run_identity_candidates(run_payload)):
        try:
            response = http_client.get(
                _join_url(marquez_url, f"api/v1/runs/{quote(run_id, safe='')}/facets"),
                params={"type": "run"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:  # noqa: BLE001 - facets are optional enrichment.
            continue
        if not isinstance(payload, Mapping):
            continue
        facets = payload.get("facets")
        if not isinstance(facets, Mapping):
            continue
        parent_run_id = _parent_run_id_from_marquez_payload({"facets": facets})
        if parent_run_id:
            return parent_run_id
    return None


def _marquez_run_identity_candidates(run_payload: Mapping[str, Any]) -> set[str]:
    candidates: set[str] = set()
    for key in ("id", "runId", "run_id"):
        value = run_payload.get(key)
        if value:
            candidates.add(str(value))

    nested_run = run_payload.get("run")
    if isinstance(nested_run, Mapping):
        for key in ("id", "runId", "run_id"):
            value = nested_run.get(key)
            if value:
                candidates.add(str(value))

    return candidates


def _regex_fullmatch(pattern: str, value: str) -> bool:
    if threading.current_thread() is not threading.main_thread():
        try:
            return re.fullmatch(pattern, value) is not None
        except re.error:
            return False

    def _timeout_handler(_signum: int, _frame: object) -> None:
        raise TimeoutError("regex match timed out")

    previous_handler = signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, 0.05)
        return re.fullmatch(pattern, value) is not None
    except (re.error, TimeoutError):
        return False
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)


def _record_has_failure_status(record: EvidenceRecord) -> bool:
    for status in _iter_status_values(record.payload):
        if status.upper() in FAILURE_STATUSES:
            return True
    return False


def _iter_status_values(payload: Mapping[str, Any]) -> Iterable[str]:
    for key, value in payload.items():
        if key.lower() in {"status", "state", "currentstate", "level", "severity"}:
            yield str(value)
        if isinstance(value, Mapping):
            yield from _iter_status_values(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    yield from _iter_status_values(item)


def _contains_value(payload_text: str, value: str) -> bool:
    return any(variant in payload_text for variant in _value_variants(value))


def _payload_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str).lower()


def _jaeger_records(payload: Mapping[str, Any]) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    traces = payload.get("data", [])
    if not isinstance(traces, list):
        return records
    for trace in traces:
        if not isinstance(trace, Mapping):
            continue
        start_times = []
        for span in trace.get("spans", []):
            if isinstance(span, Mapping) and isinstance(span.get("startTime"), int | float):
                start_times.append(float(span["startTime"]) / 1_000_000.0)
        records.append(
            EvidenceRecord(
                payload=trace,
                timestamp_epoch_seconds=max(start_times) if start_times else None,
            )
        )
    return records


def _loki_records(payload: Mapping[str, Any]) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    results = payload.get("data", {}).get("result", [])
    if not isinstance(results, list):
        return records
    for result in results:
        if not isinstance(result, Mapping):
            continue
        stream = result.get("stream", {})
        for value in result.get("values", []):
            if not isinstance(value, list) or len(value) < 2:
                continue
            timestamp = _parse_loki_timestamp(value[0])
            line = value[1]
            decoded_line = _decode_json_line(line)
            records.append(
                EvidenceRecord(
                    payload={"stream": stream, "line": decoded_line},
                    timestamp_epoch_seconds=timestamp,
                )
            )
    return records


def _prometheus_records(payload: Mapping[str, Any]) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    results = payload.get("data", {}).get("result", [])
    if not isinstance(results, list):
        return records
    for result in results:
        if not isinstance(result, Mapping):
            continue
        metric = result.get("metric", {})
        if isinstance(result.get("value"), list):
            values = [result["value"]]
        else:
            values = result.get("values", [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, list) or not value:
                continue
            records.append(
                EvidenceRecord(
                    payload={"metric": metric, "value": value},
                    timestamp_epoch_seconds=_parse_float(value[0]),
                )
            )
    return records


def _marquez_records(
    payload: Mapping[str, Any],
    *,
    namespace: str,
    job_name: str,
) -> list[EvidenceRecord]:
    runs = payload.get("runs", [])
    if not isinstance(runs, list):
        return []
    records: list[EvidenceRecord] = []
    for run in runs:
        if not isinstance(run, Mapping):
            continue
        enriched = dict(run)
        enriched.setdefault("namespace", namespace)
        enriched.setdefault("job_name", job_name)
        records.append(
            EvidenceRecord(
                payload=enriched,
                timestamp_epoch_seconds=_parse_timestamp(
                    run.get("endedAt") or run.get("startedAt") or run.get("updatedAt")
                ),
            )
        )
    return records


def _marquez_job_records(
    payload: Mapping[str, Any],
    *,
    namespace: str,
) -> list[EvidenceRecord]:
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    records: list[EvidenceRecord] = []
    for job in jobs:
        if not isinstance(job, Mapping):
            continue
        enriched = dict(job)
        enriched.setdefault("namespace", namespace)
        records.append(EvidenceRecord(payload=enriched))
    return records


def _marquez_dataset_records(
    payload: Mapping[str, Any],
    *,
    namespace: str,
) -> list[EvidenceRecord]:
    datasets = payload.get("datasets", [])
    if not isinstance(datasets, list):
        return []
    records: list[EvidenceRecord] = []
    for dataset in datasets:
        if not isinstance(dataset, Mapping):
            continue
        enriched = dict(dataset)
        enriched.setdefault("namespace", namespace)
        records.append(EvidenceRecord(payload=enriched))
    return records


def _marquez_lineage_graph_record(
    payload: Mapping[str, Any],
    *,
    namespace: str,
    dataset_name: str,
    requested_depth: int,
) -> EvidenceRecord:
    enriched = dict(payload)
    enriched.setdefault("namespace", namespace)
    enriched.setdefault("dataset_name", dataset_name)
    enriched.setdefault("requested_depth", requested_depth)
    return EvidenceRecord(payload=enriched)


def _marquez_graph_records(
    payload: Mapping[str, Any],
    *,
    node_id: str,
) -> list[EvidenceRecord]:
    """Convert a Marquez lineage graph response into evidence records."""
    enriched = dict(payload)
    enriched.setdefault("node_id", node_id)
    return [EvidenceRecord(payload=enriched)]


def _grafana_datasource_uid(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        uid = value.get("uid")
        if uid:
            return str(uid)
    return None


def _grafana_backend_from_query_or_uid(*, query: str, datasource_uid: str) -> str:
    combined = f"{datasource_uid} {query}".lower()
    if "loki" in combined or "logql" in combined:
        return "loki"
    return "prometheus"


def _grafana_backend_from_datasource(
    payload: Mapping[str, Any],
    *,
    fallback: str,
) -> str:
    datasource_type = str(payload.get("type", "")).lower()
    if "loki" in datasource_type:
        return "loki"
    if "prometheus" in datasource_type:
        return "prometheus"
    return fallback


def _grafana_query_has_frames(payload: Mapping[str, Any]) -> bool:
    results = payload.get("results", {})
    if not isinstance(results, Mapping):
        return False
    for result in results.values():
        if not isinstance(result, Mapping):
            continue
        frames = result.get("frames", [])
        if isinstance(frames, list) and frames:
            return True
    return False


def _dagster_run_record(run: Mapping[str, Any], *, product: str) -> EvidenceRecord:
    enriched = dict(run)
    enriched.setdefault("product", product)
    timestamp = _parse_dagster_timestamp(run.get("endTime") or run.get("startTime"))
    return EvidenceRecord(payload=enriched, timestamp_epoch_seconds=timestamp)


def _select_latest_product_run(
    runs: object,
    *,
    product: str,
    job_name: str,
) -> Mapping[str, Any] | None:
    if not isinstance(runs, list):
        return None
    candidates = [
        run
        for run in runs
        if isinstance(run, Mapping)
        and (
            _contains_value(_payload_text(run), product)
            or _contains_value(str(run.get("pipelineName", "")).lower(), job_name)
        )
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda run: _parse_dagster_timestamp(run.get("endTime") or run.get("startTime")) or 0,
    )


def _extract_run_id(run: Mapping[str, Any] | None) -> str | None:
    if not isinstance(run, Mapping):
        return None
    value = run.get("runId") or run.get("id") or run.get("run_id")
    return str(value) if value else None


def _parse_loki_timestamp(value: object) -> float | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return parsed / 1_000_000_000.0 if parsed > 10_000_000_000 else parsed


def _parse_dagster_timestamp(value: object) -> float | None:
    parsed = _parse_float(value)
    if parsed is not None:
        return parsed
    return _parse_timestamp(value)


def _parse_timestamp(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _parse_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _decode_json_line(line: object) -> object:
    if not isinstance(line, str):
        return line
    try:
        return json.loads(line)
    except ValueError:
        return line


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _response_status_code(response: object) -> int | None:
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None


def _blank_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


_DAGSTER_RUN_QUERY = """
query Customer360Run($runId: ID!) {
  runOrError(runId: $runId) {
    __typename
    ... on Run {
      runId
      status
      pipelineName
      startTime
      endTime
      tags { key value }
    }
    ... on RunNotFoundError { message }
    ... on PythonError { message }
  }
}
"""


_DAGSTER_RECENT_RUNS_QUERY = """
query Customer360RecentRuns {
  runsOrError(limit: 50) {
    __typename
    ... on Runs {
      results {
        runId
        status
        pipelineName
        startTime
        endTime
        tags { key value }
      }
    }
    ... on PythonError { message }
  }
}
"""
