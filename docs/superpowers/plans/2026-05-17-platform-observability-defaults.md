# Platform Observability Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Floe emit and validate queryable traces, logs, metrics, and lineage for every alpha data product by default, with Customer 360 as the live proof point.

**Architecture:** Build this as a sequence of small PRs. First create a shared observability context, lifecycle taxonomy, and registry-surface decisions in `floe-core`; then add Dagster runtime envelopes and plugin-domain instrumentation; then wire logs and metrics into an alpha backend profile; finally harden Customer 360 validation and docs. Plugins emit OpenTelemetry and OpenLineage signals only; backend choice stays in deployment bindings and chart values.

**Tech Stack:** Python 3.10+, Pydantic v2, structlog, OpenTelemetry traces/metrics/log correlation, Dagster, dbt Core, dlt, PyIceberg, Helm, OTel Collector, Grafana, Prometheus-compatible metrics, Loki-compatible logs, Jaeger or Tempo traces, Marquez OpenLineage, pytest, DevPod+Hetzner validation.

---

## Scope And PR Map

Do not implement this as one PR. Use these branches or equivalent worktrees from a clean `origin/main`.

| PR | Suggested branch | Purpose | Can run in parallel |
| --- | --- | --- | --- |
| 1 | `observability/context-contract` | Shared context, semantic conventions, lifecycle taxonomy, registry-surface decisions | No; foundation |
| 2 | `observability/dagster-runtime-envelope` | Default runtime spans/logs/metrics around generated Dagster execution units | After PR 1 |
| 3 | `observability/data-plugin-uplift` | dbt, dlt, Iceberg, catalog, storage, lineage, quality instrumentation | After PR 1; can split by package |
| 4 | `observability/security-lifecycle-uplift` | secrets, identity, RBAC, alert, network-security deployment evidence | After PR 1; can run beside PR 3 |
| 5 | `observability/backend-profile` | OTel collector, Loki/log backend, metric export, Grafana datasources/dashboards | After PR 1; can run beside PR 2 and PR 3 |
| 6 | `observability/customer360-proof-gate` | Automated and manual Customer 360 proof for logs, traces, metrics, lineage | After PR 2, PR 3, PR 5 |
| 7 | `observability/docs-release-gate` | README, docs, troubleshooting, release gate docs | After PR 6 |

Each PR should be independently reviewable and should end with a small evidence note in its PR description.

## File Structure

### Create

