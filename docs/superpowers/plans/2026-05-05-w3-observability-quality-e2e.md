# W3 Observability Quality E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove Customer 360 lineage, telemetry, and Great Expectations quality validation work end-to-end against real E2E services and Iceberg data.

**Architecture:** Keep W3 in the local E2E lane and reuse existing Floe fixtures. Add the missing GX real-data path by allowing the GX plugin to validate an explicitly supplied pandas DataFrame, then add an E2E that loads Customer 360 Iceberg data and runs a concrete `QualitySuite`. Tighten Jaeger evidence so stale traces do not satisfy the Alpha observability requirement.

**Tech Stack:** Python 3.10+, pytest, Pydantic v2 schemas, Great Expectations, pandas, PyIceberg/Polaris, Jaeger Query API, OpenTelemetry, existing Floe E2E fixtures.

---

## File Structure

- Modify `plugins/floe-quality-gx/src/floe_quality_gx/executor.py`
  - Add a `dataframe` connection path to `create_dataframe_from_connection()`.
  - Keep existing DuckDB behavior intact.
- Create `plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py`
  - Unit coverage for the DataFrame handoff and defensive copying.
- Create `tests/e2e/test_quality_gx_e2e.py`
  - Real Customer 360 Iceberg table load plus GX plugin validation.
- Modify `tests/e2e/test_observability.py`
  - Tighten `test_otel_traces_in_jaeger` so it emits fresh compile-time traces inside a bounded Jaeger query window.
- Existing files to read before editing:
  - `plugins/floe-quality-gx/src/floe_quality_gx/plugin.py`
  - `plugins/floe-quality-gx/src/floe_quality_gx/executor.py`
  - `tests/e2e/conftest.py`
  - `tests/e2e/test_data_pipeline.py`
  - `tests/e2e/test_observability_roundtrip_e2e.py`
  - `demo/customer-360/models/schema.yml`

---

### Task 1: Add DataFrame Handoff To GX Plugin

**Files:**
- Modify: `plugins/floe-quality-gx/src/floe_quality_gx/executor.py`
- Create: `plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py`

- [ ] **Step 1: Write failing unit tests for DataFrame connection support**

Create `plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py`:

```python
"""Unit tests for DataFrame-backed Great Expectations validation."""

from __future__ import annotations

import pandas as pd
import pytest
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import QualityCheck, QualitySuite
from floe_quality_gx import GreatExpectationsPlugin
from floe_quality_gx.executor import create_dataframe_from_connection


def test_create_dataframe_from_connection_accepts_explicit_dataframe() -> None:
    """DataFrame connection config returns the supplied data for validation."""
    source = pd.DataFrame(
        {
            "customer_id": ["C001", "C002"],
            "segment": ["enterprise", "smb"],
        }
    )

    result = create_dataframe_from_connection(
        {"dialect": "pandas", "dataframe": source},
        "mart_customer_360",
    )

    assert result.equals(source)
    assert result is not source


def test_create_dataframe_from_connection_rejects_non_dataframe() -> None:
    """DataFrame connection config must fail loudly for wrong object types."""
    with pytest.raises(
        TypeError,
        match="connection_config\\['dataframe'\\] must be a pandas DataFrame",
    ):
        create_dataframe_from_connection(
            {"dialect": "pandas", "dataframe": [{"customer_id": "C001"}]},
            "mart_customer_360",
        )


def test_gx_plugin_run_suite_validates_supplied_dataframe() -> None:
    """GreatExpectationsPlugin.run_suite validates checks against supplied data."""
    plugin = GreatExpectationsPlugin()
    dataframe = pd.DataFrame(
        {
            "customer_id": ["C001", "C002", "C003"],
            "segment": ["enterprise", "smb", "startup"],
        }
    )
    suite = QualitySuite(
        model_name="mart_customer_360",
        checks=[
            QualityCheck(
                name="customer_id_not_null",
                type="not_null",
                column="customer_id",
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
            ),
            QualityCheck(
                name="customer_id_unique",
                type="unique",
                column="customer_id",
                dimension=Dimension.CONSISTENCY,
                severity=SeverityLevel.CRITICAL,
            ),
            QualityCheck(
                name="segment_values",
                type="values_in_set",
                column="segment",
                dimension=Dimension.VALIDITY,
                severity=SeverityLevel.WARNING,
                parameters={"value_set": ["enterprise", "mid_market", "smb", "startup", "unknown"]},
            ),
            QualityCheck(
                name="row_count_bounds",
                type="row_count_between",
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
                parameters={"min_value": 3, "max_value": 3},
            ),
        ],
        timeout_seconds=30,
    )

    result = plugin.run_suite(suite, {"dialect": "pandas", "dataframe": dataframe})

    assert result.model_name == "mart_customer_360"
    assert result.suite_name == "mart_customer_360_suite"
    assert result.passed is True
    assert result.summary["total"] == 4
    assert result.summary["passed"] == 4
    assert result.summary["failed"] == 0
    assert {check.check_name for check in result.checks} == {
        "customer_id_not_null",
        "customer_id_unique",
        "segment_values",
        "row_count_bounds",
    }
    assert all(check.passed for check in result.checks)
    assert any(
        check.check_name == "customer_id_not_null" and check.records_checked == 3
        for check in result.checks
    )
```

