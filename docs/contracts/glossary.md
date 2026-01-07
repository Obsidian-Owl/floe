# Glossary

This glossary defines the core terminology used throughout floe documentation.

## Documentation Keywords (RFC 2119)

This documentation uses [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119.txt) keywords to indicate requirement levels in normative contexts (ADRs, requirements documents):

| Keyword | Meaning | When to Use |
|---------|---------|-------------|
| **MUST** | Absolute requirement | Non-negotiable platform enforcement, security requirements |
| **MUST NOT** | Absolute prohibition | Forbidden patterns, security violations |
| **SHOULD** | Strong recommendation | Best practice, deviation requires justification |
| **SHOULD NOT** | Discouraged | Allowed but not recommended |
| **MAY** | Optional | Truly optional features, implementer's choice |

**Examples:**
- "All plugins MUST implement PluginMetadata" (enforced at discovery)
- "Platform teams SHOULD use DuckDB for local development" (recommendation)
- "Plugins MAY include additional helper methods" (optional)

**Note:** Guides and non-normative documentation use lowercase "must/should/may" for readability.

## Configuration Types

### Manifest

A configuration file that defines platform-level settings. Manifests are versioned, immutable, and stored in an OCI registry.

```yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: "1.0.0"
  scope: enterprise    # or "domain"
```

**Scope:**
- `enterprise` - Root-level manifest with no parent (defines global policies)
- `domain` - Inherits from a parent manifest via `parent:` reference

### DataProduct

The unit of deployment in floe. A DataProduct defines transforms, schedules, and optionally input/output ports.

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-analytics
  version: "1.0"
```

DataProducts can reference a `platform:` or `domain:` manifest, or use system defaults.

### CompiledArtifacts

The output of `floe compile`. Contains resolved configuration after inheritance, validation, and compilation. This is what the runtime uses for execution.

## Deployment Modes

### Simple Mode

The minimal deployment mode. Uses only a `floe.yaml` file with system defaults (DuckDB, Dagster, Polaris, Cube, dlt).

### Centralized Mode

Platform Team defines a `Manifest` (scope: enterprise), Data Team references it in their `DataProduct`.

### Data Mesh Mode

Three-tier hierarchy:
1. Enterprise `Manifest` (global policies)
2. Domain `Manifest` (domain-specific settings, inherits from enterprise)
3. `DataProduct` (references domain)

## Architecture Layers

### Layer 1: Foundation

Framework code distributed via PyPI and Helm. Includes floe-core, floe-dbt, floe-iceberg, and plugins.

### Layer 2: Configuration

Immutable, versioned configuration stored in OCI registry. Defines plugins, governance, and data architecture.

### Layer 3: Services

Long-lived platform services deployed as Kubernetes Deployments/StatefulSets. Includes orchestrator, catalog, semantic layer, and observability stack.

### Layer 4: Data

Ephemeral pipeline jobs running as Kubernetes Jobs. Executes dbt transforms, ingestion, and quality checks.

## Plugin Types

### Compute Plugin

Where dbt transforms execute. Default: **DuckDB**. Alternatives: Spark, Snowflake, Databricks, BigQuery.

### Orchestrator Plugin

Pipeline scheduling and execution. Default: **Dagster**. Alternatives: Airflow, Prefect, Argo Workflows.

### Catalog Plugin

Iceberg catalog for table metadata. Default: **Polaris**. Alternatives: AWS Glue, Hive Metastore, Nessie.

### Semantic Layer Plugin

Analytics/BI consumption layer. Default: **Cube**. Alternatives: dbt Semantic Layer, None.

### Ingestion Plugin

Data loading (EL). Default: **dlt**. Alternatives: Airbyte (external).

## Enforced Standards

### Apache Iceberg

Open table format. All data in floe is stored as Iceberg tables. Non-negotiable.

### OpenTelemetry

Vendor-neutral observability standard. All traces and metrics use OTel. Non-negotiable.

### OpenLineage

Data lineage standard. All lineage events use OpenLineage format. Non-negotiable.

### dbt

Transformation layer. "dbt owns SQL" - all transforms are dbt models. Non-negotiable.

## Governance

### Data Classification

Metadata attached to columns via dbt `meta` tags. Levels: public, internal, confidential, pii, phi.

### Quality Gates

Compile-time checks that enforce test coverage, required tests, and naming conventions.

### Naming Conventions

Layer-based prefixes enforced at compile time. Medallion pattern uses `bronze_*`, `silver_*`, `gold_*`.

## Data Mesh Concepts

### Output Port

A published interface from a DataProduct. Defines the table, SLA, and access controls.

### Input Port

A dependency on another data source. Can reference ingestion sources or other DataProducts.

### Data Contract

Agreement between a provider DataProduct and consumer DataProduct. Auto-generated when an input port references another product's output port.

### Namespace

Hierarchical identifier for lineage and catalog organization. Format: `{project}` or `{domain}.{product}`.

## OCI Registry

### Platform Artifacts

Compiled manifests stored as OCI artifacts. Versioned, immutable, and optionally signed.

### Artifact Reference

OCI reference format: `oci://registry.example.com/artifact-name:version`

