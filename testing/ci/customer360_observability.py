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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from floe_core.telemetry.conventions import FLOE_PRODUCT_NAME, FLOE_RUN_ID

ASSET_MATERIALIZATIONS_METRIC = "floe_asset_materializations_total"
ASSET_FAILURES_METRIC = "floe_asset_failures_total"
METRIC_ASSET_KEY_LABEL = "floe_asset_key"
METRIC_PLUGIN_NAME_LABEL = "floe_plugin_name"
METRIC_PRODUCT_NAME_LABEL = "floe_product_name"
METRIC_STATUS_LABEL = "floe_status"


class EvidenceStatus(str, Enum):
    """Classification for backend evidence checks."""

    PASS = "pass"
    BACKEND_UNREACHABLE = "backend_unreachable"
    NO_FRESH_EVIDENCE = "no_fresh_evidence"
    STALE_EVIDENCE = "stale_evidence"
    WRONG_CONTEXT = "wrong_context"
    PRODUCT_FAILURE = "product_failure"


FAILURE_STATUSES = {"FAILURE", "FAILED", "ERROR", "CANCELED", "CANCELLED"}
SUCCESS_STATUSES = {"SUCCESS", "SUCCEEDED", "COMPLETED", "OK", "PASS", "PASSED"}


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
            dagster_url=os.environ.get("FLOE_DEMO_DAGSTER_URL", "http://localhost:3100"),
            jaeger_url=os.environ.get("FLOE_DEMO_JAEGER_URL", "http://localhost:16686"),
            loki_url=os.environ.get("FLOE_DEMO_LOKI_URL", "http://localhost:3101"),
            prometheus_url=os.environ.get(
                "FLOE_DEMO_PROMETHEUS_URL",
                "http://localhost:9090",
            ),
            marquez_url=os.environ.get("FLOE_DEMO_MARQUEZ_URL", "http://localhost:5100"),
            run_id=_blank_to_none(os.environ.get("FLOE_DEMO_RUN_ID")),
            run_evidence_file=Path(
                os.environ.get("FLOE_DEMO_RUN_EVIDENCE_FILE", ".customer360-run.env")
            ),
            freshness_window_seconds=float(
                os.environ.get("FLOE_DEMO_OBSERVABILITY_FRESHNESS_SECONDS", "1800")
            ),
            timeout_seconds=float(os.environ.get("FLOE_DEMO_COMMAND_TIMEOUT_SECONDS", "30")),
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
    loki_query = f'{{job=~".+"}} |= "{product}" |= "{run_id}"'
    url = _join_url(loki_url, "loki/api/v1/query_range")
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
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

    return classify_evidence_records(
        backend="logs",
        query=loki_query,
        context=context,
        records=records,
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
    runs_url = _join_url(
        marquez_url,
        f"api/v1/namespaces/{encoded_namespace}/jobs/{encoded_job}/runs",
    )
    jobs_url = _join_url(marquez_url, f"api/v1/namespaces/{encoded_namespace}/jobs")
    query = f"namespace={namespace} job={job_name} run_id={context.run_id}"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        runs_response = http_client.get(runs_url)
        runs_response.raise_for_status()
        run_records = _marquez_records(
            runs_response.json(),
            namespace=namespace,
            job_name=job_name,
        )
        jobs_response = http_client.get(jobs_url)
        jobs_response.raise_for_status()
        job_records = _marquez_job_records(jobs_response.json(), namespace=namespace)
        model_run_records: list[EvidenceRecord] = []
        for model_job_name in _marquez_model_table_job_names(job_records, context):
            model_runs_url = _join_url(
                marquez_url,
                (
                    f"api/v1/namespaces/{encoded_namespace}/jobs/"
                    f"{quote(model_job_name, safe='')}/runs"
                ),
            )
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
    except Exception as exc:  # noqa: BLE001
        return classify_evidence_records(
            backend="lineage",
            query=query,
            context=context,
            records=None,
            backend_error=str(exc),
            url=runs_url,
        )
    finally:
        if owns_client:
            http_client.close()

    return _classify_marquez_lineage_records(
        query=query,
        context=context,
        run_records=run_records,
        model_run_records=model_run_records,
        url=runs_url,
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
        table=config.table,
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
    backend_results = (
        dagster_result,
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
            context=trace_context,
            timeout_seconds=config.timeout_seconds,
        ),
    )

    evidence = {}
    failures = []
    for result in backend_results:
        evidence.update(_result_evidence(result.backend, result))
        failures.extend(_result_failures(result))
    evidence["observability.run_id"] = resolved_run_id
    failures.extend(_trace_category_failures(backend_results[1], evidence))

    return ObservabilityProofResult(
        run_id=resolved_run_id,
        evidence=evidence,
        failures=failures,
        backend_results=backend_results,
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
    run_records: Sequence[EvidenceRecord],
    model_run_records: Sequence[EvidenceRecord],
    url: str,
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

    return EvidenceResult(
        backend="lineage",
        status=EvidenceStatus.PASS,
        query=query,
        url=url,
        message=(
            f"lineage backend returned product run evidence for {context.run_id} "
            f"and model/table evidence for {context.table}"
        ),
        records=(*product_result.records, *table_result.records),
        diagnostics={
            "product_run_count": str(product_result.evidence_count),
            "model_table_count": str(table_result.evidence_count),
        },
    )


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
            status=EvidenceStatus.NO_FRESH_EVIDENCE,
            query=query,
            url=url,
            message=(
                "lineage backend returned no fresh model/table run evidence linked to "
                f"{context.product}/{context.run_id}/{context.table or '<none>'}"
            ),
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
        if _contains_value(job_name.lower(), context.table):
            job_names.add(job_name)
    return tuple(sorted(job_names))


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
    if context.table and not _contains_value(payload_text, context.table):
        return False
    if _parent_run_id_from_marquez_payload(record.payload) != context.run_id:
        return False
    return _marquez_record_is_completed(record)


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
    normalized = value.lower()
    variants = {normalized, normalized.replace("-", "_"), normalized.replace("_", "-")}
    return any(variant in payload_text for variant in variants)


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
