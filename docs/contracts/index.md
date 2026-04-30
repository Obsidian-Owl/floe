# floe Contracts

**Version:** 0.1.0

This directory contains the interface contracts that define floe's configuration schemas.

## Overview

floe uses a **unified two-type configuration model**:

| Kind | Purpose | Owner |
|------|---------|-------|
| **`Manifest`** | Configuration scope (enterprise or domain level) | Platform Team |
| **`DataProduct`** | Unit of deployment (transforms, schedule, ports) | Data Team |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MANIFEST (Optional - Platform Team)                                        │
│                                                                              │
│  kind: Manifest                                                              │
│  scope: enterprise | domain                                                  │
│  parent: (optional reference for inheritance)                               │
│                                                                              │
│  Defines: plugins, governance, data architecture                            │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ inherits
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATAPRODUCT (Required - Data Team)                                         │
│                                                                              │
│  kind: DataProduct                                                           │
│  platform: | domain: (reference to manifest)                                │
│                                                                              │
│  Defines: transforms, schedule, ports                                       │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  COMPILED ARTIFACTS (Output of the compilation pipeline)                     │
│                                                                              │
│  Resolved configuration for runtime execution                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Deployment Modes

| Mode | Files | Use Case |
|------|-------|----------|
| **Simple** | Just `floe.yaml` (DataProduct) | Getting started, prototyping |
| **Centralized** | `manifest.yaml` + `floe.yaml` | Platform Team defines guardrails |
| **Data Mesh** | Enterprise manifest + Domain manifest + `floe.yaml` | Federated domain ownership |

## Contract List

| Contract | Description | Purpose |
|----------|-------------|---------|
| [CompiledArtifacts](./compiled-artifacts.md) | Unified schema for all modes | Output of the compilation pipeline |
| [Observability Attributes](./observability-attributes.md) | OpenTelemetry/OpenLineage conventions | Consistent telemetry |
| [Glossary](./glossary.md) | Terminology definitions | Shared vocabulary |

## Configuration Types

### Manifest (scope: enterprise)

Root-level configuration with no parent. Defines global policies and approved plugins.

```yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: "1.0.0"
  scope: enterprise

plugins:
  compute:
    approved:
      - name: duckdb
      - name: spark
      - name: snowflake
    default: duckdb
  orchestrator: { type: dagster }
  catalog: { type: polaris }
  semantic_layer: { type: cube }
  ingestion: { type: dlt }

governance:
  classification:
    levels: [public, internal, confidential, pii]
  quality_gates:
    minimum_test_coverage: 80
    required_tests: [not_null, unique]
    block_on_failure: true

data_architecture:
  pattern: medallion
  layers:
    bronze: { prefix: "bronze_" }
    silver: { prefix: "silver_" }
    gold: { prefix: "gold_" }
  naming_enforcement: strict
```

### Manifest (scope: domain)

Domain-level configuration that inherits from a parent. Used in Data Mesh deployments.

```yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: sales-domain
  version: "2.0.0"
  scope: domain

parent:
  ref: oci://registry.acme.com/enterprise:v1.0.0

plugins:
  compute:
    approved: [duckdb, spark]  # Restrict to subset of enterprise
    default: duckdb

data_architecture:
  layers:
    bronze: { prefix: "sales_bronze_", namespace: sales.bronze }
    silver: { prefix: "sales_silver_", namespace: sales.silver }
    gold: { prefix: "sales_gold_", namespace: sales.gold }
```

### DataProduct

The unit of deployment. References a manifest (or uses system defaults).

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-analytics
  version: "1.0"

platform:
  ref: oci://registry.acme.com/platform:v1.0.0

transforms:
  - type: dbt
    path: models/staging/
    compute: spark      # Heavy processing

  - type: dbt
    path: models/marts/
    compute: duckdb     # Analytics (or uses default if omitted)

schedule:
  cron: "0 6 * * *"
  timezone: UTC
```

## Compilation Flow

```bash
# Current alpha: compile the Customer 360 demo artifacts
make compile-demo

# Current alpha: validate and compile a platform manifest
uv run floe platform compile --manifest manifest.yaml
```

The planned root data-team lifecycle commands are not the current alpha workflow:

```bash
# Planned target-state commands; not alpha-supported user commands today.
floe init --platform=v1.0.0  # planned target-state command
floe compile                 # planned target-state command
```

The compilation pipeline:
1. Loads manifest from OCI registry (if referenced)
2. Resolves inheritance chain
3. Validates DataProduct against constraints
4. Produces CompiledArtifacts

## Validation

### Python (floe-core)

```python
from floe_core.schemas import CompiledArtifacts

# Load and validate
with open(".floe/artifacts.json") as f:
    artifacts = CompiledArtifacts.model_validate_json(f.read())

# Access configuration
print(artifacts.mode)  # "simple" | "centralized" | "mesh"
print(artifacts.plugins.compute.type)  # "duckdb"
print(artifacts.plugins.orchestrator.type)  # "dagster"
```

### Schema Inspection

The public CLI does not currently expose a schema export command. During alpha, contributors can inspect the current Pydantic schema from the repository:

```python
import json

from floe_core.schemas import CompiledArtifacts

print(json.dumps(CompiledArtifacts.export_json_schema(), indent=2))
```

## Versioning

Contracts follow semantic versioning:

| Change Type | Version Impact |
|-------------|----------------|
| Add optional field | Minor (0.x.0) |
| Add required field | Major (x.0.0) |
| Remove field | Major (x.0.0) |
| Change field type | Major (x.0.0) |

## Related Documents

- [Four-Layer Overview](../architecture/four-layer-overview.md) - Architecture context
- [Platform Artifacts](../architecture/platform-artifacts.md) - OCI storage
- [Plugin Architecture](../architecture/plugin-system/index.md) - Plugin system
- [Opinionation Boundaries](../architecture/opinionation-boundaries.md) - Defaults