- `packages/floe-core/src/floe_core/telemetry/context.py`: runtime `ObservabilityContext`, label sanitization, and context-to-attribute conversion.
- `packages/floe-core/src/floe_core/telemetry/lifecycle.py`: shared plugin lifecycle span/log/metric helpers.
- `packages/floe-core/tests/unit/test_telemetry/test_context.py`: unit tests for context construction, secret exclusion, and low-cardinality metric labels.
- `packages/floe-core/tests/unit/test_telemetry/test_lifecycle.py`: unit tests for lifecycle helpers.
- `tests/contract/test_plugin_observability_contract.py`: contract test that every published alpha plugin has an explicit observability decision.
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime_observability.py`: Dagster asset/job envelope helpers.
- `plugins/floe-orchestrator-dagster/tests/unit/test_runtime_observability.py`: envelope unit tests.
- `tests/e2e/test_customer360_observability_gate.py`: Customer 360 proof gate across traces, logs, metrics, and lineage.
- `testing/ci/customer360_observability.py`: reusable backend query helpers for the demo validator.
- `charts/floe-platform/templates/configmap-loki.yaml`: Loki-compatible log backend configuration for the alpha proof profile when no dependency chart is used.
- `charts/floe-platform/templates/deployment-loki.yaml`: Loki-compatible log backend deployment for the alpha proof profile when no dependency chart is used.
- `charts/floe-platform/templates/service-loki.yaml`: Loki-compatible log backend service for the alpha proof profile when no dependency chart is used.

### Modify

- `packages/floe-core/src/floe_core/telemetry/conventions.py`: align constants with the new context and metric label contract.
- `packages/floe-core/src/floe_core/telemetry/metrics.py`: add bounded-label helper methods or consume context labels from the new context.
- `packages/floe-core/src/floe_core/telemetry/logging.py`: ensure structured logs include Floe context fields as well as trace/span IDs.
- `packages/floe-core/src/floe_core/plugins/lifecycle.py`: wrap startup, shutdown, and health checks in lifecycle instrumentation.
- `packages/floe-core/src/floe_core/plugin_types.py`: resolve the `floe.network_security` registry gap or document the separate extension path in a contract test.
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`: wrap generated transform assets.
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`: wrap generated ingestion assets.
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/semantic_sync.py`: wrap semantic sync assets.
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py`: instrument lineage event send/flush outcomes.
- `plugins/floe-dbt-core/src/floe_dbt_core/callbacks.py`: convert dbt events/run results into per-node observability records.
- `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py`: attach per-node records to command spans and metrics.
- `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`: enrich ingestion spans/logs/metrics with source and destination context.
- `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py`: trace table load/existence/read validation paths in addition to create/drop.
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`: instrument catalog operations required by the alpha path.
- `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py`: instrument deployment binding/config generation and logical object operations.
- `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py`: instrument backend config and connection validation.
- `plugins/floe-quality-gx/src/floe_quality_gx/plugin.py`: instrument suite/check execution and quality scores.
- `charts/floe-platform/values.yaml`: add pluggable log backend profile and real metrics/logs collector exporters.
- `charts/floe-platform/values-demo.yaml`: enable alpha proof backend defaults.
- `charts/floe-platform/templates/configmap-otel.yaml`: align collector configuration with resolved backend profile values.
- `charts/floe-platform/templates/grafana-dashboards-configmap.yaml`: update dashboards to use emitted Floe metrics and log queries.
- `charts/floe-platform/templates/validate-otel-endpoints.yaml`: validate log, metric, and trace endpoints for the alpha proof profile.
- `testing/ci/validate_customer_360_demo.py`: assert fresh logs, metrics, traces, and lineage.
- `Makefile`: ensure `demo-customer-360-validate` runs the expanded proof.
- `docs/contracts/observability-attributes.md`: update the attribute and metric contract.
- `README.md`, demo docs, release docs, and troubleshooting docs: update user-facing observability claims.

## Task 1: Shared Observability Context And Semantic Contract

**Files:**
- Create: `packages/floe-core/src/floe_core/telemetry/context.py`
- Modify: `packages/floe-core/src/floe_core/telemetry/conventions.py`
- Modify: `packages/floe-core/src/floe_core/telemetry/metrics.py`
- Test: `packages/floe-core/tests/unit/test_telemetry/test_context.py`

- [ ] **Step 1: Write failing context tests**

Create `packages/floe-core/tests/unit/test_telemetry/test_context.py`:

```python
from __future__ import annotations

from floe_core.telemetry.context import ObservabilityContext


def test_observability_context_exports_span_attributes() -> None:
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
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_telemetry/test_context.py -q
```

Expected: fails with `ModuleNotFoundError` for `floe_core.telemetry.context`.

- [ ] **Step 3: Implement `ObservabilityContext`**

Create `packages/floe-core/src/floe_core/telemetry/context.py`:

