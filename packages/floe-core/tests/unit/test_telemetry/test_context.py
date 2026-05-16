"""Unit tests for shared observability context."""

from __future__ import annotations

from floe_core.telemetry.context import ObservabilityContext


def test_observability_context_exports_span_attributes() -> None:
    """Context exports secret-free span attributes for runtime correlation."""
    ctx = ObservabilityContext(
        product_name="customer-360",
        product_version="0.1.0",
        environment="demo",
        namespace="customer_360",
        run_id="run-123",
        asset_key="customer_360.mart_customer_360",
        stage="dbt",
        table_name="customer_360.mart_customer_360",
        plugin_type="dbt",
        plugin_name="dbt-core",
        lineage_namespace="customer-360",
    )

    attrs = ctx.to_span_attributes()

    assert attrs["floe.product.name"] == "customer-360"
    assert attrs["floe.environment"] == "demo"
    assert attrs["floe.run.id"] == "run-123"
    assert attrs["floe.asset.key"] == "customer_360.mart_customer_360"
    assert attrs["floe.table.name"] == "customer_360.mart_customer_360"
    assert attrs["floe.plugin.type"] == "dbt"
    assert attrs["floe.plugin.name"] == "dbt-core"
    assert attrs["floe.lineage.namespace"] == "customer-360"


def test_observability_context_metric_labels_exclude_high_cardinality_run_id() -> None:
    """Metric labels include only bounded-cardinality dimensions."""
    ctx = ObservabilityContext(
        product_name="customer-360",
        product_version="0.1.0",
        environment="demo",
        namespace="customer_360",
        run_id="run-123",
        asset_key="customer_360.mart_customer_360",
        stage="dbt",
        table_name="customer_360.mart_customer_360",
        plugin_type="dbt",
        plugin_name="dbt-core",
    )

    labels = ctx.to_metric_labels(status="success")

    assert labels == {
        "floe.product.name": "customer-360",
        "floe.environment": "demo",
        "floe.namespace": "customer_360",
        "floe.stage": "dbt",
        "floe.plugin.type": "dbt",
        "floe.plugin.name": "dbt-core",
        "floe.status": "success",
    }
    assert "floe.run.id" not in labels
    assert "floe.asset.key" not in labels
    assert "floe.table.name" not in labels


def test_observability_context_rejects_secret_like_fields() -> None:
    """Secret-like extra attribute keys are removed before export."""
    ctx = ObservabilityContext(
        product_name="customer-360",
        product_version="0.1.0",
        environment="demo",
        namespace="customer_360",
        plugin_type="storage",
        plugin_name="minio",
        extra_attributes={
            "floe.storage.bucket": "warehouse",
            "aws.secret_access_key": "must-not-leak",  # pragma: allowlist secret
            "password": "must-not-leak",  # pragma: allowlist secret
        },
    )

    attrs = ctx.to_span_attributes()

    assert attrs["floe.storage.bucket"] == "warehouse"
    assert "aws.secret_access_key" not in attrs
    assert "password" not in attrs
