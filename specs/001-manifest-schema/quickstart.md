# Quickstart: Manifest Schema

**Feature**: 001-manifest-schema
**Date**: 2026-01-09

## Overview

This guide shows how to create and validate platform manifests using the unified schema that supports both 2-tier (single platform) and 3-tier (Data Mesh) configurations.

## Prerequisites

- Python 3.10+
- floe-core package installed

## 2-Tier Mode (Simple Platform)

For single-team or startup deployments without hierarchical governance:

```yaml
# manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: "1.0.0"
  owner: platform-team@acme.com
  description: ACME data platform configuration

# scope: omitted (defaults to null = 2-tier mode)
# parent_manifest: omitted (not used in 2-tier)

plugins:
  compute:
    type: duckdb
    config:
      threads: 4

  orchestrator:
    type: dagster

  catalog:
    type: polaris
    connection_secret_ref: polaris-credentials

  storage:
    type: s3
    config:
      bucket: acme-data-lake
      region: us-east-1

  secrets:
    type: kubernetes

governance:
  pii_encryption: required
  audit_logging: enabled
  policy_enforcement_level: warn
  data_retention_days: 90
```

## 3-Tier Mode (Data Mesh)

For enterprise deployments with hierarchical governance:

### Enterprise Manifest (Parent)

```yaml
# enterprise-manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-enterprise
  version: "1.0.0"
  owner: enterprise-arch@acme.com
  description: Enterprise-wide data platform standards

scope: enterprise
# parent_manifest: null (enterprise has no parent)

# Enterprise defines approved plugins for all domains
approved_plugins:
  compute: [duckdb, snowflake]
  orchestrator: [dagster]
  catalog: [polaris, glue]
  storage: [s3, gcs]
  secrets: [kubernetes, external-secrets]

governance:
  pii_encryption: required
  audit_logging: enabled
  policy_enforcement_level: strict
  data_retention_days: 365

plugins:
  # Enterprise sets defaults; domains can override within approved list
  orchestrator:
    type: dagster
  secrets:
    type: kubernetes
```

### Domain Manifest (Child of Enterprise)

```yaml
# domain-sales-manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-sales-domain
  version: "1.0.0"
  owner: sales-data@acme.com
  description: Sales domain data platform

scope: domain
parent_manifest: oci://registry.acme.com/floe-enterprise:v1.0.0

# Domain approves specific products
approved_products:
  - customer-360
  - sales-analytics

plugins:
  # Must be in enterprise approved_plugins list
  compute:
    type: snowflake
    connection_secret_ref: snowflake-credentials

  catalog:
    type: glue
    config:
      database: sales_catalog

  storage:
    type: s3
    config:
      bucket: acme-sales-data
      prefix: sales/

governance:
  # Can match or strengthen, but NOT weaken enterprise policies
  # pii_encryption: required (inherited, cannot change to optional)
  # audit_logging: enabled (inherited, cannot disable)
  data_retention_days: 730  # Stronger than enterprise's 365
```

## Loading and Validating Manifests

### Python API

```python
from floe_core.schemas import PlatformManifest
from pathlib import Path
import yaml

# Load and validate a manifest
def load_manifest(path: Path) -> PlatformManifest:
    """Load and validate a manifest file."""
    content = yaml.safe_load(path.read_text())
    return PlatformManifest.model_validate(content)

# Example usage
manifest = load_manifest(Path("manifest.yaml"))
print(f"Loaded: {manifest.metadata.name} v{manifest.metadata.version}")
print(f"Scope: {manifest.scope or '2-tier'}")
print(f"Compute: {manifest.plugins.compute.type if manifest.plugins.compute else 'not set'}")
```

### CLI (future)

```bash
# Validate a manifest
floe manifest validate manifest.yaml

# Show resolved configuration (with inheritance)
floe manifest resolve manifest.yaml --show-sources
```

## JSON Schema for IDE Autocomplete

The manifest schema is available as JSON Schema for IDE autocomplete and validation.

### VS Code / YAML Language Server

Add this line at the top of your manifest.yaml:

```yaml
# yaml-language-server: $schema=https://floe.dev/schemas/manifest.schema.json
apiVersion: floe.dev/v1
kind: Manifest
# ... IDE will now provide autocomplete and validation
```

Or use a local schema path:

```yaml
# yaml-language-server: $schema=./contracts/manifest.schema.json
apiVersion: floe.dev/v1
kind: Manifest
# ...
```

### Regenerating the Schema

The JSON Schema is generated from the Pydantic models. To regenerate:

```bash
# From the repo root
python packages/floe-core/scripts/export_schema.py

# Or specify a custom output path
python packages/floe-core/scripts/export_schema.py /path/to/schema.json
```

### Programmatic Schema Export

```python
from floe_core.schemas import export_json_schema, export_json_schema_to_file

# Get schema as dict
schema = export_json_schema()

# Export to file
export_json_schema_to_file("manifest.schema.json")
```

## Common Validation Errors

### Missing Required Field

```
ValidationError: metadata.name - Field required
  Location: manifest.yaml line 3
  Fix: Add 'name' field under 'metadata'
```

### Invalid Plugin

```
ValidationError: plugins.compute.type - Plugin 'invalid' not found
  Available plugins: duckdb, snowflake, spark, bigquery, databricks
  Location: manifest.yaml line 12
```

### Security Policy Violation

```
SecurityPolicyViolationError: Cannot weaken security policy
  Field: governance.pii_encryption
  Parent value: required
  Child value: optional
  Fix: Child manifests can only match or strengthen parent policies
```

### Circular Inheritance

```
InheritanceError: Circular reference detected
  Chain: domain-a → enterprise-b → domain-a
  Fix: Ensure inheritance chain has no cycles
```

## Environment Variables

Manifests are environment-agnostic. Environment context is determined at runtime:

```bash
# Development
export FLOE_ENV=dev
floe run my-pipeline

# Production (same manifest, different credentials)
export FLOE_ENV=production
floe run my-pipeline
```

## Next Steps

1. **Create your manifest**: Start with 2-tier, migrate to 3-tier when needed
2. **Configure plugins**: Select compute, orchestrator, catalog for your stack
3. **Set governance**: Define security policies appropriate for your org
4. **Publish to OCI**: Push enterprise/domain manifests to registry for sharing
5. **Create data products**: Reference manifest via `platform.ref` in floe.yaml