```python
"""Runtime observability context for Floe-managed execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_SECRET_KEY_MARKERS = ("secret", "password", "token", "credential", "private_key")


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_KEY_MARKERS)


def _clean_value(value: Any) -> str | int | float | bool:
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)


@dataclass(frozen=True)
class ObservabilityContext:
    """Secret-free context attached to traces, logs, metrics, and lineage."""

    product_name: str
    product_version: str
    environment: str
    namespace: str
    run_id: str | None = None
    asset_key: str | None = None
    stage: str | None = None
    table_name: str | None = None
    plugin_type: str | None = None
    plugin_name: str | None = None
    lineage_namespace: str | None = None
    extra_attributes: dict[str, Any] = field(default_factory=dict)

    def to_span_attributes(self) -> dict[str, str | int | float | bool]:
        attrs: dict[str, str | int | float | bool] = {
            "floe.product.name": self.product_name,
            "floe.product.version": self.product_version,
            "floe.environment": self.environment,
            "floe.namespace": self.namespace,
        }
        optional = {
            "floe.run.id": self.run_id,
            "floe.asset.key": self.asset_key,
            "floe.stage": self.stage,
            "floe.table.name": self.table_name,
            "floe.plugin.type": self.plugin_type,
            "floe.plugin.name": self.plugin_name,
            "floe.lineage.namespace": self.lineage_namespace,
        }
        attrs.update({key: value for key, value in optional.items() if value is not None})
        attrs.update(
            {
                key: _clean_value(value)
                for key, value in self.extra_attributes.items()
                if not _is_secret_key(key)
            }
        )
        return attrs

    def to_log_fields(self) -> dict[str, str | int | float | bool]:
        return self.to_span_attributes()

    def to_metric_labels(self, *, status: str | None = None) -> dict[str, str]:
        labels = {
            "floe.product.name": self.product_name,
            "floe.environment": self.environment,
            "floe.namespace": self.namespace,
        }
        if self.stage is not None:
            labels["floe.stage"] = self.stage
        if self.plugin_type is not None:
            labels["floe.plugin.type"] = self.plugin_type
        if self.plugin_name is not None:
            labels["floe.plugin.name"] = self.plugin_name
        if status is not None:
            labels["floe.status"] = status
        return labels
```

- [ ] **Step 4: Export the context**

Modify `packages/floe-core/src/floe_core/telemetry/__init__.py` to export `ObservabilityContext`:

```python
from floe_core.telemetry.context import ObservabilityContext
```

Add `ObservabilityContext` to `__all__`.

- [ ] **Step 5: Run context tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_telemetry/test_context.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Run existing telemetry unit tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_telemetry packages/floe-core/tests/unit/telemetry -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add packages/floe-core/src/floe_core/telemetry/context.py \
  packages/floe-core/src/floe_core/telemetry/__init__.py \
  packages/floe-core/src/floe_core/telemetry/conventions.py \
  packages/floe-core/tests/unit/test_telemetry/test_context.py
git commit -m "Add shared observability context"
```

## Task 2: Plugin Lifecycle Observability And Registry Decisions

**Files:**
- Create: `packages/floe-core/src/floe_core/telemetry/lifecycle.py`
- Modify: `packages/floe-core/src/floe_core/plugins/lifecycle.py`
- Modify: `packages/floe-core/src/floe_core/plugin_types.py`
- Test: `packages/floe-core/tests/unit/test_telemetry/test_lifecycle.py`
- Test: `tests/contract/test_plugin_observability_contract.py`

- [ ] **Step 1: Write failing lifecycle helper tests**

Create `packages/floe-core/tests/unit/test_telemetry/test_lifecycle.py`:

```python
from __future__ import annotations

from floe_core.telemetry.lifecycle import plugin_lifecycle_attributes


def test_plugin_lifecycle_attributes_are_secret_free() -> None:
    attrs = plugin_lifecycle_attributes(
        plugin_type="SECRETS",
        plugin_name="k8s",
        plugin_version="0.1.0",
        floe_api_version="0.1",
        phase="health_check",
        status="unhealthy",
        error_type="SecretBackendUnavailableError",
        extra={"token": "must-not-leak", "backend": "kubernetes"},
    )

    assert attrs["floe.plugin.type"] == "SECRETS"
    assert attrs["floe.plugin.name"] == "k8s"
    assert attrs["floe.plugin.lifecycle.phase"] == "health_check"
    assert attrs["floe.plugin.lifecycle.status"] == "unhealthy"
    assert attrs["floe.error.type"] == "SecretBackendUnavailableError"
    assert attrs["backend"] == "kubernetes"
    assert "token" not in attrs
