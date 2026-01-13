# Quickstart: Compilation Pipeline

**Branch**: `2b-compilation-pipeline` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)

## Overview

The `floe compile` command transforms FloeSpec (`floe.yaml`) and PlatformManifest (`manifest.yaml`) into CompiledArtifacts - the sole contract between floe-core and downstream packages.

## Prerequisites

- Python 3.10+
- floe-core package installed
- Platform manifest (local file or OCI registry)

## Basic Usage

### Compile a Data Product

```bash
# Compile with default output (target/compiled_artifacts.json)
floe compile --spec floe.yaml --manifest manifest.yaml

# Compile with custom output path
floe compile --spec floe.yaml --manifest manifest.yaml --output build/artifacts.json

# Compile to YAML format
floe compile --spec floe.yaml --manifest manifest.yaml --output build/artifacts.yaml
```

### Validation Modes

```bash
# Dry-run: Validate without generating artifacts
floe compile --spec floe.yaml --manifest manifest.yaml --dry-run

# Validate-only: Check policies without full compilation
floe compile --spec floe.yaml --manifest manifest.yaml --validate-only
```

## FloeSpec Configuration

Create a `floe.yaml` in your data product directory:

```yaml
# floe.yaml - Data product configuration
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: customer-360
  version: 1.0.0
  description: Customer 360 data product
  owner: analytics-team@acme.com
  labels:
    domain: analytics
    tier: gold

# Reference platform manifest (optional - uses local if not specified)
platform:
  manifest: oci://registry.acme.com/floe/platform:v1

# Define transforms (dbt models)
transforms:
  - name: stg_customers
    tags: [staging]

  - name: int_customer_orders
    compute: spark  # Override compute for this model
    depends_on:
      - stg_customers
      - stg_orders

  - name: mart_customer_360
    tags: [marts]
    depends_on:
      - int_customer_orders

# Optional scheduling
schedule:
  cron: "0 6 * * *"
  timezone: America/New_York
```

## Platform Manifest

Platform team provides `manifest.yaml`:

```yaml
# manifest.yaml - Platform configuration
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: 2.0.0
  owner: platform-team@acme.com

plugins:
  compute:
    type: duckdb
    config:
      threads: 4
  orchestrator:
    type: dagster
  catalog:
    type: polaris
    config:
      uri: https://polaris.acme.com/api/catalog

governance:
  pii_encryption: required
  audit_logging: enabled
  policy_enforcement_level: strict
```

## Output: CompiledArtifacts

After compilation, `target/compiled_artifacts.json` contains:

```json
{
  "version": "0.2.0",
  "metadata": {
    "compiled_at": "2026-01-14T10:30:00Z",
    "floe_version": "0.1.0",
    "source_hash": "sha256:abc123...",
    "product_name": "customer-360",
    "product_version": "1.0.0"
  },
  "identity": {
    "product_id": "analytics.customer_360",
    "domain": "analytics",
    "repository": "github.com/acme/customer-360"
  },
  "plugins": {
    "compute": {"type": "duckdb", "version": "0.1.0"},
    "orchestrator": {"type": "dagster", "version": "0.1.0"}
  },
  "transforms": {
    "models": [
      {"name": "stg_customers", "compute": "duckdb"},
      {"name": "int_customer_orders", "compute": "spark"},
      {"name": "mart_customer_360", "compute": "duckdb"}
    ],
    "default_compute": "duckdb"
  },
  "dbt_profiles": {
    "customer_360": {
      "target": "{{ env_var('FLOE_ENV', 'dev') }}",
      "outputs": {
        "dev": {"type": "duckdb", "path": ":memory:"},
        "prod": {"type": "duckdb", "path": "{{ env_var('DUCKDB_PATH') }}"}
      }
    }
  }
}
```

## Environment-Agnostic Compilation

CompiledArtifacts are environment-agnostic (FR-014):

- **Same artifact, any environment**: Compile once, deploy to dev/staging/prod
- **Credential placeholders**: `{{ env_var('SECRET_NAME') }}` resolved at runtime
- **Runtime behavior**: Controlled by `FLOE_ENV` environment variable

```bash
# Deploy to dev
FLOE_ENV=dev dagster dev

# Deploy to production
FLOE_ENV=prod dagster deploy
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation error (invalid schema, missing fields) |
| 2 | Compilation error (plugin not found, policy violation) |

## CLI Reference

```
floe compile [OPTIONS]

Options:
  --spec PATH          Path to floe.yaml (required)
  --manifest PATH      Path to manifest.yaml or OCI URI (required)
  --output PATH        Output path (default: target/compiled_artifacts.json)
  --format FORMAT      Output format: json (default) or yaml
  --dry-run            Validate without generating artifacts
  --validate-only      Check policies without full compilation
  --verbose            Enable verbose logging
  --quiet              Suppress non-error output
  --help               Show this help message
```

## Troubleshooting

### Common Errors

**E001: Invalid FloeSpec**
```
Error: FloeSpec validation failed at metadata.name
  - Name must match pattern ^[a-z][a-z0-9-]*$
Suggestion: Use lowercase letters, numbers, and hyphens only. Start with a letter.
```

**E002: Plugin Not Found**
```
Error: Compute plugin 'spark' not found
  - Available plugins: duckdb, snowflake
Suggestion: Check manifest.yaml plugins section or install the plugin package.
```

**E003: Policy Violation**
```
Error: Policy violation in transforms
  - Model 'sensitive_data' requires pii_encryption=required
Suggestion: Enable PII encryption in governance config or remove sensitive fields.
```

### Debug Mode

```bash
# Enable debug logging
FLOE_LOG_LEVEL=DEBUG floe compile --spec floe.yaml --manifest manifest.yaml
```

## Next Steps

After compilation:

1. **Run dbt**: Use generated profiles.yml
   ```bash
   dbt run --profiles-dir target/
   ```

2. **Deploy with Dagster**: floe-dagster consumes CompiledArtifacts
   ```bash
   dagster dev
   ```

3. **Package for distribution**: Epic 8A adds OCI output format
