# Contract Monitoring Guide

This guide explains how to set up and use contract monitoring in floe.

## Overview

Contract monitoring validates that data products meet their declared SLAs and schema agreements. The `ContractMonitor` service runs continuously, checking contracts at configurable intervals and emitting violations as OpenLineage events.

## Prerequisites

- floe with data contracts enabled
- OpenLineage-compatible backend (Marquez, Atlan, etc.)
- Optional: Prometheus for metrics

## Quick Start

### 1. Define a Contract

Create `datacontract.yaml` alongside your data product:

```yaml
apiVersion: v3.0.2
kind: DataContract
name: my-customers
version: 1.0.0

owner: data-team@example.com

models:
  customers:
    elements:
      customer_id:
        type: string
        primaryKey: true
      email:
        type: string
        format: email

slaProperties:
  freshness:
    value: "PT6H"
    element: updated_at
  availability:
    value: "99.9%"
```

### 2. Enable Monitoring in Platform Manifest

```yaml
# platform-manifest.yaml
data_contracts:
  enforcement: alert_only
  monitoring:
    enabled: true
    mode: scheduled
    freshness:
      check_interval: 15m
    schema_drift:
      check_interval: 1h
```

### 3. Compile and Run

```bash
floe compile
floe run
```

The ContractMonitor will automatically start and begin checking contracts.

## Configuration

### Monitoring Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `scheduled` | Fixed intervals | Production (default) |
| `continuous` | Event-driven | Real-time requirements |
| `on_demand` | Manual trigger only | Development/testing |

### Check Intervals

```yaml
monitoring:
  freshness:
    check_interval: 15m    # Check freshness every 15 minutes
  schema_drift:
    check_interval: 1h     # Check schema every hour
  quality:
    check_interval: 6h     # Run quality checks every 6 hours
  availability:
    check_interval: 5m     # Check availability every 5 minutes
```

### Enforcement Levels

| Level | Behavior |
|-------|----------|
| `off` | No monitoring |
| `warn` | Log warnings only |
| `alert_only` | Emit OpenLineage FAIL events (default) |
| `block` | Block processing on violation |

## Monitoring Checks

### Freshness Check

Verifies data is updated within the SLA window.

```yaml
slaProperties:
  freshness:
    value: "PT6H"        # Max 6 hours since last update
    element: updated_at   # Column to check
```

**How it works:**
1. Query `MAX(updated_at)` from the data source
2. Calculate time since last update
3. Compare against SLA threshold
4. Emit violation if exceeded

### Schema Drift Check

Detects when actual schema differs from contract.

**Detected changes:**
- Removed columns (breaking)
- Type changes (breaking)
- New required columns (breaking)
- New optional columns (info)
- Nullability changes

**Example violation:**

```json
{
  "violationType": "schema_drift",
  "message": "Breaking changes: [Removed column: email, Type change: id (int → string)]"
}
```

### Availability Check

Verifies data source is accessible.

```yaml
slaProperties:
  availability:
    value: "99.9%"
```

### Quality Check

Runs quality rules defined in the contract.

```yaml
slaProperties:
  quality:
    completeness: "99%"    # Non-null required fields
    uniqueness: "100%"     # Primary key uniqueness
```

## Viewing Violations

### OpenLineage Events

Violations are emitted as OpenLineage FAIL events:

```json
{
  "eventType": "FAIL",
  "job": {
    "namespace": "floe",
    "name": "contract_check.my-customers"
  },
  "run": {
    "facets": {
      "contractViolation": {
        "contractName": "my-customers",
        "contractVersion": "1.0.0",
        "violationType": "freshness_violation",
        "severity": "warning",
        "message": "Data is 8 hours old, SLA is 6 hours"
      }
    }
  }
}
```

### Prometheus Metrics

```promql
# Total violations by type
sum(floe_contract_violations_total) by (contract, type)

# Current freshness in hours
floe_contract_freshness_hours{contract="my-customers"}

# Availability status
floe_contract_availability_up{contract="my-customers"}

# Schema drift detection
floe_contract_schema_drift_detected{contract="my-customers"}
```