```

- [ ] **Step 2: Write failing registry contract test**

Create `tests/contract/test_plugin_observability_contract.py`:

```python
from __future__ import annotations

from pathlib import Path

from floe_core.plugin_types import PluginType

ROOT = Path(__file__).resolve().parents[2]


def test_network_security_entry_point_has_explicit_registry_decision() -> None:
    pyproject = ROOT / "plugins" / "floe-network-security-k8s" / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    assert '[project.entry-points."floe.network_security"]' in text
    assert (
        hasattr(PluginType, "NETWORK_SECURITY")
        or "network_security is documented as a non-PluginType extension" in text
    )


def test_alpha_plugin_types_have_observability_categories() -> None:
    expected = {
        "COMPUTE",
        "ORCHESTRATOR",
        "CATALOG",
        "STORAGE",
        "TELEMETRY_BACKEND",
        "LINEAGE_BACKEND",
        "DBT",
        "SEMANTIC_LAYER",
        "INGESTION",
        "SECRETS",
        "IDENTITY",
        "QUALITY",
        "RBAC",
        "ALERT_CHANNEL",
    }

    assert expected.issubset({member.name for member in PluginType})
```

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_telemetry/test_lifecycle.py \
  tests/contract/test_plugin_observability_contract.py -q
```

Expected: lifecycle module is missing; registry test fails until network security has an explicit decision.

- [ ] **Step 4: Implement lifecycle attributes**

Create `packages/floe-core/src/floe_core/telemetry/lifecycle.py`:

```python
"""Shared plugin lifecycle observability helpers."""

from __future__ import annotations

from typing import Any

from floe_core.telemetry.context import _is_secret_key, _clean_value


def plugin_lifecycle_attributes(
    *,
    plugin_type: str,
    plugin_name: str,
    plugin_version: str,
    floe_api_version: str,
    phase: str,
    status: str,
    error_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, str | int | float | bool]:
    attrs: dict[str, str | int | float | bool] = {
        "floe.plugin.type": plugin_type,
        "floe.plugin.name": plugin_name,
        "floe.plugin.version": plugin_version,
        "floe.plugin.floe_api_version": floe_api_version,
        "floe.plugin.lifecycle.phase": phase,
        "floe.plugin.lifecycle.status": status,
    }
    if error_type is not None:
        attrs["floe.error.type"] = error_type
    if extra:
        attrs.update(
            {
                key: _clean_value(value)
                for key, value in extra.items()
                if not _is_secret_key(key)
            }
        )
    return attrs
```

- [ ] **Step 5: Resolve the network security registry surface**

Prefer adding `NETWORK_SECURITY = "floe.network_security"` to `PluginType` because the repo already ships a plugin package under that entry point.

Modify `packages/floe-core/src/floe_core/plugin_types.py`:

```python
    NETWORK_SECURITY = "floe.network_security"
```

Update the enum docstring count and description from 14 to 15 categories. If this causes release or docs validators to fail, update those validators in the same commit so the repo has one source of truth.

- [ ] **Step 6: Instrument plugin lifecycle manager**

Modify `packages/floe-core/src/floe_core/plugins/lifecycle.py` so `activate_plugin`, `shutdown_all`, and `health_check_all` create spans and structured logs using `plugin_lifecycle_attributes()`. Use span names:

```text
floe.plugin.lifecycle.startup
floe.plugin.lifecycle.shutdown
floe.plugin.lifecycle.health_check
```

Record duration metrics:

```text
floe.plugin.lifecycle.duration
floe.plugin.lifecycle.failures
```

Labels must be limited to plugin type, plugin name, phase, and status.