- [ ] **Step 2: Run the focused unit tests and verify they fail**

Run:

```bash
pytest plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py -q
```

Expected: FAIL because `create_dataframe_from_connection()` currently returns an empty DataFrame for non-DuckDB dialects, and `run_suite()` cannot validate the supplied DataFrame.

- [ ] **Step 3: Add explicit DataFrame support**

Modify `plugins/floe-quality-gx/src/floe_quality_gx/executor.py` in `create_dataframe_from_connection()` after `dialect = connection_config.get("dialect", "duckdb")` and before the DuckDB branch:

```python
    if "dataframe" in connection_config or dialect in {"pandas", "dataframe"}:
        dataframe = connection_config.get("dataframe")
        if not isinstance(dataframe, pd.DataFrame):
            msg = "connection_config['dataframe'] must be a pandas DataFrame"
            raise TypeError(msg)
        return dataframe.copy(deep=True)
```

Keep the existing DuckDB branch unchanged.

- [ ] **Step 4: Run the focused unit tests and verify they pass**

Run:

```bash
pytest plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py -q
```

Expected: PASS.

- [ ] **Step 5: Run existing GX unit coverage**

Run:

```bash
pytest plugins/floe-quality-gx/tests/unit -q
```

Expected: PASS. Existing DuckDB/empty-check behavior must remain unchanged.

- [ ] **Step 6: Commit Task 1**

```bash
git add plugins/floe-quality-gx/src/floe_quality_gx/executor.py \
  plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py
git commit -m "Add DataFrame-backed GX validation"
```

---

### Task 2: Add Real-Iceberg GX E2E Validation

**Files:**
- Create: `tests/e2e/test_quality_gx_e2e.py`

- [ ] **Step 1: Write the failing E2E test**

Create `tests/e2e/test_quality_gx_e2e.py`:

```python
"""E2E tests for Great Expectations validation against real Iceberg data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import QualityCheck, QualitySuite
from floe_quality_gx import GreatExpectationsPlugin

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.polaris import rewrite_table_io_for_host_access


@pytest.mark.e2e
@pytest.mark.requirement("W3-QUALITY-GX")
class TestGreatExpectationsIcebergE2E(IntegrationTestBase):
    """Validate GX checks against Customer 360 data materialized in Iceberg."""

    required_services: ClassVar[list[str]] = [
        "polaris",
        "minio",
    ]

    def _load_customer_360_dataframe(self, polaris_client: Any) -> Any:
        """Load the Customer 360 mart table through Polaris and return pandas data."""
        namespace = "customer_360"
        table_name = "mart_customer_360"

        available_tables = [table[1] for table in polaris_client.list_tables(namespace)]
        assert table_name in available_tables, (
            f"Expected {namespace}.{table_name} to exist after dbt_pipeline_result. "
            f"Available tables: {available_tables}"
        )

        table = polaris_client.load_table(f"{namespace}.{table_name}")
        rewrite_table_io_for_host_access(table)
        dataframe = table.scan().to_arrow().to_pandas()
        assert not dataframe.empty, f"{namespace}.{table_name} should contain real demo rows"
        return dataframe

    @pytest.mark.parametrize("dbt_pipeline_result", ["customer-360"], indirect=True)
    def test_gx_plugin_validates_real_customer_360_iceberg_data(
        self,
        dbt_pipeline_result: tuple[str, Path],
        polaris_client: Any,
    ) -> None:
        """GreatExpectationsPlugin validates checks against real Iceberg data."""
        product, _project_dir = dbt_pipeline_result
        assert product == "customer-360"
        self.check_infrastructure("polaris")
        self.check_infrastructure("minio")

        dataframe = self._load_customer_360_dataframe(polaris_client)
        row_count = len(dataframe)
        assert row_count == 500, (
            "Customer 360 mart should preserve one row per raw customer. "
            f"Expected 500 rows, got {row_count}"
        )

        suite = QualitySuite(
            model_name="mart_customer_360",
            checks=[
                QualityCheck(
                    name="customer_id_not_null",
                    type="not_null",
                    column="customer_id",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheck(
                    name="customer_id_unique",
                    type="unique",
                    column="customer_id",
                    dimension=Dimension.CONSISTENCY,
                    severity=SeverityLevel.CRITICAL,
                ),
                QualityCheck(
                    name="segment_values",
                    type="values_in_set",
                    column="segment",
                    dimension=Dimension.VALIDITY,
                    severity=SeverityLevel.WARNING,
                    parameters={"value_set": ["enterprise", "mid_market", "smb", "startup", "unknown"]},
                ),
                QualityCheck(
                    name="row_count_bounds",
                    type="row_count_between",
                    dimension=Dimension.COMPLETENESS,
                    severity=SeverityLevel.WARNING,
                    parameters={"min_value": 500, "max_value": 500},
                ),
            ],
            timeout_seconds=60,
        )

        result = GreatExpectationsPlugin().run_suite(
            suite,
            {"dialect": "pandas", "dataframe": dataframe},
        )

        assert result.suite_name == "mart_customer_360_suite"
        assert result.model_name == "mart_customer_360"
        assert result.passed is True
        assert result.summary["total"] == 4
        assert result.summary["passed"] == 4
        assert result.summary["failed"] == 0

        check_names = {check.check_name for check in result.checks}
        assert check_names == {
            "customer_id_not_null",
            "customer_id_unique",
            "segment_values",
            "row_count_bounds",
        }
        assert all(check.passed for check in result.checks)
        assert any(
            check.check_name == "customer_id_not_null"
            and check.records_checked == row_count
            and check.records_failed == 0
            for check in result.checks
        )
```

- [ ] **Step 2: Run the focused E2E test**

Run with the local E2E stack active:

```bash
pytest tests/e2e/test_quality_gx_e2e.py -m e2e -q
```

Expected before Task 1 is implemented: FAIL because the GX plugin cannot validate the supplied DataFrame. Expected after Task 1: PASS if Polaris/MinIO/dbt E2E services are healthy.

- [ ] **Step 3: If row count differs, inspect the generated mart before changing assertions**

Run:

```bash
pytest tests/e2e/test_data_pipeline.py::TestDataPipeline::test_medallion_layers -q
```

Expected: PASS. The existing test asserts the Customer 360 mart row count is greater
than zero and does not exceed the raw customer count. If the new exact `500`
assertion fails, inspect the existing Customer 360 table contract with:

```bash
rg -n "mart_customer_360|raw_customers|SEED_ROW_COUNTS" tests/e2e/test_data_pipeline.py
```

Then update only the new E2E assertion to match the repo's existing Customer 360
mart contract.

- [ ] **Step 4: Commit Task 2**

```bash
git add tests/e2e/test_quality_gx_e2e.py
git commit -m "Add GX E2E validation for Customer 360 Iceberg data"
```

---

### Task 3: Tighten Jaeger Trace Freshness

