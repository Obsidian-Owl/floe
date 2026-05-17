"""Tests for dbt per-node runtime observability records."""

from __future__ import annotations

from types import SimpleNamespace

from floe_dbt_core.callbacks import (
    DBTEventCollector,
    DBTNodeRecord,
    dbt_node_records_from_run_results,
)


def test_run_result_record_includes_node_context_without_error_secrets() -> None:
    """run_results.json entries become secret-free per-node records."""
    records = dbt_node_records_from_run_results(
        {
            "results": [
                {
                    "unique_id": "model.customer_360.stg_orders",
                    "status": "error",
                    "execution_time": 1.25,
                    "error_type": "DatabaseError",
                    "message": "password=super-secret failed",
                    "node": {
                        "name": "stg_orders",
                        "resource_type": "model",
                    },
                }
            ]
        }
    )

    assert records == [
        DBTNodeRecord(
            unique_id="model.customer_360.stg_orders",
            node_name="stg_orders",
            resource_type="model",
            status="error",
            duration_seconds=1.25,
            error_type="DatabaseError",
        )
    ]
    attrs = records[0].to_span_attributes()
    labels = records[0].to_metric_labels()
    assert attrs["dbt.node.name"] == "stg_orders"
    assert attrs["dbt.node.resource_type"] == "model"
    assert attrs["dbt.node.status"] == "error"
    assert attrs["dbt.node.duration_seconds"] == 1.25
    assert attrs["dbt.node.error_type"] == "DatabaseError"
    assert labels == {
        "dbt.resource_type": "model",
        "dbt.status": "error",
        "dbt.error_type": "DatabaseError",
    }
    assert "super-secret" not in str(attrs)
    assert "password" not in str(labels)


def test_run_result_error_type_is_bounded_and_secret_free() -> None:
    """run_results error_type values cannot become credential-bearing labels."""
    records = dbt_node_records_from_run_results(
        {
            "results": [
                {
                    "unique_id": "model.customer_360.stg_orders",
                    "status": "error",
                    "execution_time": 1.25,
                    "error_type": "DatabaseError password=super-secret",
                    "node": {
                        "name": "stg_orders",
                        "resource_type": "model",
                    },
                }
            ]
        }
    )

    assert records[0].error_type == "DbtNodeFailure"
    assert records[0].to_metric_labels()["dbt.error_type"] == "DbtNodeFailure"
    assert "super-secret" not in str(records[0].to_span_attributes())
    assert "password" not in str(records[0].to_metric_labels()).lower()


def test_callback_record_includes_node_name_resource_type_status_and_duration() -> None:
    """Synthetic dbt callbacks produce per-node records."""
    collector = DBTEventCollector()
    event = SimpleNamespace(
        info=SimpleNamespace(name="NodeFinished", level="info", msg="completed"),
        data=SimpleNamespace(
            node_info={
                "unique_id": "test.customer_360.not_null_orders_id",
                "node_name": "not_null_orders_id",
                "resource_type": "test",
            },
            status="pass",
            execution_time=0.42,
        ),
    )

    collector.callback(event)

    records = collector.node_records
    assert len(records) == 1
    assert records[0].node_name == "not_null_orders_id"
    assert records[0].resource_type == "test"
    assert records[0].status == "pass"
    assert records[0].duration_seconds == 0.42
    assert records[0].to_span_attributes()["dbt.node.unique_id"] == (
        "test.customer_360.not_null_orders_id"
    )


def test_callback_error_type_is_bounded_and_secret_free() -> None:
    """Callback error_type values cannot become credential-bearing attributes."""
    collector = DBTEventCollector()
    event = SimpleNamespace(
        info=SimpleNamespace(name="NodeErrored", level="error", msg="failed"),
        data=SimpleNamespace(
            node_info={
                "unique_id": "model.customer_360.stg_orders",
                "node_name": "stg_orders",
                "resource_type": "model",
            },
            status="error",
            execution_time=0.42,
            error_type="https://user:" + "super-secret@example.com/dbt/Error",
        ),
    )

    collector.callback(event)

    assert collector.node_records[0].error_type == "DbtNodeFailure"
    attrs = collector.node_records[0].to_span_attributes()
    labels = collector.node_records[0].to_metric_labels()
    assert "super-secret" not in str(attrs)
    assert "https://" not in str(labels)