- [ ] **Step 7: Run lifecycle and registry tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/test_telemetry/test_lifecycle.py \
  packages/floe-core/tests/unit/test_plugin_registry.py \
  tests/contract/test_plugin_observability_contract.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add packages/floe-core/src/floe_core/telemetry/lifecycle.py \
  packages/floe-core/src/floe_core/plugins/lifecycle.py \
  packages/floe-core/src/floe_core/plugin_types.py \
  packages/floe-core/tests/unit/test_telemetry/test_lifecycle.py \
  tests/contract/test_plugin_observability_contract.py
git commit -m "Instrument plugin lifecycle observability"
```

## Task 3: Dagster Runtime Envelope

**Files:**
- Create: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime_observability.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py`
- Modify: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/semantic_sync.py`
- Test: `plugins/floe-orchestrator-dagster/tests/unit/test_runtime_observability.py`

- [ ] **Step 1: Write failing envelope tests**

Create `plugins/floe-orchestrator-dagster/tests/unit/test_runtime_observability.py` with tests that call a wrapper around a fake Dagster context and assert:

- span attributes include `floe.product.name`, `floe.run.id`, `floe.asset.key`, `floe.plugin.type`, and `floe.status`;
- success records `floe.asset.materializations`;
- failure records `floe.asset.failures` and sets span error status;
- logs include the same context fields.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_runtime_observability.py -q
```

Expected: fails because the helper does not exist.

- [ ] **Step 3: Create runtime envelope helper**

Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime_observability.py` with:

```python
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import structlog
from opentelemetry import trace

from floe_core.telemetry.context import ObservabilityContext
from floe_core.telemetry.metrics import MetricRecorder
from floe_core.telemetry.tracer_factory import get_tracer

T = TypeVar("T")

logger = structlog.get_logger(__name__)
tracer = get_tracer("floe.orchestrator.dagster.runtime")
metrics = MetricRecorder(name="floe.orchestrator.dagster.runtime")


def run_observed_asset(
    *,
    context: ObservabilityContext,
    operation_name: str,
    fn: Callable[[], T],
) -> T:
    with tracer.start_as_current_span(operation_name, attributes=context.to_span_attributes()) as span:
        logger.info("floe_asset_started", **context.to_log_fields())
        try:
            result = fn()
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, type(exc).__name__))
            metrics.increment(
                "floe.asset.failures",
                labels=context.to_metric_labels(status="failure"),
                unit="1",
            )
            logger.error(
                "floe_asset_failed",
                error_type=type(exc).__name__,
                **context.to_log_fields(),
            )
            raise
        metrics.increment(
            "floe.asset.materializations",
            labels=context.to_metric_labels(status="success"),
            unit="1",
        )
        logger.info("floe_asset_completed", **context.to_log_fields())
        return result
```

- [ ] **Step 4: Wire transform, ingestion, and semantic assets**

Wrap the bodies of generated asset functions in:

```python
return run_observed_asset(
    context=observability_context,
    operation_name=f"floe.asset.{asset_name}",
    fn=lambda: existing_asset_body(),
)
```

Do not change dbt execution ownership. The wrapper starts the platform asset span and delegates existing work.

- [ ] **Step 5: Run orchestrator unit tests**

Run:

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/runtime_observability.py \
  plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py \
  plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py \
  plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/semantic_sync.py \
  plugins/floe-orchestrator-dagster/tests/unit/test_runtime_observability.py
git commit -m "Add Dagster runtime observability envelope"
```

## Task 4: Data Plugin Runtime Uplift

**Files:**
- Modify: `plugins/floe-dbt-core/src/floe_dbt_core/callbacks.py`
- Modify: `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py`
- Modify: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Modify: `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py`
- Modify: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- Modify: `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py`
- Modify: `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py`
- Modify: `plugins/floe-quality-gx/src/floe_quality_gx/plugin.py`
- Test: focused unit tests in each touched package.

- [ ] **Step 1: Add dbt per-node observability tests**

Extend `plugins/floe-dbt-core` tests so synthetic dbt callback/run-result data produces per-node records with node name, resource type, status, duration, and sanitized error type.