### Sample Grafana Dashboard

```yaml
# panels:
- title: Contract Violations
  type: stat
  targets:
    - expr: sum(increase(floe_contract_violations_total[24h]))

- title: Freshness by Contract
  type: gauge
  targets:
    - expr: floe_contract_freshness_hours
  thresholds:
    - value: 6
      color: green
    - value: 12
      color: yellow
    - value: 24
      color: red

- title: Availability Status
  type: stat
  targets:
    - expr: floe_contract_availability_up
```

## Post-Run Validation

The orchestrator automatically runs contract checks after each pipeline run:

```python
# In DagsterOrchestratorPlugin
@asset(post_hooks=[contract_check_hook])
def my_asset(context):
    # ... dbt run ...
    pass

def contract_check_hook(context):
    violations = await contract_monitor.check_contract_post_run("my-customers")
    if violations:
        context.log.warning(f"{len(violations)} contract violations detected")
```

## Manual Checks

### CLI

```bash
# Check a specific contract
floe contract check my-customers

# Check all contracts
floe contract check --all

# Validate contract file
floe contract validate datacontract.yaml
```

### Python API

```python
from floe_runtime.monitoring import ContractMonitor

monitor = ContractMonitor(config, plugin, emitter)

# Check single contract
violations = await monitor.check_contract_post_run("my-customers")

# Check all contracts
all_violations = await monitor.check_all_contracts()
```

## Alerting

### Configure Alerting

```yaml
# platform-manifest.yaml
data_contracts:
  alerting:
    openlineage_events: true
    prometheus_metrics: true
    slack:
      webhook_url: ${SLACK_WEBHOOK_URL}
      channel: "#data-alerts"
    pagerduty:
      service_key: ${PAGERDUTY_KEY}
      severity_threshold: error  # Only page on error/critical
```

### Alert Rules (Prometheus Alertmanager)

```yaml
groups:
  - name: contract-violations
    rules:
      - alert: ContractFreshnessViolation
        expr: floe_contract_freshness_hours > 12
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Contract {{ $labels.contract }} freshness SLA violated"

      - alert: ContractUnavailable
        expr: floe_contract_availability_up == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Contract {{ $labels.contract }} data source unavailable"

      - alert: ContractSchemaDrift
        expr: floe_contract_schema_drift_detected == 1
        for: 1m
        labels:
          severity: error
        annotations:
          summary: "Schema drift detected for {{ $labels.contract }}"
```

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| No violations emitted | Monitoring disabled | Check `monitoring.enabled: true` |
| Missing metrics | Prometheus not configured | Enable `prometheus_metrics: true` |
| False positives | Too strict SLA | Adjust SLA thresholds |
| Schema drift false positive | Dynamic columns | Exclude in contract config |

### Debug Mode

```bash
# Run with verbose logging
FLOE_LOG_LEVEL=debug floe run

# Check contract directly
floe contract test datacontract.yaml --connection prod --verbose
```

### Viewing Logs

```bash
# Kubernetes
kubectl logs -l app=floe -c contract-monitor

# Docker
docker logs floe 2>&1 | grep "contract"
```

## Best Practices

1. **Start with `alert_only`**: Don't block processing until SLAs are tuned
2. **Tune thresholds gradually**: Start lenient, tighten over time
3. **Use appropriate intervals**: Frequent checks for critical data, infrequent for batch
4. **Document SLA rationale**: Explain why thresholds are set
5. **Set up dashboards early**: Visibility helps catch issues

## Related Documents

- [Data Contracts Architecture](../architecture/data-contracts.md)
- [ADR-0028: Runtime Contract Monitoring](../architecture/adr/0028-runtime-contract-monitoring.md)
- [datacontract.yaml Reference](../contracts/datacontract-yaml-reference.md)
- [Observability Attributes](../contracts/observability-attributes.md)
- [Contract Versioning Guide](./contract-versioning.md)
