# 10. Glossary

This document defines implementation-specific terms used in floe guides.

> **Shared Terminology:** For core configuration types (Manifest, DataProduct, CompiledArtifacts), architecture layers (Layer 1-4), plugin types, enforced standards, and Data Mesh concepts, see the **[Shared Glossary](../contracts/glossary.md)**.

---

## A

### Asset (Dagster)
A Software-Defined Asset (SDA) in Dagster—a declarative representation of a data artifact. In floe, each dbt model becomes an asset.

### Artifacts
See [CompiledArtifacts](#compiledartifacts).

---

## C

### Catalog
A metadata service that tracks Iceberg table locations and schemas. floe uses Apache Polaris as the default catalog.

### Classification
Metadata identifying the sensitivity of data columns. Types include `pii`, `financial`, `identifier`, and `public`. Defined in dbt meta tags using the `floe:` namespace. See [ADR-0012](../architecture/adr/0012-data-classification-governance.md).

### CLI
Command-Line Interface. The `floe` command provides user interaction with floe.

### CompiledArtifacts
See [Shared Glossary](../contracts/glossary.md#compiledartifacts).

### Contract
A formal interface specification defining schemas and APIs. Contracts ensure compatibility. See [contracts documentation](../contracts/index.md).

### ContractMonitor
Runtime service that continuously validates data contracts. Checks freshness, schema drift, and quality at configurable intervals. Emits violations as OpenLineage FAIL events. See [ADR-0028](../architecture/adr/0028-runtime-contract-monitoring.md).

### Compute Target
See [Shared Glossary](../contracts/glossary.md#compute-plugin). Also called "Compute Plugin".

### Cube
Open-source semantic layer for data analytics. floe uses Cube to expose transformed data via REST, GraphQL, and SQL APIs. See [floe-semantic-cube](#floe-semantic-cube).

### Cube Store
Cube's built-in caching engine. Stores pre-aggregated data for sub-second query response.

### cube_dbt
Python package that integrates Cube with dbt. Loads dbt manifest and generates Cube data model definitions.

---

## D

### Dagster
Open-source data orchestrator used by floe. Treats data as first-class assets rather than tasks.

### Data Contract
Formal agreement between data producer and consumer specifying schema, SLAs, ownership, and governance terms. Defined in `datacontract.yaml` using ODCS v3 format. See [Data Contracts Architecture](../architecture/data-contracts.md).

### DataContract (Core Module)
Data contract functionality is now a **core module** in floe-core, not a plugin. Data contracts use ODCS v3 as an enforced standard, with validation and monitoring handled by built-in functionality wrapping `datacontract-cli`. See [ADR-0026](../architecture/adr/0026-data-contract-architecture.md).

### Data Plane (Deprecated)
Deprecated term for floe. Please use "floe" instead. See [floe](#floe).

### dbt
See [Shared Glossary](../contracts/glossary.md#dbt). Data Build Tool—SQL transformation framework.

### dbt Adapter
A plugin that allows dbt to connect to a specific database. Examples: dbt-duckdb, dbt-snowflake.

---

## E

### Entry Point
Python packaging mechanism for plugin discovery. floe uses entry points for 11 plugin types: `floe.orchestrators`, `floe.computes`, `floe.catalogs`, `floe.storage`, `floe.telemetry_backends`, `floe.lineage_backends`, `floe.dbt`, `floe.semantic_layers`, `floe.ingestion`, `floe.secrets`, `floe.identity`.

### Environment
A deployment context (dev, preview, staging, production). Each environment can have different compute targets and data.

---

## F

### floe.yaml
The declarative configuration file that defines a data pipeline (Data Team). Specifies transforms and schedules. Inherits platform configuration from `manifest.yaml`.

### DataProduct
See [Shared Glossary](../contracts/glossary.md#dataproduct).

---

## G

### Governance
The framework for managing data classification, access control, and policy enforcement in floe. See [ADR-0012](../architecture/adr/0012-data-classification-governance.md).

### Governance Policy
A rule in `floe.yaml` defining how classified data should be handled. Actions include `restrict`, `synthesize`, `mask`, `redact`, and `hash`.

---

## H

### Helm
Kubernetes package manager. floe provides Helm charts for production deployment.

### Hybrid Distribution
floe's distribution strategy: PyPI packages as source of truth, container images for convenience, Helm charts for Kubernetes.

---

## I

### Iceberg
See [Shared Glossary](../contracts/glossary.md#apache-iceberg).

### Identity (Product)
The unique identifier for a data product, composed of domain and product name: `{domain}.{product}`. Example: `sales.customer_360`. Identity is enforced at compile-time via catalog namespace registration. See [ADR-0030](../architecture/adr/0030-namespace-identity.md).

### Identity Conflict
An error that occurs when a data product attempts to register a namespace already owned by a different repository. The first-to-register repository owns the namespace.

---

## J

### JSON Schema
Schema format generated from Pydantic models. Used for validation and IDE support.

---

## L

### Lineage
The tracking of data flow—which datasets are inputs to a transformation and which are outputs. floe uses OpenLineage.

---

## N

### Namespace (Product)
The Iceberg catalog namespace that represents a data product. Format: `{domain}.{product}`. Stores product metadata in namespace properties with `floe.product.*` prefix. See [ADR-0030](../architecture/adr/0030-namespace-identity.md).

### Namespace Properties
Key-value metadata stored in an Iceberg catalog namespace. floe uses properties prefixed with `floe.` to store product and contract registration information.

---

## M

### Manifest
See [Shared Glossary](../contracts/glossary.md#manifest).

### Manifest (dbt)
The `manifest.json` file produced by `dbt compile`. Contains the compiled project including models, tests, and dependencies.

### Marquez
Open-source metadata service for data lineage. Default backend for OpenLineage events in floe.

### MCP (Model Context Protocol)
Standard protocol for AI agent tool integration. Cube exposes an MCP server for AI-powered data queries.

### Materialization
The process of executing a transformation and persisting results. Dagster "materializes" assets.

---

## O

### ODCS
Open Data Contract Standard—a Linux Foundation standard (via Bitol) for defining data contracts in YAML format. floe uses ODCS v3.x via `datacontract-cli`. See [ADR-0027](../architecture/adr/0027-odcs-standard-adoption.md).

### OpenLineage
See [Shared Glossary](../contracts/glossary.md#openlineage).

### OpenTelemetry (OTel)
See [Shared Glossary](../contracts/glossary.md#opentelemetry).

### OTLP
OpenTelemetry Protocol—the wire format for exporting telemetry data.

---

## P

### manifest.yaml
The platform configuration file (Platform Team). Defines compute target, plugins, governance policies, naming conventions, and quality gates. Compiled to immutable OCI artifacts.

### Pipeline
A sequence of data transformations defined in `floe.yaml`.

### Plugin
An extension to floe discovered via Python entry points. Can add custom transforms, targets, or catalogs.

### Pre-aggregation
Materialized rollup tables in Cube Store. Pre-computed aggregations that provide sub-second query performance.

### Polaris
Apache Polaris—open-source REST catalog for Apache Iceberg. Default catalog for floe.

### Profiles.yml
dbt configuration file specifying database connections. Generated by floe-dbt based on compute target.

### Pydantic
Python library for data validation using type hints. floe uses Pydantic for all schemas.

---

## R

### Registration (Product)
The process of claiming a namespace in the Iceberg catalog during `floe compile`. First-to-register wins ownership. The repository URL is stored in namespace properties to verify ownership on subsequent compilations. See [ADR-0030](../architecture/adr/0030-namespace-identity.md).

### Runtime
See [floe](#floe).

### floe
The open-source Data Execution Layer (Apache 2.0). Integrates Dagster, dbt, Iceberg, Polaris, and Cube into a cohesive framework. This is the canonical name for the execution layer. See [Shared Glossary](../contracts/glossary.md) for cross-repository terms.

> **Terminology Note:** "floe" (lowercase, hyphenated) is the canonical term. "Runtime" is acceptable shorthand. The terms "Data Plane" and "Data Runtime" are deprecated.

### floe-semantic-cube
floe plugin package (`plugins/floe-semantic-cube/`) that wraps Cube configuration and dbt model sync. Provides semantic layer capabilities.

---

## S

### Schema Drift
A change in the actual data schema compared to the contract definition. Detected by ContractMonitor comparing live schema against `datacontract.yaml`. Breaking drift (removed columns, type changes) triggers violations.

### Semantic Layer
An abstraction layer that defines business-friendly metrics, dimensions, and entities on top of physical data models. Cube provides the semantic layer for floe.

### SLA (Service Level Agreement)
Quantitative guarantees in a data contract. Includes freshness (max data age), availability (uptime percentage), and quality thresholds. Defined in `slaProperties` section of `datacontract.yaml`.

### SDA
Software-Defined Asset. See [Asset](#asset-dagster).

### Span
A unit of work in distributed tracing. Spans are nested to form traces.

### Standalone Mode
The default operating mode for floe. User manages infrastructure directly.

---

## T

### Target
See [Compute Target](#compute-target).

### Telemetry
Observability data: traces, metrics, and logs.

### Trace
A collection of spans representing an end-to-end operation across services.

### Transform
A data transformation step. Currently supports `dbt` type only. Python transforms are deferred to future scope due to integration complexity with telemetry and lineage.

---

## V

### Validation
The process of checking `floe.yaml` against the schema. Performed by floe-core.

---

## Abbreviations

| Abbreviation | Meaning |
|--------------|---------|
| API | Application Programming Interface |
| CI/CD | Continuous Integration / Continuous Deployment |
| CLI | Command-Line Interface |
| dbt | Data Build Tool |
| DX | Developer Experience |
| GHCR | GitHub Container Registry |
| HA | High Availability |
| K8s | Kubernetes |
| ODCS | Open Data Contract Standard |
| OSS | Open Source Software |
| OTel | OpenTelemetry |
| OTLP | OpenTelemetry Protocol |
| PyPI | Python Package Index |
| RBAC | Role-Based Access Control |
| REST | Representational State Transfer |
| SDA | Software-Defined Asset |
| SDK | Software Development Kit |
| SLA | Service Level Agreement |
| SQL | Structured Query Language |
| TLS | Transport Layer Security |
| UI | User Interface |
| UUID | Universally Unique Identifier |

---

## Package Names

### Foundation Packages (Enforced)

| Package | Description |
|---------|-------------|
| `floe-core` | Schema definitions, interfaces (ABCs), enforcement engine |
| `floe-cli` | Command-line interface |
| `floe-dbt` | dbt framework for SQL transformations (framework enforced; compilation environment pluggable via DBTPlugin) |
| `floe-iceberg` | Iceberg table utilities (not pluggable) |

### Plugin Packages (Pluggable)

| Package | Description |
|---------|-------------|
| `floe-orchestrator-dagster` | Dagster orchestration plugin |
| `floe-orchestrator-airflow` | Airflow orchestration plugin |
| `floe-compute-duckdb` | DuckDB compute plugin |
| `floe-compute-spark` | Spark compute plugin |
| `floe-compute-snowflake` | Snowflake compute plugin |
| `floe-catalog-polaris` | Polaris catalog plugin |
| `floe-catalog-glue` | AWS Glue catalog plugin |
| `floe-semantic-cube` | Cube semantic layer plugin |
| `floe-ingestion-dlt` | dlt ingestion plugin |
| `floe-secrets-eso` | External Secrets Operator plugin |

See [04-building-blocks](04-building-blocks.md) for the full plugin architecture.