**Files:**
- Modify: `tests/e2e/test_observability.py`

- [ ] **Step 1: Update imports for bounded fresh trace emission**

Modify the imports near the top of `tests/e2e/test_observability.py` so `time` is available:

```python
import json
import os
import re
import time
from collections.abc import Callable
```

- [ ] **Step 2: Replace `test_otel_traces_in_jaeger` with a fresh compile-time trace check**

In `tests/e2e/test_observability.py`, replace the body and signature of `test_otel_traces_in_jaeger` with:

```python
    @pytest.mark.e2e
    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-047")
    def test_otel_traces_in_jaeger(
        self,
        e2e_namespace: str,
        jaeger_client: httpx.Client,
        dagster_client: Any,
        project_root: Path,
    ) -> None:
        """Validate a fresh Customer 360 compilation trace is queryable in Jaeger."""
        from floe_core.compilation.stages import compile_pipeline
        from floe_core.telemetry.initialization import (
            ensure_telemetry_initialized,
            reset_telemetry,
        )
        from testing.fixtures.polling import wait_for_condition

        self.check_infrastructure("dagster")
        self.check_infrastructure("jaeger-query")

        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"
        service_name = "customer-360"
        start_time = int(time.time() * 1_000_000)

        saved_env: dict[str, str | None] = {
            "OTEL_EXPORTER_OTLP_ENDPOINT": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
            "OTEL_EXPORTER_OTLP_INSECURE": os.environ.get("OTEL_EXPORTER_OTLP_INSECURE"),
            "OTEL_SERVICE_NAME": os.environ.get("OTEL_SERVICE_NAME"),
        }
        try:
            reset_telemetry()
            os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ServiceEndpoint("otel-collector-grpc").url
            os.environ["OTEL_EXPORTER_OTLP_INSECURE"] = "true"
            os.environ["OTEL_SERVICE_NAME"] = service_name
            ensure_telemetry_initialized()

            artifacts = compile_pipeline(spec_path, manifest_path)
            assert artifacts.metadata.product_name == service_name
        finally:
            reset_telemetry()
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        end_time = int(time.time() * 1_000_000)

        def _fresh_trace_data() -> list[dict[str, Any]]:
            response = jaeger_client.get(
                "/api/traces",
                params={
                    "service": service_name,
                    "start": start_time,
                    "end": end_time + 60_000_000,
                    "limit": 20,
                },
            )
            if response.status_code != 200:
                return []
            return list(response.json().get("data") or [])

        traces_found = wait_for_condition(
            lambda: len(_fresh_trace_data()) > 0,
            timeout=30.0,
            interval=3.0,
            description="fresh customer-360 compilation traces in Jaeger",
            raise_on_timeout=False,
        )
        traces = _fresh_trace_data()
        if not traces_found or not traces:
            services_response = jaeger_client.get("/api/services")
            services = (
                services_response.json().get("data", [])
                if services_response.status_code == 200
                else []
            )
            pytest.fail(
                "OBSERVABILITY GAP: No fresh traces found for 'customer-360' "
                "inside the current test window.\n"
                f"Available services: {services}\n"
                "Expected compilation spans to export through OTel Collector to Jaeger."
            )

        first_trace = traces[0]
        assert "traceID" in first_trace, "Trace missing traceID"
        spans = first_trace.get("spans", [])
        assert spans, "Fresh trace has no spans"

        operation_names = [span.get("operationName", "") for span in spans]
        assert all(operation_names), f"Fresh trace contains empty operation names: {operation_names}"

        tag_keys = {
            tag.get("key", "")
            for span in spans
            for tag in span.get("tags", [])
        }
        domain_attributes = [
            key
            for key in tag_keys
            if key.startswith(("compile.", "governance.", "enforcement.", "floe."))
        ]
        assert domain_attributes, (
            "TRACE GAP: Fresh customer-360 trace has no Floe domain attributes.\n"
            f"Tag keys found: {sorted(tag_keys)}"
        )
```

- [ ] **Step 3: Run the targeted Jaeger E2E**

Run with the local E2E stack active:

```bash
pytest tests/e2e/test_observability.py::TestObservability::test_otel_traces_in_jaeger -m e2e -q
```

Expected: PASS when OTel Collector and Jaeger are healthy. FAIL should clearly say whether there are no fresh traces, no spans, or missing domain attributes.

- [ ] **Step 4: Run the existing round-trip trace test**

Run:

```bash
pytest tests/e2e/test_observability_roundtrip_e2e.py::TestObservabilityRoundTrip::test_compilation_generates_traces -m e2e -q
```

Expected: PASS. If this fails with the same no-fresh-traces message, fix telemetry export wiring rather than weakening assertions.

- [ ] **Step 5: Commit Task 3**

```bash
git add tests/e2e/test_observability.py
git commit -m "Require fresh Jaeger traces in observability E2E"
```

---

### Task 4: Final Verification And Review

**Files:**
- Verify all files changed in Tasks 1-3.

- [ ] **Step 1: Run focused unit tests**

```bash
pytest plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py -q
pytest plugins/floe-quality-gx/tests/unit -q
```

Expected: PASS.

- [ ] **Step 2: Run focused E2E tests**

With the local E2E stack active, run:

```bash
pytest tests/e2e/test_quality_gx_e2e.py -m e2e -q
pytest tests/e2e/test_observability.py::TestObservability::test_otel_traces_in_jaeger -m e2e -q
pytest tests/e2e/test_lineage_roundtrip_e2e.py::TestLineageRoundTrip::test_runtime_lifecycle_runs_visible_for_compiled_product -m e2e -q
```

Expected: PASS. The lineage command is verification-only because existing tests already assert a fresh Customer 360 Marquez run.

- [ ] **Step 3: Run lint/type checks for touched Python files**

```bash
ruff check plugins/floe-quality-gx/src/floe_quality_gx/executor.py \
  plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py \
  tests/e2e/test_quality_gx_e2e.py \
  tests/e2e/test_observability.py
ruff format --check plugins/floe-quality-gx/src/floe_quality_gx/executor.py \
  plugins/floe-quality-gx/tests/unit/test_dataframe_connection.py \
  tests/e2e/test_quality_gx_e2e.py \
  tests/e2e/test_observability.py
```

Expected: PASS.

- [ ] **Step 4: Run the local E2E lane when practical**

```bash
make test-e2e
```

Expected: PASS. If this is too expensive for the current session, record the focused E2E results and explicitly state that full `make test-e2e` was not run.

- [ ] **Step 5: Review changed files**

```bash
git diff --stat HEAD~3..HEAD
git diff HEAD~3..HEAD -- plugins/floe-quality-gx/src/floe_quality_gx/executor.py
git diff HEAD~3..HEAD -- tests/e2e/test_quality_gx_e2e.py
git diff HEAD~3..HEAD -- tests/e2e/test_observability.py
```

Expected:

- production change is limited to the GX DataFrame connection path;
- new GX E2E uses real `dbt_pipeline_result`, `polaris_client`, and Iceberg table data;
- Jaeger test uses a bounded time window around a fresh compilation;
- no mocks are introduced in the E2E path.

- [ ] **Step 6: Final commit if verification-only fixes were needed**

Only if Task 4 required follow-up edits:

```bash
git add <changed-files>
git commit -m "Stabilize W3 observability quality E2E validation"
```

---

## Self-Review

- Spec coverage:
  - Lineage fresh evidence is covered by Task 4 verification of the existing fresh-run lineage E2E.
  - Telemetry fresh evidence is covered by Task 3.
  - GX real-Iceberg evidence is covered by Tasks 1 and 2.
  - Small production wiring fixes are limited to Task 1.
- Placeholder scan:
  - No placeholder markers or unspecified implementation steps are present.
  - All code-changing steps include concrete code.
- Type consistency:
  - `QualityCheck`, `QualitySuite`, `Dimension`, and `SeverityLevel` imports match existing schema modules.
  - DataFrame handoff uses `connection_config["dataframe"]` consistently in unit and E2E tests.
  - Jaeger trace parsing follows the existing `{"data": [...]}` API shape used in current tests.
