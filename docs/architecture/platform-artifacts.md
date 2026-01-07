# Platform Artifacts

This document describes how platform configuration is stored and distributed via OCI registries.

## Overview

Platform artifacts are immutable, versioned configuration bundles stored in OCI-compliant registries.

```
Platform Team                        OCI Registry                         Data Team
     │                                    │                                    │
     │  manifest.yaml            │                                    │
     │         │                          │                                    │
     │         ▼                          │                                    │
     │  [floe platform compile]           │                                    │
     │         │                          │                                    │
     │         ▼                          │                                    │
     │  [floe platform publish v1.2.3] ───┼───► oci://registry/platform:v1.2.3│
     │                                    │                                    │
     │                                    │         [floe init --platform=v1.2.3]
     │                                    │                ◄────────────────────│
     │                                    │                                    │
     │                                    │         Pull immutable artifacts   │
     │                                    │                ────────────────────►│
```

## Why OCI Registry?

| Requirement | OCI Registry | Alternative (S3) |
|-------------|--------------|------------------|
| K8s-native | ✅ ORAS, Helm 3.8+ standard | Requires custom tooling |
| Versioning | ✅ Built-in tags + digests | Manual version management |
| Immutability | ✅ Content-addressable | Requires object lock |
| Signing | ✅ cosign integration | Custom signing setup |
| Enterprise | ✅ ECR, ACR, GCR, Harbor | Additional infra needed |
| Caching | ✅ CDN-backed by registries | Custom CDN setup |

## Artifact Structure

```
oci://registry.example.com/floe-platform:v1.2.3
│
├── manifest.json                    # Platform metadata
│   {
│     "apiVersion": "floe.dev/v1",
│     "kind": "PlatformArtifact",
│     "metadata": {
│       "name": "acme-data-platform",
│       "version": "1.2.3",
│       "created": "2024-01-15T10:30:00Z",
│       "digest": "sha256:abc123..."
│     },
│     "plugins": {
│       "compute": "duckdb",
│       "orchestrator": "dagster",
│       "catalog": "polaris"
│     }
│   }
│
├── policies/                        # Governance policies
│   ├── classification.json          # Data classification rules
│   │   {
│   │     "levels": ["public", "internal", "confidential", "pii", "phi"],
│   │     "rules": {...}
│   │   }
│   │
│   ├── access-control.json          # RBAC definitions
│   │   {
│   │     "roles": ["data_engineer", "analyst", "admin"],
│   │     "permissions": {...}
│   │   }
│   │
│   └── quality-gates.json           # Quality requirements
│       {
│         "minimum_test_coverage": 80,
│         "required_tests": ["not_null", "unique", "freshness"],
│         "block_on_failure": true
│       }
│
├── catalog/                         # Catalog configuration
│   ├── namespaces.json              # Approved namespaces
│   │   {
│   │     "namespaces": ["bronze", "silver", "gold"],
│   │     "grants": {...}
│   │   }
│   │
│   └── schema-registry.json         # Schema constraints
│
└── architecture/                    # Data architecture rules
    ├── naming-rules.json            # Naming conventions
    │   {
    │     "pattern": "medallion",
    │     "enforcement": "strict",
    │     "prefixes": {
    │       "bronze": "bronze_",
    │       "silver": "silver_",
    │       "gold": "gold_"
    │     }
    │   }
    │
    └── layer-constraints.json       # Layer-specific rules
        {
          "bronze": {"required_tests": ["not_null_pk"]},
          "silver": {"required_tests": ["not_null_pk", "unique_pk", "freshness"]},
          "gold": {"required_tests": ["not_null_pk", "unique_pk", "freshness", "documentation"]}
        }
```

## Platform Team Workflow

### 1. Create Platform Configuration

```yaml
# manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-data-platform
  version: "1.2.3"
  scope: enterprise

plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
  catalog:
    type: polaris

data_architecture:
  pattern: medallion
  naming:
    enforcement: strict

governance:
  quality_gates:
    minimum_test_coverage: 80
    block_on_failure: true
```

### 2. Compile Artifacts

```bash
$ floe platform compile

[1/4] Validating manifest.yaml
      ✓ Schema validation passed
      ✓ Plugin references valid

[2/4] Resolving plugin charts
      ✓ floe-orchestrator-dagster@1.0.0
      ✓ floe-catalog-polaris@1.0.0
      ✓ floe-compute-duckdb@1.0.0

[3/4] Building governance policies
      ✓ classification.json
      ✓ access-control.json
      ✓ quality-gates.json

[4/4] Building architecture rules
      ✓ naming-rules.json
      ✓ layer-constraints.json

Artifacts built: .floe/artifacts/
```