- [ ] **Step 2: Implement dbt node records**

Use existing `DBTEventCollector` in `plugins/floe-dbt-core/src/floe_dbt_core/callbacks.py`. Add a small record model or dataclass that turns callbacks and `run_results.json` entries into span attributes and metric labels.

- [ ] **Step 3: Add dlt context tests**

Add tests proving `DltIngestionPlugin.run()` records source type, source name, destination table, rows, bytes, duration, and status without secret values.

- [ ] **Step 4: Implement dlt enrichment**

Update `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py` so `ingestion_span()` receives source and destination context from `run_kwargs`, and metrics/logs use `ObservabilityContext`.

- [ ] **Step 5: Add Iceberg lifecycle tests**

Add tests proving `load_table()`, `table_exists()`, and any read validation helper emit spans with namespace/table/status attributes.

- [ ] **Step 6: Implement Iceberg lifecycle spans**

Modify `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py` using the existing `@traced` pattern already used by `create_table()` and `drop_table()`.

- [ ] **Step 7: Add catalog and storage tests**

Add focused tests for Polaris and MinIO plugin observability around connect, deployment binding/config generation, health checks, and logical storage operations.

- [ ] **Step 8: Implement catalog and storage instrumentation**

Use sanitized endpoint identity and logical storage identity only. Do not include access keys, secret keys, session tokens, presigned URLs, or full credential-bearing connection strings.

- [ ] **Step 9: Add lineage and quality tests**

Add tests proving Marquez connection validation/event sends and GX suite/check execution record spans, metrics, logs, and failure types.

- [ ] **Step 10: Implement lineage and quality instrumentation**

Instrument plugin-owned methods only. OpenLineage payload content remains lineage-owned; OTel records event send status and correlation context.

- [ ] **Step 11: Run focused package tests**

Run:

```bash
uv run pytest plugins/floe-dbt-core/tests/unit \
  plugins/floe-ingestion-dlt/tests/unit \
  packages/floe-iceberg/tests/unit \
  plugins/floe-catalog-polaris/tests/unit \
  plugins/floe-storage-minio/tests/unit \
  plugins/floe-lineage-marquez/tests/unit \
  plugins/floe-quality-gx/tests/unit -q
```

Expected: all pass.

- [ ] **Step 12: Commit**

```bash
git add plugins/floe-dbt-core plugins/floe-ingestion-dlt packages/floe-iceberg \
  plugins/floe-catalog-polaris plugins/floe-storage-minio \
  plugins/floe-lineage-marquez plugins/floe-quality-gx
git commit -m "Add runtime observability to alpha data plugins"
```

## Task 5: Security And Deployment Lifecycle Uplift

**Files:**
- Modify: `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py`
- Modify: `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py`
- Modify: `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py`
- Modify: `plugins/floe-rbac-k8s/src/floe_rbac_k8s/plugin.py`
- Modify: `plugins/floe-network-security-k8s/src/floe_network_security_k8s/plugin.py`
- Modify: `plugins/floe-alert-alertmanager/src/floe_alert_alertmanager/plugin.py`
- Modify: `plugins/floe-alert-email/src/floe_alert_email/plugin.py`
- Modify: `plugins/floe-alert-slack/src/floe_alert_slack/plugin.py`
- Modify: `plugins/floe-alert-webhook/src/floe_alert_webhook/plugin.py`
- Test: focused unit tests in each touched package.

- [ ] **Step 1: Add security-sensitive observability tests**

For each package, add or extend tests proving:

- success/failure lifecycle spans exist;
- token, password, secret value, private key, email, and credential-like fields are not emitted;
- access denied, not found, unavailable, and validation failures are classified by error type.

- [ ] **Step 2: Instrument secrets plugins**

Record secret backend operation type and outcome. Emit secret reference identity only when it is safe and already non-secret. Never emit secret values.

- [ ] **Step 3: Instrument identity plugin**

