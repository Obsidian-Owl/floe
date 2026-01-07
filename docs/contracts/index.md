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
│  COMPILED ARTIFACTS (Output of floe compile)                                 │
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
| [CompiledArtifacts](./compiled-artifacts.md) | Unified schema for all modes | Output of `floe compile` |
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
  compute: { type: duckdb }
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
  compute: { type: spark }  # Override parent

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
    path: models/

schedule:
  cron: "0 6 * * *"
  timezone: UTC
```

## Compilation Flow

```bash
# Platform Team: publish manifest
floe platform compile
floe platform publish v1.0.0

# Data Team: compile DataProduct
floe init --platform=v1.0.0
floe compile
```

The `floe compile` command:
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

### Schema Export

```bash
floe schema export --output compiled-artifacts.schema.json
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
