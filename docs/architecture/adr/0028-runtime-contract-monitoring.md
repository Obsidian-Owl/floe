# ADR-0028: Runtime Contract Monitoring

## Status

Accepted

## Context

ADR-0026 establishes the data contract architecture with the `DataContractPlugin` interface. However, contract validation must occur not only at compile-time but also during runtime to detect:

1. **Schema drift**: Actual data diverging from contract schema
2. **Freshness violations**: Data not updated within SLA window
3. **Availability issues**: Data sources becoming unavailable
4. **Quality degradation**: Data quality falling below thresholds

The existing `PolicyEnforcer` operates at compile-time only and cannot detect runtime violations.

### Current Gap

```
                   COMPILE TIME                    RUNTIME
                   ─────────────                   ───────
                        │                             │
    PolicyEnforcer ─────┤                             │
    (validates contracts)                             │
                        │                             │
    CompiledArtifacts ──┼─────────────────────────────►  No monitoring
                        │                                No alerts
                                                         No OpenLineage
```

### Requirements

1. Continuous or scheduled monitoring of contract SLAs
2. Post-run validation after data pipeline execution
3. Alert emission via OpenLineage FAIL events
4. Prometheus metrics for observability
5. Non-blocking enforcement (alert-only, don't stop processing)

## Decision

Introduce a **ContractMonitor** runtime component that performs continuous contract monitoring and emits violations via OpenLineage.

### Architecture

```
                        RUNTIME
                        ───────
                           │
   CompiledArtifacts ──────┼──────► ContractMonitor
   (with contracts)        │              │
                           │              ├──► Freshness Loop (15min)
                           │              ├──► Schema Drift Loop (1h)
                           │              └──► Quality Loop (6h)
                           │
   OrchestratorPlugin ─────┼──────► Post-Run Hook
   (Dagster/Airflow)       │              │
                           │              └──► ContractMonitor.check_contract_post_run()
                           │
                           │
                   OpenLineage ◄────────── Violations emitted as FAIL events
```

### ContractMonitor Component

```python
# floe_runtime/monitoring/contract_monitor.py

class ContractMonitor:
    """Runtime service for contract monitoring.

    Runs continuously or on-demand, checking contracts against
    live data sources and emitting violations as OpenLineage events.
    """

    def __init__(
        self,
        config: MonitoringConfig,
        contract_plugin: DataContractPlugin,
        lineage_emitter: Callable,
        metrics_registry: prometheus_client.Registry | None = None,
    ):
        self._config = config
        self._plugin = contract_plugin
        self._emit_lineage = lineage_emitter
        self._contracts: dict[str, RegisteredContract] = {}
        self._metrics = self._init_metrics(metrics_registry)

    # ─────────────────────────────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────────────────────────────

    def register_contract(
        self,
        contract: DataContract,
        connection: dict,
    ) -> None:
        """Register a contract for monitoring."""
        pass

    def unregister_contract(self, contract_name: str) -> None:
        """Unregister a contract from monitoring."""
        pass

    # ─────────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start background monitoring loops."""
        pass

    async def stop(self) -> None:
        """Stop monitoring."""
        pass

    # ─────────────────────────────────────────────────────────────────
    # On-Demand Checks
    # ─────────────────────────────────────────────────────────────────

    async def check_contract_post_run(
        self,
        contract_name: str,
    ) -> list[ContractViolation]:
        """Run all checks after pipeline execution.

        Called by OrchestratorPlugin post-materialize hook.
        """
        pass

    async def check_all_contracts(self) -> dict[str, list[ContractViolation]]:
        """Run checks on all registered contracts."""
        pass
```

### Monitoring Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `scheduled` | Fixed intervals per check type | Production default |
| `continuous` | Event-driven, real-time | High-frequency data |
| `on_demand` | Manual trigger only | Development/testing |

### Check Intervals (Default)

| Check Type | Interval | Rationale |
|------------|----------|-----------|
| Freshness | 15 minutes | Catch SLA breaches quickly |
| Schema Drift | 1 hour | Schema changes are infrequent |
| Quality | 6 hours | Quality checks are expensive |
| Availability | 5 minutes | Quick health checks |

These defaults can be overridden in `manifest.yaml`:

```yaml
data_contracts:
  monitoring:
    enabled: true
    mode: scheduled
    freshness:
      check_interval: 15m
    schema_drift:
      check_interval: 1h
    quality:
      check_interval: 6h
    availability:
      check_interval: 5m
```

### Alert-Only Enforcement

Violations are emitted as alerts but do not block processing:

```python
async def _emit_violation(self, violation: ContractViolation) -> None:
    """Emit violation as OpenLineage FAIL event + Prometheus metric."""

    # 1. OpenLineage FAIL event
    self._emit_lineage(
        event_type="FAIL",
        job=f"contract_check.{violation.contract_name}",
        facets={
            "contractViolation": {
                "_producer": "floe",
                "_schemaURL": "https://floe.dev/schemas/contract-violation-facet.json",
                "contractName": violation.contract_name,
                "contractVersion": violation.contract_version,
                "violationType": violation.violation_type.value,
                "severity": violation.severity.value,
                "message": violation.message,
                "element": violation.element,
                "expectedValue": str(violation.expected_value),
                "actualValue": str(violation.actual_value),
                "timestamp": violation.timestamp.isoformat(),
            }
        }
    )

    # 2. Prometheus metrics
    self._metrics["violations_total"].labels(
        contract=violation.contract_name,
        type=violation.violation_type.value,
        severity=violation.severity.value,
    ).inc()

    # 3. Log for debugging
    logger.warning(
        "Contract violation",
        contract=violation.contract_name,
        type=violation.violation_type.value,
        message=violation.message,
    )

    # NOTE: No exception raised - processing continues
```

### Prometheus Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `floe_contract_violations_total` | Counter | contract, type, severity | Total violations |
| `floe_contract_check_duration_seconds` | Histogram | contract, check_type | Check latency |
| `floe_contract_freshness_hours` | Gauge | contract | Hours since last update |
| `floe_contract_availability_up` | Gauge | contract | 1 if available, 0 if not |
| `floe_contract_quality_score` | Gauge | contract | Quality score 0-100 |

### OpenLineage Integration

Violations are emitted as OpenLineage FAIL events with a custom `contractViolation` facet:

```json
{
  "eventType": "FAIL",
  "eventTime": "2026-01-03T10:15:00Z",
  "job": {
    "namespace": "floe",
    "name": "contract_check.sales-customers"
  },
  "run": {
    "runId": "uuid-here",
    "facets": {
      "contractViolation": {
        "_producer": "floe",
        "_schemaURL": "https://floe.dev/schemas/contract-violation-facet.json",
        "contractName": "sales-customers",
        "contractVersion": "2.1.0",
        "violationType": "freshness_violation",
        "severity": "warning",
        "message": "Data is 8 hours old, SLA is 6 hours",
        "element": "updated_at",
        "expectedValue": "PT6H",
        "actualValue": "PT8H",
        "timestamp": "2026-01-03T10:15:00Z"
      }
    }
  }
}
```

### Post-Run Integration

The `OrchestratorPlugin` calls `ContractMonitor.check_contract_post_run()` after each data pipeline run:

```python
# In DagsterOrchestratorPlugin

@asset(post_hooks=[contract_check_hook])
def customers(context: AssetExecutionContext):
    # ... dbt run ...
    pass

def contract_check_hook(context: HookContext):
    """Post-materialize hook that validates contracts."""
    asset_key = context.op.name
    contract_name = f"{context.job_name}.{asset_key}"

    violations = await contract_monitor.check_contract_post_run(contract_name)

    if violations:
        context.log.warning(
            f"Contract {contract_name} has {len(violations)} violations"
        )
        # Violations already emitted via OpenLineage
```

### Sequence Diagram: Post-Run Check

```
┌─────────┐  ┌─────────────┐  ┌───────────────┐  ┌─────────────────┐  ┌───────────┐
│ Dagster │  │Orchestrator │  │ContractMonitor│  │DataContractPlugin│  │OpenLineage│
└────┬────┘  └──────┬──────┘  └───────┬───────┘  └────────┬────────┘  └─────┬─────┘
     │              │                 │                   │                 │
     │ asset run    │                 │                   │                 │
     │ complete     │                 │                   │                 │
     │──────────────►                 │                   │                 │
     │              │                 │                   │                 │
     │              │ post_materialize│                   │                 │
     │              │─────────────────►                   │                 │
     │              │                 │                   │                 │
     │              │                 │ check_freshness() │                 │
     │              │                 │──────────────────►│                 │
     │              │                 │                   │                 │
     │              │                 │ SLACheckResult    │                 │
     │              │                 │◄──────────────────│                 │
     │              │                 │                   │                 │
     │              │                 │ detect_schema_drift()               │
     │              │                 │──────────────────►│                 │
     │              │                 │                   │                 │
     │              │                 │ SchemaComparisonResult              │
     │              │                 │◄──────────────────│                 │
     │              │                 │                   │                 │
     │              │                 │ (if violations)   │                 │
     │              │                 │────────────────────────────────────►│
     │              │                 │                   │   FAIL event    │
     │              │                 │                   │                 │
     │              │ violations[]    │                   │                 │
     │              │◄────────────────│                   │                 │
     │              │                 │                   │                 │
     │ log warnings │                 │                   │                 │
     │◄─────────────│                 │                   │                 │
```

### Why Alert-Only (Not Blocking)?

| Approach | Pros | Cons |
|----------|------|------|
| **Alert-only** | Processing continues, no downtime | Violations may go unnoticed |
| **Blocking** | Guarantees compliance | Pipeline failures, cascading issues |

**Decision**: Alert-only for initial implementation. Reasons:
1. Data pipelines should be resilient to monitoring failures
2. Blocking on contract violations can cause cascading outages
3. Alert fatigue is better managed with good observability
4. Future: Add opt-in blocking for critical contracts via `enforcement: block`

## Consequences

### Positive

1. **Runtime visibility**: Violations are detectable after compile-time
2. **Non-blocking**: Processing continues, alerts flow to observability
3. **Integrated**: Works with existing OrchestratorPlugin and OpenLineage
4. **Configurable**: Intervals and modes adjustable per deployment
5. **Observable**: Prometheus metrics enable dashboards and alerting

### Negative

1. **Operational complexity**: New runtime service to operate
2. **Resource usage**: Continuous checks consume CPU/memory
3. **False positives**: Schema drift detection may flag benign changes
4. **Alert fatigue**: Without tuning, teams may ignore violations

### Neutral

1. **Alert-only default**: Violations don't block (by design)
2. **Separate from PolicyEnforcer**: Compile-time and runtime are distinct

## References

- [ADR-0026: Data Contract Architecture](./0026-data-contract-architecture.md)
- [ADR-0027: ODCS Standard Adoption](./0027-odcs-standard-adoption.md)
- [ADR-0007: OpenLineage from Start](./0007-openlineage-from-start.md)
- [OpenLineage Facets](https://openlineage.io/docs/spec/facets)
- [Prometheus Metrics Best Practices](https://prometheus.io/docs/practices/naming/)
