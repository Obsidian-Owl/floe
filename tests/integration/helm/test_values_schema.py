"""Integration tests for Helm values schema validation.

Tests that values files conform to JSON Schema specifications.

Requirements tested:
- 9b-FR-004: Values schema validation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from testing.fixtures.kubernetes import run_helm_template

# Try to import jsonschema, skip tests if not available
try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


CHARTS_DIR = Path(__file__).parent.parent.parent.parent / "charts"


@pytest.fixture
def floe_platform_schema() -> dict[str, Any]:
    """Load floe-platform values schema."""
    schema_path = CHARTS_DIR / "floe-platform" / "values.schema.json"
    if not schema_path.exists():
        pytest.fail(f"Schema not found: {schema_path}")
    with schema_path.open() as f:
        return json.load(f)


@pytest.fixture
def floe_jobs_schema() -> dict[str, Any]:
    """Load floe-jobs values schema."""
    schema_path = CHARTS_DIR / "floe-jobs" / "values.schema.json"
    if not schema_path.exists():
        pytest.fail(f"Schema not found: {schema_path}")
    with schema_path.open() as f:
        return json.load(f)


def load_values_file(chart: str, filename: str = "values.yaml") -> dict[str, Any]:
    """Load a values file from a chart directory."""
    values_path = CHARTS_DIR / chart / filename
    if not values_path.exists():
        pytest.fail(f"Values file not found: {values_path}")
    with values_path.open() as f:
        return yaml.safe_load(f) or {}


def deep_merge_values(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge Helm values maps the same way layered values files are resolved."""
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = deep_merge_values(existing, value)
        else:
            merged[key] = value
    return merged


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFloePlatformSchema:
    """Tests for floe-platform values schema validation."""

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_is_valid_json_schema(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that the schema itself is a valid JSON Schema."""
        # This will raise if schema is invalid
        jsonschema.Draft7Validator.check_schema(floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_default_values_conform_to_schema(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that default values.yaml conforms to schema."""
        values = load_values_file("floe-platform")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_dev_values_conform_to_schema(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that values-dev.yaml conforms to schema."""
        values = load_values_file("floe-platform", "values-dev.yaml")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_staging_values_conform_to_schema(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that values-staging.yaml conforms to schema."""
        values = load_values_file("floe-platform", "values-staging.yaml")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_prod_values_conform_to_schema(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that values-prod.yaml conforms to schema."""
        values = load_values_file("floe-platform", "values-prod.yaml")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_test_values_conform_to_schema(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that values-test.yaml conforms to schema."""
        values = load_values_file("floe-platform", "values-test.yaml")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_demo_values_conform_to_schema(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that values-demo.yaml conforms to schema."""
        values = load_values_file("floe-platform", "values-demo.yaml")
        jsonschema.validate(values, floe_platform_schema)

    @pytest.mark.requirement("FR-044")
    def test_demo_values_wire_queryable_observability_backends(self) -> None:
        """Demo profile must send logs and metrics to queryable backends."""
        values = deep_merge_values(
            load_values_file("floe-platform"),
            load_values_file("floe-platform", "values-demo.yaml"),
        )

        otel_config = values["otel"]["config"]
        exporters = otel_config["exporters"]
        pipelines = otel_config["service"]["pipelines"]

        log_exporters = pipelines["logs"]["exporters"]
        assert log_exporters, "Demo logs pipeline must configure at least one exporter"
        assert any(exporter != "debug" for exporter in log_exporters), (
            "Demo logs pipeline must export to a queryable backend, not debug only"
        )
        assert "otlphttp/loki" in log_exporters
        assert "otlphttp/loki" in exporters

        metric_exporters = pipelines["metrics"]["exporters"]
        assert "prometheus" in metric_exporters, (
            "Demo metrics pipeline must expose a Prometheus-compatible scrape path"
        )
        assert exporters["prometheus"]["endpoint"].endswith(":9464")
        assert "namespace" not in exporters["prometheus"], (
            "OTel Prometheus exporter must not duplicate the floe metric prefix"
        )
        assert values["prometheus"]["enabled"] is True
        assert values["loki"]["config"]["limits_config"]["allow_structured_metadata"] is True

    @pytest.mark.requirement("FR-044")
    def test_demo_observability_backend_profile_renders_query_backends(self) -> None:
        """Demo Helm profile renders Loki, Prometheus query, and Grafana datasources."""
        chart_path = CHARTS_DIR / "floe-platform"
        result = run_helm_template(
            "test-release",
            chart_path,
            values_path=chart_path / "values-demo.yaml",
            timeout=60,
        )

        assert result.returncode == 0, (
            f"Helm template rendering failed: {result.returncode}\nstderr: {result.stderr}"
        )

        rendered = result.stdout
        documents = [
            doc for doc in yaml.safe_load_all(rendered) if isinstance(doc, dict) and doc.get("kind")
        ]
        names_by_kind = {
            (doc.get("kind"), doc.get("metadata", {}).get("name")) for doc in documents
        }

        assert ("ConfigMap", "floe-platform-loki") in names_by_kind
        assert ("Deployment", "floe-platform-loki") in names_by_kind
        assert ("Service", "floe-platform-loki") in names_by_kind
        assert ("ConfigMap", "floe-platform-prometheus") in names_by_kind
        assert ("Deployment", "floe-platform-prometheus") in names_by_kind
        assert ("Service", "floe-platform-prometheus") in names_by_kind

        assert "otlphttp/loki" in rendered
        assert "- otlphttp/loki" in rendered
        assert "endpoint: http://floe-platform-loki:3100/otlp" in rendered
        assert "endpoint: 0.0.0.0:9464" in rendered
        assert "- prometheus" in rendered
        assert "targets:" in rendered
        assert "namespace: floe" not in rendered

        datasource_configmaps = [
            doc
            for doc in documents
            if doc.get("kind") == "ConfigMap"
            and "grafana-datasources" in doc.get("metadata", {}).get("name", "")
        ]
        assert datasource_configmaps, "Grafana datasource provisioning ConfigMap not rendered"

        datasource_payload = yaml.safe_dump(datasource_configmaps)
        assert "type: loki" in datasource_payload
        assert "type: prometheus" in datasource_payload
        assert "type: jaeger" in datasource_payload
        assert "url: http://floe-platform-prometheus:9090" in datasource_payload
        assert "url: http://floe-platform-otel:9464" not in datasource_payload

        assert "floe_asset_materializations" in rendered
        assert "floe_asset_failures" in rendered
        assert "floe_lineage_marquez_event_sends" in rendered
        assert "floe_floe_asset_materializations" not in rendered
        assert "allow_structured_metadata: true" in rendered

        prometheus_configmap = next(
            doc
            for doc in documents
            if doc.get("kind") == "ConfigMap"
            and doc.get("metadata", {}).get("name") == "floe-platform-prometheus"
        )
        prometheus_config = yaml.safe_load(prometheus_configmap["data"]["prometheus.yml"])
        assert prometheus_config["scrape_configs"][0]["static_configs"][0]["targets"] == [
            "floe-platform-otel:9464"
        ]

    @pytest.mark.requirement("FR-044")
    def test_default_profile_does_not_render_disabled_backend_links(self) -> None:
        """Default chart must not link Grafana to disabled logs/metrics backends."""
        chart_path = CHARTS_DIR / "floe-platform"
        result = run_helm_template("test-release", chart_path, timeout=60)

        assert result.returncode == 0, (
            f"Helm template rendering failed: {result.returncode}\nstderr: {result.stderr}"
        )

        documents = [
            doc
            for doc in yaml.safe_load_all(result.stdout)
            if isinstance(doc, dict) and doc.get("kind")
        ]
        dashboard_configmaps = [
            doc
            for doc in documents
            if doc.get("kind") == "ConfigMap"
            and "grafana-dashboards" in doc.get("metadata", {}).get("name", "")
        ]
        assert dashboard_configmaps, "Grafana dashboard ConfigMap not rendered"
        for configmap in dashboard_configmaps:
            assert "observability-backends.json" not in configmap.get("data", {})

        datasource_configmaps = [
            doc
            for doc in documents
            if doc.get("kind") == "ConfigMap"
            and "grafana-datasources" in doc.get("metadata", {}).get("name", "")
        ]
        datasource_payload = yaml.safe_dump(datasource_configmaps)
        assert "type: loki" not in datasource_payload
        assert "type: prometheus" not in datasource_payload
        assert "type: jaeger" in datasource_payload

    @pytest.mark.requirement("FR-044")
    def test_demo_backend_name_overrides_keep_links_aligned(self) -> None:
        """Backend fullnameOverride values must propagate to rendered links."""
        chart_path = CHARTS_DIR / "floe-platform"
        result = run_helm_template(
            "test-release",
            chart_path,
            values_path=chart_path / "values-demo.yaml",
            set_values={
                "loki.fullnameOverride": "custom-loki",
                "prometheus.fullnameOverride": "custom-prometheus",
                "otel.fullnameOverride": "custom-otel",
                "otel.config.exporters.otlphttp/loki.endpoint": "http://custom-loki:3100/otlp",
                "dagster.dagsterWebserver.env[0].value": "http://custom-otel:4317",
                "dagster.dagsterDaemon.env[0].value": "http://custom-otel:4317",
            },
            timeout=60,
        )

        assert result.returncode == 0, (
            f"Helm template rendering failed: {result.returncode}\nstderr: {result.stderr}"
        )

        rendered = result.stdout
        documents = [
            doc for doc in yaml.safe_load_all(rendered) if isinstance(doc, dict) and doc.get("kind")
        ]
        names_by_kind = {
            (doc.get("kind"), doc.get("metadata", {}).get("name")) for doc in documents
        }

        assert ("Service", "custom-loki") in names_by_kind
        assert ("Service", "custom-prometheus") in names_by_kind
        assert ("Service", "custom-otel") in names_by_kind
        assert "endpoint: http://custom-loki:3100/otlp" in rendered
        assert "url: http://custom-prometheus:9090" in rendered

        prometheus_configmap = next(
            doc
            for doc in documents
            if doc.get("kind") == "ConfigMap"
            and doc.get("metadata", {}).get("name") == "custom-prometheus"
        )
        prometheus_config = yaml.safe_load(prometheus_configmap["data"]["prometheus.yml"])
        assert prometheus_config["scrape_configs"][0]["static_configs"][0]["targets"] == [
            "custom-otel:9464"
        ]

    @pytest.mark.requirement("FR-044")
    def test_custom_grafana_datasource_uid_matches_generated_dashboard(self) -> None:
        """Generated Prometheus datasource UID must match dashboard panel references."""
        chart_path = CHARTS_DIR / "floe-platform"
        result = run_helm_template(
            "test-release",
            chart_path,
            values_path=chart_path / "values-demo.yaml",
            set_values={"observability.grafana.datasourceUid": "custom-prom"},
            timeout=60,
        )

        assert result.returncode == 0, (
            f"Helm template rendering failed: {result.returncode}\nstderr: {result.stderr}"
        )

        documents = [
            doc
            for doc in yaml.safe_load_all(result.stdout)
            if isinstance(doc, dict) and doc.get("kind") == "ConfigMap"
        ]
        dashboard_configmap = next(
            doc
            for doc in documents
            if "grafana-dashboards" in doc.get("metadata", {}).get("name", "")
        )
        backend_dashboard = json.loads(dashboard_configmap["data"]["observability-backends.json"])
        prometheus_panel_uids = {
            panel["datasource"]["uid"]
            for panel in backend_dashboard["panels"]
            if panel["datasource"]["type"] == "prometheus"
        }
        assert prometheus_panel_uids == {"custom-prom"}

        datasource_configmap = next(
            doc
            for doc in documents
            if "grafana-datasources" in doc.get("metadata", {}).get("name", "")
        )
        datasource_config = yaml.safe_load(datasource_configmap["data"]["datasources.yaml"])
        prometheus_datasource = next(
            datasource
            for datasource in datasource_config["datasources"]
            if datasource["type"] == "prometheus"
        )
        assert prometheus_datasource["uid"] == "custom-prom"

    @pytest.mark.requirement("FR-044")
    def test_custom_grafana_datasources_render_when_supplied(self) -> None:
        """Non-empty observability.grafana.datasources should be rendered via tpl."""
        chart_path = CHARTS_DIR / "floe-platform"
        result = run_helm_template(
            "test-release",
            chart_path,
            set_values={
                "jaeger.enabled": "false",
                "observability.grafana.datasources[0].name": "ExternalPrometheus",
                "observability.grafana.datasources[0].uid": "external-prom",
                "observability.grafana.datasources[0].type": "prometheus",
                "observability.grafana.datasources[0].access": "proxy",
                "observability.grafana.datasources[0].url": "http://external-prometheus:9090",
                "observability.grafana.datasources[0].editable": "true",
            },
            timeout=60,
        )

        assert result.returncode == 0, (
            f"Helm template rendering failed: {result.returncode}\nstderr: {result.stderr}"
        )

        documents = [
            doc
            for doc in yaml.safe_load_all(result.stdout)
            if isinstance(doc, dict) and doc.get("kind") == "ConfigMap"
        ]
        datasource_configmap = next(
            doc
            for doc in documents
            if "grafana-datasources" in doc.get("metadata", {}).get("name", "")
        )
        datasource_payload = datasource_configmap["data"]["datasources.yaml"]
        assert "name: ExternalPrometheus" in datasource_payload
        assert "uid: external-prom" in datasource_payload
        assert "url: http://external-prometheus:9090" in datasource_payload

    @pytest.mark.requirement("FR-044")
    def test_custom_prometheus_scrape_configs_render_when_supplied(self) -> None:
        """prometheus.config.scrape_configs should render instead of being ignored."""
        chart_path = CHARTS_DIR / "floe-platform"
        result = run_helm_template(
            "test-release",
            chart_path,
            set_values={
                "prometheus.enabled": "true",
                "prometheus.config.scrape_configs[0].job_name": "custom-otel",
                "prometheus.config.scrape_configs[0].metrics_path": "/custom-metrics",
                "prometheus.config.scrape_configs[0].static_configs[0].targets[0]": (
                    "custom-otel:9999"
                ),
            },
            timeout=60,
        )

        assert result.returncode == 0, (
            f"Helm template rendering failed: {result.returncode}\nstderr: {result.stderr}"
        )

        documents = [
            doc
            for doc in yaml.safe_load_all(result.stdout)
            if isinstance(doc, dict) and doc.get("kind") == "ConfigMap"
        ]
        prometheus_configmap = next(
            doc
            for doc in documents
            if doc.get("metadata", {}).get("name") == "floe-platform-prometheus"
        )
        prometheus_config = yaml.safe_load(prometheus_configmap["data"]["prometheus.yml"])
        assert prometheus_config["scrape_configs"] == [
            {
                "job_name": "custom-otel",
                "metrics_path": "/custom-metrics",
                "static_configs": [{"targets": ["custom-otel:9999"]}],
            }
        ]

    @pytest.mark.requirement("9b-FR-004")
    def test_invalid_environment_rejected(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that invalid environment value is rejected."""
        invalid_values = {"global": {"environment": "invalid"}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_has_required_sections(self, floe_platform_schema: dict[str, Any]) -> None:
        """Test that schema defines expected top-level sections."""
        properties = floe_platform_schema.get("properties", {})
        expected = [
            "global",
            "namespace",
            "clusterMapping",
            "dagster",
            "postgresql",
            "polaris",
            "minio",
            "ingress",
        ]
        for section in expected:
            assert section in properties, f"Missing schema section: {section}"

    @pytest.mark.requirement("9b-FR-004")
    def test_polaris_bootstrap_grants_schema_has_expected_fields(
        self,
        floe_platform_schema: dict[str, Any],
    ) -> None:
        """Test that Polaris bootstrap grants are covered by values.schema.json."""
        grants_schema = floe_platform_schema["properties"]["polaris"]["properties"]["bootstrap"][
            "properties"
        ]["grants"]

        properties = grants_schema.get("properties", {})
        assert properties["enabled"]["type"] == "boolean"
        assert properties["catalogRole"]["type"] == "string"
        assert properties["principalRole"]["type"] == "string"
        assert properties["bootstrapPrincipal"]["type"] == "string"
        assert properties["privileges"]["type"] == "array"
        assert properties["privileges"]["items"]["type"] == "string"
        assert "enum" in properties["privileges"]["items"]

    @pytest.mark.requirement("9b-FR-004")
    def test_polaris_bootstrap_grants_enabled_must_be_boolean(
        self,
        floe_platform_schema: dict[str, Any],
    ) -> None:
        """Test that grants.enabled rejects string values."""
        invalid_values = {
            "polaris": {
                "bootstrap": {
                    "grants": {
                        "enabled": "true",
                    },
                },
            },
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_polaris_bootstrap_grants_privileges_must_be_valid_enum_values(
        self,
        floe_platform_schema: dict[str, Any],
    ) -> None:
        """Test that grants.privileges rejects unsupported Polaris privilege names."""
        invalid_values = {
            "polaris": {
                "bootstrap": {
                    "grants": {
                        "privileges": ["NOT_A_POLARIS_PRIVILEGE"],
                    },
                },
            },
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_values, floe_platform_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_polaris_bootstrap_grants_identity_fields_do_not_add_length_cap(
        self,
        floe_platform_schema: dict[str, Any],
    ) -> None:
        """Test that schema does not add a stricter role-name cap than runtime validation."""
        long_role_name = "platform_data_engineering_catalog_admin_role_for_customer_360_alpha"
        values = {
            "polaris": {
                "bootstrap": {
                    "grants": {
                        "enabled": True,
                        "catalogRole": long_role_name,
                        "principalRole": long_role_name,
                        "bootstrapPrincipal": long_role_name,
                        "privileges": ["CATALOG_MANAGE_CONTENT"],
                    },
                },
            },
        }

        jsonschema.validate(values, floe_platform_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFloeJobsSchema:
    """Tests for floe-jobs values schema validation."""

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_is_valid_json_schema(self, floe_jobs_schema: dict[str, Any]) -> None:
        """Test that the schema itself is a valid JSON Schema."""
        jsonschema.Draft7Validator.check_schema(floe_jobs_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_default_values_conform_to_schema(self, floe_jobs_schema: dict[str, Any]) -> None:
        """Test that default values.yaml conforms to schema."""
        values = load_values_file("floe-jobs")
        jsonschema.validate(values, floe_jobs_schema)

    @pytest.mark.requirement("9b-FR-004")
    def test_schema_has_required_sections(self, floe_jobs_schema: dict[str, Any]) -> None:
        """Test that schema defines expected top-level sections."""
        properties = floe_jobs_schema.get("properties", {})
        expected = ["global", "platform", "dbt", "ingestion", "custom", "resources"]
        for section in expected:
            assert section in properties, f"Missing schema section: {section}"

    @pytest.mark.requirement("9b-FR-004")
    def test_invalid_environment_rejected(self, floe_jobs_schema: dict[str, Any]) -> None:
        """Test that invalid environment value is rejected."""
        invalid_values = {"global": {"environment": "invalid"}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_values, floe_jobs_schema)