Record auth/token/user-info operation type and outcome. Never emit tokens, refresh tokens, claims containing PII, or raw user profile payloads.

- [ ] **Step 4: Instrument RBAC and network security generation**

Record generated resource kind, namespace, policy type, status, and duration. Do not record generated YAML bodies as telemetry attributes.

- [ ] **Step 5: Instrument alert channels**

Record destination type, delivery status, retry count, contract violation identifier, and error type. Do not record webhook URLs, email addresses, Slack tokens, or alert body payloads as attributes.

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest plugins/floe-secrets-k8s/tests/unit \
  plugins/floe-secrets-infisical/tests/unit \
  plugins/floe-identity-keycloak/tests/unit \
  plugins/floe-rbac-k8s/tests/unit \
  plugins/floe-network-security-k8s/tests/unit \
  plugins/floe-alert-alertmanager/tests/unit \
  plugins/floe-alert-email/tests/unit \
  plugins/floe-alert-slack/tests/unit \
  plugins/floe-alert-webhook/tests/unit -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add plugins/floe-secrets-k8s plugins/floe-secrets-infisical \
  plugins/floe-identity-keycloak plugins/floe-rbac-k8s \
  plugins/floe-network-security-k8s plugins/floe-alert-alertmanager \
  plugins/floe-alert-email plugins/floe-alert-slack plugins/floe-alert-webhook
git commit -m "Add security lifecycle observability"
```

## Task 6: Backend Profile For Queryable Logs And Metrics

**Files:**
- Modify: `charts/floe-platform/values.yaml`
- Modify: `charts/floe-platform/values-demo.yaml`
- Modify: `charts/floe-platform/templates/configmap-otel.yaml`
- Modify: `charts/floe-platform/templates/grafana-dashboards-configmap.yaml`
- Modify: `charts/floe-platform/templates/validate-otel-endpoints.yaml`
- Create: `charts/floe-platform/templates/configmap-loki.yaml`
- Create: `charts/floe-platform/templates/deployment-loki.yaml`
- Create: `charts/floe-platform/templates/service-loki.yaml`
- Modify: `tests/integration/helm/test_values_schema.py`
- Modify: `tests/e2e/test_demo_mode.py`

- [ ] **Step 1: Add Helm tests for log backend profile**

Extend Helm tests to assert the demo profile includes:

- OTel logs pipeline with a non-debug exporter;
- OTel metrics pipeline with a Prometheus-compatible path;
- Grafana datasource for logs;
- Grafana datasource for metrics;
- trace datasource remains available.

- [ ] **Step 2: Run Helm tests and verify failure**

Run:

```bash
uv run pytest tests/integration/helm/test_values_schema.py tests/e2e/test_demo_mode.py -q
```

Expected: fails until chart values and datasource wiring are added.

- [ ] **Step 3: Add Loki-compatible log backend profile**

Update chart values so alpha demo deployments include a queryable log backend. Prefer Loki because Grafana is already in the proof path. The OTel collector logs pipeline must export to that backend rather than `debug` only.

- [ ] **Step 4: Add metrics export and Grafana datasource wiring**

Ensure OTel metrics become queryable by Prometheus/Grafana. Existing dashboards must query metric names emitted by `MetricRecorder` and plugin instrumentation.

- [ ] **Step 5: Render and validate charts**

Run:

```bash
make helm-validate
uv run pytest tests/integration/helm/test_values_schema.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add charts/floe-platform tests/integration/helm/test_values_schema.py tests/e2e/test_demo_mode.py
git commit -m "Wire alpha observability backend profile"
```

## Task 7: Customer 360 Observability Proof Gate

**Files:**
- Create: `testing/ci/customer360_observability.py`
- Create: `tests/e2e/test_customer360_observability_gate.py`
- Modify: `testing/ci/validate_customer_360_demo.py`
- Modify: `Makefile`

- [ ] **Step 1: Add backend query helper tests**

Add unit tests for helper functions that classify:

- backend unreachable;
- backend reachable but no fresh evidence;
- backend returned stale evidence;
- backend returned wrong product/run/table evidence;
- product execution failure.

- [ ] **Step 2: Implement backend query helpers**

Create helpers for:

- trace backend query by service/product/run;
- Loki log query by product/run;
- Prometheus query by product/status/plugin;
- Marquez query by namespace/job/run.

- [ ] **Step 3: Add E2E proof test**

Create `tests/e2e/test_customer360_observability_gate.py` asserting a fresh Customer 360 run has:

- run root span;
- Dagster asset spans;
- dbt model spans;
- ingestion spans;
- catalog/storage/Iceberg spans where applicable;
- queryable structured logs;
- queryable metrics;
- Marquez lineage for the same run context.

- [ ] **Step 4: Update demo validator**

Modify `testing/ci/validate_customer_360_demo.py` so `make demo-customer-360-validate` fails when traces, logs, metrics, or lineage are missing or stale.

- [ ] **Step 5: Run local targeted tests**

Run:

```bash
uv run pytest tests/unit/test_observability_trigger_helper.py \
  tests/e2e/test_customer360_observability_gate.py -q