### 3. Test Policies

```bash
$ floe platform test

Running policy tests...
  ✓ Naming convention enforcement
  ✓ Quality gate validation
  ✓ Classification propagation
  ✓ Access control rules

All 4 tests passed
```

### 4. Publish to Registry

```bash
$ floe platform publish v1.2.3

Publishing to oci://registry.example.com/floe-platform:v1.2.3
  ✓ Uploading manifest.json (2.1 KB)
  ✓ Uploading policies/ (4.5 KB)
  ✓ Uploading catalog/ (1.2 KB)
  ✓ Uploading architecture/ (0.8 KB)

Signing artifact with cosign...
  ✓ Signed: sha256:abc123def456...

Published: oci://registry.example.com/floe-platform:v1.2.3
Digest: sha256:abc123def456...
```

## Data Team Workflow

### 1. Initialize Project

```bash
$ floe init --platform=v1.2.3

Pulling platform artifacts from oci://registry.example.com/floe-platform:v1.2.3
  ✓ Verifying signature
  ✓ Downloading artifacts (8.6 KB)

Platform: acme-data-platform v1.2.3
  Compute: duckdb
  Orchestrator: dagster
  Catalog: polaris
  Pattern: medallion (strict enforcement)

Created:
  floe.yaml
  .floe/platform/v1.2.3/
```

### 2. Compile Pipeline

```bash
$ floe compile

[1/4] Loading platform artifacts
      ✓ Platform: acme-data-platform v1.2.3
      ✓ Cached at: .floe/platform/v1.2.3/

[2/4] Validating against platform
      ✓ Naming conventions
      ✓ Quality gates
      ✓ Classification compliance

[3/4] Generating dbt profile
      ✓ profiles.yml (target: duckdb)

[4/4] Compilation successful
```

## Artifact Caching

Platform artifacts are cached locally to avoid repeated downloads:

```
.floe/
├── platform/
│   ├── v1.2.3/                      # Cached artifacts
│   │   ├── manifest.json
│   │   ├── policies/
│   │   ├── catalog/
│   │   └── architecture/
│   └── v1.2.2/                      # Previous version
│       └── ...
└── cache/
    └── artifacts.lock               # Lock file with digests
```

### Cache Invalidation

```bash
# Force re-pull
floe platform pull --force

# Clear cache
floe platform cache clear
```

## Signing and Verification

### Sign with cosign

```bash
# Automatic during publish
floe platform publish v1.2.3

# Manual signing
cosign sign oci://registry.example.com/floe-platform:v1.2.3
```

### Verify Signature

```bash
# Automatic during init/pull
floe init --platform=v1.2.3

# Manual verification
cosign verify oci://registry.example.com/floe-platform:v1.2.3
```

### Require Signatures

```yaml
# manifest.yaml
security:
  require_signed_artifacts: true
  trusted_keys:
    - cosign.pub
```

## Registry Options

| Registry | Use Case | Notes |
|----------|----------|-------|
| GitHub Container Registry | Open source, public | Free for public repos |
| Amazon ECR | AWS deployments | Native IAM integration |
| Azure Container Registry | Azure deployments | Native AD integration |
| Google Artifact Registry | GCP deployments | Native IAM integration |
| Harbor | Self-hosted | Full control, air-gapped |

## Version Management

### Semantic Versioning

```
v1.2.3
│ │ │
│ │ └── Patch: Bug fixes, no breaking changes
│ └──── Minor: New features, backward compatible
└────── Major: Breaking changes
```

### Version Constraints

```yaml
# floe.yaml
platform:
  ref: oci://registry.example.com/floe-platform:v1.2.3    # Exact version
  # OR
  ref: oci://registry.example.com/floe-platform:v1.2.*    # Patch updates OK
  # OR
  ref: oci://registry.example.com/floe-platform:v1.*.*    # Minor updates OK
```

## Related Documents

- [ADR-0016: Platform Enforcement Architecture](adr/0016-platform-enforcement-architecture.md) - OCI storage decision
- [Four-Layer Overview](four-layer-overview.md) - Layer 2 configuration
- [Platform Enforcement](platform-enforcement.md) - Enforcement model
