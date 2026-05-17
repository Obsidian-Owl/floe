"""Customer 360 observability proof gate.

This gate is designed for the demo validation lane:

    make demo
    make demo-customer-360-run
    make demo-customer-360-validate

When services are absent it fails with backend-specific diagnostics instead of
skipping or reporting a generic platform error.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from testing.ci.customer360_observability import (
    Customer360ObservabilityConfig,
    EvidenceStatus,
    validate_customer360_observability,
)


@pytest.mark.e2e
@pytest.mark.platform_blackbox
@pytest.mark.requirement("platform-observability-defaults-task-7")
def test_customer360_observability_gate(trigger_lineage_run: Callable[..., None]) -> None:
    """A fresh Customer 360 run must have queryable observability evidence."""
    trigger_lineage_run(
        expected_namespace="customer-360",
        expected_job_name="customer-360",
    )

    result = validate_customer360_observability(Customer360ObservabilityConfig.from_env())

    assert result.run_id, _format_observability_failure(result)
    assert not result.failures, _format_observability_failure(result)

    expected_backends = {"dagster", "traces", "logs", "metrics", "lineage"}
    statuses = {backend.backend: backend.status for backend in result.backend_results}
    assert expected_backends <= set(statuses), _format_observability_failure(result)
    assert all(status is EvidenceStatus.PASS for status in statuses.values()), (
        _format_observability_failure(result)
    )

    for category in (
        "run_root_span",
        "dagster_asset_spans",
        "dbt_model_spans",
        "ingestion_spans",
        "catalog_storage_iceberg_spans",
    ):
        assert result.evidence.get(f"observability.traces.{category}") == "true", (
            _format_observability_failure(result)
        )


def _format_observability_failure(result: object) -> str:
    run_id = getattr(result, "run_id", None)
    evidence = getattr(result, "evidence", {})
    failures = getattr(result, "failures", [])
    lines = [
        "Customer 360 observability proof failed.",
        f"run_id={run_id or '<missing>'}",
    ]
    if isinstance(evidence, dict):
        lines.extend(f"evidence.{key}={value}" for key, value in sorted(evidence.items()))
    if isinstance(failures, list):
        lines.extend(f"failure={failure}" for failure in failures)
    return "\n".join(lines)