```

Expected: unit tests pass; E2E may require platform services and should fail clearly when services are not running.

- [ ] **Step 6: Run remote proof**

Run from DevPod+Hetzner validation infrastructure:

```bash
make demo
make demo-customer-360-run
make demo-customer-360-validate
```

Expected: validation output includes fresh run ID plus logs, metrics, traces, and lineage evidence. Failure output distinguishes product failures from infra/backend failures.

- [ ] **Step 7: Commit**

```bash
git add testing/ci/customer360_observability.py \
  testing/ci/validate_customer_360_demo.py \
  tests/e2e/test_customer360_observability_gate.py \
  Makefile
git commit -m "Validate Customer 360 observability proof"
```

## Task 8: Docs And Release Gate Updates

**Files:**
- Modify: `README.md`
- Modify: `docs/contracts/observability-attributes.md`
- Modify: `docs/releases/v0.1.0-alpha.1-checklist.md`
- Modify: `docs/releases/v0.1.0-alpha.1-release-notes.md`
- Modify: `docs/demo/index.md`
- Modify: `docs/demo/customer-360.md`
- Modify: `docs/demo/customer-360-validation.md`
- Modify: `docs/contributing/troubleshooting.md`

- [ ] **Step 1: Update observability contract docs**

Document:

- required trace attributes;
- required structured log fields;
- metric names and allowed labels;
- lineage correlation fields;
- plugin lifecycle fields;
- fields that must never be emitted.

- [ ] **Step 2: Update README alpha claims**

State that alpha observability includes queryable logs, traces, metrics, and lineage for supported alpha paths, with backend pluggability through the OTel collector and lineage backend plugin model.

- [ ] **Step 3: Update demo manual validation guide**

Add explicit user-facing checks:

- Grafana logs query by product and run ID;
- Grafana metrics query by product;
- trace query by run/model/table;
- Marquez lineage query by namespace/job/table;
- how to tell product failure from infra/backend failure.

- [ ] **Step 4: Update release checklist**

Make the release gate require the new Customer 360 observability proof before tagging or GitHub Release publication.

- [ ] **Step 5: Run docs validation**

Run:

```bash
make docs-validate
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add README.md docs
git commit -m "Document alpha observability proof"
```

## Final Verification

Run these after all PRs land on `main`:

```bash
make check
make demo
make demo-customer-360-run
make demo-customer-360-validate
```

The final validation evidence must include:

- fresh Customer 360 run ID;
- trace backend URL/query and required span inventory;
- Grafana log query and matching log count;
- Prometheus/Grafana metric query and fresh samples;
- Marquez namespace/job/dataset evidence;
- explicit product-vs-infra failure classification.

Do not tag a release until these gates pass on the intended `main` SHA.
