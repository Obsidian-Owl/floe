"""Contract tests for Floe platform Grafana dashboard wiring.

The curated alpha dashboards are a presentation surface over emitted runtime
signals. These tests keep datasource drift separate from product/runtime
failure by proving rendered dashboard panels point at provisioned datasources
and only query currently implemented metric families.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

CHART_DIR = Path(__file__).resolve().parents[2] / "charts" / "floe-platform"
DEMO_VALUES = CHART_DIR / "values-demo.yaml"
DASHBOARD_DRIFT_CLASS = "dashboard_datasource_drift"
UNSUPPORTED_ALPHA_METRICS = (
    "dagster_run_",
    "dagster_asset_materialization_count",
    "dbt_test_",
    "dbt_model_",
    "openlineage_",
    "floe_lineage_marquez_event_sends_total",
)
SUPPORTED_ALPHA_METRICS = (
    "floe_asset_materializations_total",
    "floe_asset_failures_total",
    "up",
)


def test_curated_dashboards_reference_provisioned_datasources() -> None:
    """Rendered dashboard UIDs must match generated datasource provisioning."""
    docs = _render_demo_chart()
    _assert_dashboards_reference_provisioned_datasources(docs)


def test_default_dashboards_do_not_reference_unprovisioned_datasources() -> None:
    """Base chart render must not create datasource drift when Prometheus is off."""
    docs = _render_chart()
    _assert_dashboards_reference_provisioned_datasources(docs)


def _assert_dashboards_reference_provisioned_datasources(
    docs: list[dict[str, Any]],
) -> None:
    dashboard_config = _maybe_find_configmap(docs, "floe-platform-grafana-dashboards")
    if dashboard_config is None:
        return
    datasource_config = _find_configmap(docs, "floe-platform-grafana-datasources")

    datasource_uids = _datasource_uids(datasource_config)
    dashboard_refs = _dashboard_datasource_refs(dashboard_config)

    missing = sorted(ref for ref in dashboard_refs if ref not in datasource_uids)
    assert not missing, (
        f"{DASHBOARD_DRIFT_CLASS}: dashboard panels reference datasource UIDs "
        f"{missing}, but provisioned datasource UIDs are {sorted(datasource_uids)}"
    )


def test_curated_dashboards_omit_unsupported_alpha_metric_families() -> None:
    """Dashboards must query emitted Floe runtime signals, not stale families."""
    docs = _render_demo_chart()
    dashboard_config = _find_configmap(docs, "floe-platform-grafana-dashboards")
    queries = _dashboard_queries(dashboard_config)

    unsupported = {
        metric for metric in UNSUPPORTED_ALPHA_METRICS for query in queries if metric in query
    }
    assert not unsupported, (
        "Curated alpha dashboards must omit unsupported metric families until "
        f"runtime emitters produce them; found {sorted(unsupported)}"
    )
    assert any(metric in query for metric in SUPPORTED_ALPHA_METRICS for query in queries), (
        "Curated alpha dashboards must contain at least one implemented Floe metric query"
    )


def test_custom_datasource_uids_render_consistently() -> None:
    """UID overrides must update both provisioned datasources and dashboards."""
    docs = _render_demo_chart(
        "--set",
        "observability.grafana.datasourceUids.prometheus=floe-prom",
        "--set",
        "observability.grafana.datasourceUids.loki=floe-logs",
        "--set",
        "observability.grafana.datasourceUids.jaeger=floe-traces",
    )
    dashboard_config = _find_configmap(docs, "floe-platform-grafana-dashboards")
    datasource_config = _find_configmap(docs, "floe-platform-grafana-datasources")

    datasource_uids = _datasource_uids(datasource_config)
    dashboard_refs = _dashboard_datasource_refs(dashboard_config)

    assert {"floe-prom", "floe-logs", "floe-traces"} <= datasource_uids
    assert "prometheus" not in datasource_uids
    assert "loki" not in dashboard_refs
    assert "prometheus" not in dashboard_refs
    assert {"floe-prom", "floe-logs"} <= dashboard_refs


def test_custom_datasources_fail_when_dashboard_uids_do_not_match() -> None:
    """Custom datasources must not silently create dashboard datasource drift."""
    result = _helm_template_result(
        "-f",
        str(DEMO_VALUES),
        "--set",
        "observability.grafana.datasources[0].name=External Prometheus",
        "--set",
        "observability.grafana.datasources[0].type=prometheus",
        "--set",
        "observability.grafana.datasources[0].uid=external-prom",
        "--set",
        "observability.grafana.datasources[0].url=http://external-prometheus:9090",
        "--set",
        "observability.grafana.datasources[0].access=proxy",
    )

    assert result.returncode != 0
    assert DASHBOARD_DRIFT_CLASS in result.stderr


def test_custom_datasources_can_match_dashboard_uid_overrides() -> None:
    """External Grafana datasource provisioning remains supported when UIDs agree."""
    docs = _render_demo_chart(
        "--set",
        "observability.grafana.datasourceUids.prometheus=external-prom",
        "--set",
        "observability.grafana.datasourceUids.loki=external-loki",
        "--set",
        "observability.grafana.datasourceUids.jaeger=external-jaeger",
        "--set",
        "observability.grafana.datasources[0].name=External Prometheus",
        "--set",
        "observability.grafana.datasources[0].type=prometheus",
        "--set",
        "observability.grafana.datasources[0].uid=external-prom",
        "--set",
        "observability.grafana.datasources[0].url=http://external-prometheus:9090",
        "--set",
        "observability.grafana.datasources[0].access=proxy",
        "--set",
        "observability.grafana.datasources[1].name=External Loki",
        "--set",
        "observability.grafana.datasources[1].type=loki",
        "--set",
        "observability.grafana.datasources[1].uid=external-loki",
        "--set",
        "observability.grafana.datasources[1].url=http://external-loki:3100",
        "--set",
        "observability.grafana.datasources[1].access=proxy",
        "--set",
        "observability.grafana.datasources[2].name=External Jaeger",
        "--set",
        "observability.grafana.datasources[2].type=jaeger",
        "--set",
        "observability.grafana.datasources[2].uid=external-jaeger",
        "--set",
        "observability.grafana.datasources[2].url=http://external-jaeger:16686",
        "--set",
        "observability.grafana.datasources[2].access=proxy",
    )

    _assert_dashboards_reference_provisioned_datasources(docs)


def test_demo_datasources_point_at_floe_chart_backends() -> None:
    """Local and DevPod dashboards must resolve against Floe platform services."""
    docs = _render_demo_chart()
    datasource_config = _find_configmap(docs, "floe-platform-grafana-datasources")
    datasources = _datasources(datasource_config)
    urls_by_type = {source["type"]: source["url"] for source in datasources}

    assert urls_by_type["prometheus"] == "http://floe-platform-prometheus:9090"
    assert urls_by_type["loki"] == "http://floe-platform-loki:3100"
    assert urls_by_type["jaeger"] == "http://floe-platform-jaeger-query:16686"


def test_prometheus_scrapes_otel_collector_and_itself() -> None:
    """Prometheus must expose target health for the platform metric path."""
    docs = _render_demo_chart()
    prometheus_config = _find_configmap(docs, "floe-platform-prometheus")
    scrape_config = yaml.safe_load(prometheus_config["data"]["prometheus.yml"])
    jobs = {scrape["job_name"]: scrape for scrape in scrape_config["scrape_configs"]}

    assert jobs["floe-otel-collector"]["static_configs"][0]["targets"] == [
        "floe-platform-otel:9464"
    ]
    assert jobs["floe-prometheus"]["static_configs"][0]["targets"] == [
        "floe-platform-prometheus:9090"
    ]


def _render_demo_chart(*extra_args: str) -> list[dict[str, Any]]:
    return _render_chart("-f", str(DEMO_VALUES), *extra_args)


def _render_chart(*extra_args: str) -> list[dict[str, Any]]:
    if shutil.which("helm") is None:
        pytest.fail("helm CLI is required for dashboard contract rendering")

    result = _helm_template_result(*extra_args)
    if result.returncode != 0:
        pytest.fail(f"helm template failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

    return [doc for doc in yaml.safe_load_all(result.stdout) if isinstance(doc, dict)]


def _helm_template_result(*extra_args: str) -> subprocess.CompletedProcess[str]:
    if shutil.which("helm") is None:
        pytest.fail("helm CLI is required for dashboard contract rendering")

    return subprocess.run(
        [
            "helm",
            "template",
            "floe-platform",
            str(CHART_DIR),
            "--namespace",
            "floe-dev",
            "--skip-schema-validation",
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _find_configmap(docs: list[dict[str, Any]], name: str) -> dict[str, Any]:
    doc = _maybe_find_configmap(docs, name)
    if doc is not None:
        return doc
    pytest.fail(f"ConfigMap {name!r} was not rendered")


def _maybe_find_configmap(docs: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for doc in docs:
        if doc.get("kind") == "ConfigMap" and doc.get("metadata", {}).get("name") == name:
            return doc
    return None


def _datasources(configmap: dict[str, Any]) -> list[dict[str, Any]]:
    payload = yaml.safe_load(configmap["data"]["datasources.yaml"])
    return list(payload["datasources"])


def _datasource_uids(configmap: dict[str, Any]) -> set[str]:
    return {source["uid"] for source in _datasources(configmap)}


def _dashboard_datasource_refs(configmap: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for value in (configmap.get("data") or {}).values():
        dashboard = json.loads(value)
        for panel in _iter_panels(dashboard.get("panels", [])):
            datasource = panel.get("datasource")
            if isinstance(datasource, dict) and datasource.get("uid"):
                refs.add(str(datasource["uid"]))
            for target in panel.get("targets", []):
                target_datasource = target.get("datasource")
                if isinstance(target_datasource, dict) and target_datasource.get("uid"):
                    refs.add(str(target_datasource["uid"]))
    return refs


def _dashboard_queries(configmap: dict[str, Any]) -> list[str]:
    queries: list[str] = []
    for value in (configmap.get("data") or {}).values():
        dashboard = json.loads(value)
        for panel in _iter_panels(dashboard.get("panels", [])):
            for target in panel.get("targets", []):
                expr = target.get("expr")
                if isinstance(expr, str):
                    queries.append(expr)
    return queries


def _iter_panels(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for panel in panels:
        expanded.append(panel)
        nested = panel.get("panels")
        if isinstance(nested, list):
            expanded.extend(_iter_panels(nested))
    return expanded