## CLI Commands

### floe compile

Validates DataProduct against inherited manifests and produces CompiledArtifacts.

### floe run

Executes the pipeline using CompiledArtifacts.

### floe platform compile

Validates a Manifest and prepares it for publishing.

### floe platform publish

Pushes compiled manifest to OCI registry.

### floe platform deploy

Deploys platform services (Layer 3) to Kubernetes.

## Core Concepts

### Plugin

An extensible component that implements a plugin interface (ABC) and registers via Python entry points. floe defines 11 plugin types. See [Plugin Architecture](../architecture/plugin-architecture.md).

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins.

### Entry Point

Python packaging mechanism for plugin discovery. Plugins register in `pyproject.toml` under `[project.entry-points."floe.<type>"]` groups.

### Contract

A versioned interface between packages. The primary contract is CompiledArtifacts (floe-core → floe-dagster). Uses semantic versioning (MAJOR.MINOR.PATCH).

### Interface

An Abstract Base Class (ABC) defining methods a plugin must implement. All plugins inherit from an interface (e.g., ComputePlugin, OrchestratorPlugin).

## Teams & Roles

### Platform Team

The team responsible for:
- Writing and versioning `platform-manifest.yaml`
- Selecting plugins (compute, orchestrator, catalog, etc.)
- Deploying platform services (Layer 3)
- Defining governance policies

### Data Team

The team responsible for:
- Writing `floe.yaml` (data product definitions)
- Implementing dbt models and transformations
- Scheduling pipelines
- Consuming platform services

## Deployment Concepts

### Service

A long-lived Kubernetes Deployment or StatefulSet (Layer 3). Examples: Dagster webserver, Polaris catalog, Cube API. Managed by Platform Team.

### Job

An ephemeral Kubernetes Job (Layer 4) that runs to completion. Examples: dbt run, data quality checks, dlt ingestion. Created by orchestrator.

## Governance Model

### Enforcement

**Compile-time** validation that blocks deployment of non-compliant configurations. Example: Missing required dbt tests → compilation fails.

### Validation

**Runtime** checks that may warn or fail execution. Example: Data contract schema mismatch → alert sent, execution continues (depending on config).

### Compliance

Adherence to governance policies defined in platform-manifest.yaml. Enforced at compile-time, monitored at runtime.

### Namespace Isolation

Security boundary separating data products within the platform. Each namespace has independent credentials, resource quotas, and access controls. Implemented via Kubernetes namespaces and Polaris catalog namespaces.

## Related Documents

- [CompiledArtifacts Contract](./compiled-artifacts.md) - Schema definition
- [Observability Attributes](./observability-attributes.md) - Telemetry conventions
- [Four-Layer Overview](../architecture/four-layer-overview.md) - Architecture
