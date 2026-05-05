# dlt Ingestion E2E Design

## Context

Customer 360 currently proves the transform path through dbt seed data, but the
`floe-ingestion-dlt` plugin has not been executed as part of a product-level E2E
flow. The strategic goal is broader than adding a plugin test: ingestion should
reinforce Floe's user experience promise that platform engineers choose and
operate capabilities once, while data engineers declare product intent in
`floe.yaml` and inherit the governed runtime.

The current Dagster runtime also has a known blocker: compiled JSON ingestion
configuration cannot construct executable dlt source objects, so runtime loading
fails loudly when ingestion workloads are present. This design closes that
product-experience gap instead of bypassing it with test-only Python objects.

## Goals

- Keep Customer 360 as a simple user-facing demo: local CSV files become raw
  Iceberg tables, then dbt builds the existing Customer 360 mart.
- Add a platform ingestion E2E matrix for realistic landing-zone ingestion:
  CSV, JSONL, and Parquet from MinIO/S3-compatible storage.
- Convert declarative ingestion configuration into executable dlt runtime
  sources without exposing dlt, Dagster, Polaris, or MinIO wiring to data
  engineers.
- Distinguish product-data failures from platform/infrastructure failures in
  test assertions and runtime errors.
- Validate real dlt, real Polaris, and real MinIO/S3 behavior with no mocks in
  E2E tests.

## Non-Goals

- REST API or SQL database ingestion sources.
- CDC, streaming, or Airbyte.
- A full schema-evolution matrix beyond the selected CSV/JSONL/Parquet edge
  cases.
- A broad dbt `source()` migration unless implementation needs it. dbt
  `source()` is the target semantic model for externally loaded raw tables, but
  preserving current Customer 360 dbt SQL is acceptable for Alpha compatibility.

## User Experience Boundary

Platform engineers own `manifest.yaml`: dlt selection, Polaris, MinIO/S3,
credentials, observability, retry defaults, and governance. They should not
write per-product Dagster ingestion assets or hand-build dlt source objects.

Data engineers own `floe.yaml`: source name, format, path or prefix,
destination raw table, write mode, schema contract, and optional cursor or
primary key. The same declaration shape should work for local demo files and
governed object-storage landing zones.

Floe owns the translation: compiled ingestion config becomes orchestrator
execution units upstream of dbt.

Example product-level shape:

```yaml
ingestion:
  sources:
    - name: raw_customers
      source_type: filesystem
      format: csv
      path: seeds/raw_customers.csv
      destination_table: customer_360_raw.raw_customers
      write_mode: replace
      schema_contract: evolve
```

## Architecture

The runtime flow is:

```text
floe.yaml ingestion declarations
  -> floe-core compile
  -> CompiledArtifacts.plugins.ingestion.config
  -> Dagster runtime source-construction layer
  -> one ingestion asset per source
  -> DltIngestionPlugin.create_pipeline()
  -> DltIngestionPlugin.run()
  -> Iceberg raw tables via Polaris + MinIO/S3
  -> dbt staging/intermediate/mart models
```

The key implementation unit is a JSON-safe source-construction layer in the
orchestrator/runtime boundary. It takes compiled dictionaries and constructs dlt
filesystem resources at runtime. Executable dlt objects must not be stored in
`CompiledArtifacts`.

The source-construction layer should support:

- local paths for demo/bootstrap flows.
- S3-compatible paths for platform landing-zone flows.
- `csv`, `jsonl`, and `parquet` readers.
- table naming that lands each source in a deterministic Iceberg raw table.
- write mode and schema contract forwarding to dlt.

Before broad implementation, add a focused spike or executable guard for the
actual dlt Iceberg destination configuration against Polaris. dlt's current
documentation describes Iceberg through the filesystem destination and
PyIceberg catalog configuration, so implementation should not assume a generic
`destination="iceberg"` shortcut.

## Customer 360 Demo E2E

Customer 360 remains the readable product demo.

Validate:

- `demo/customer-360/floe.yaml` declares three CSV ingestion sources.
- Runtime creates one ingestion execution unit per source.
- dlt loads `raw_customers.csv`, `raw_transactions.csv`, and
  `raw_support_tickets.csv`.
- Data lands in the raw Iceberg tables expected by the existing dbt models.
- dbt produces `mart_customer_360`.
- `IngestionResult` reports success and expected row counts.
- `health_check()` is healthy against real dlt plus real destination/catalog
  reachability.

This path should avoid becoming a file-format matrix. Its job is to show the
simple data engineer workflow.

## Platform Ingestion Matrix E2E

The platform capability suite is independent from Customer 360 and should create
isolated namespaces and MinIO/S3 prefixes.

Mandatory happy paths:

- CSV from MinIO/S3 landing prefix.
- JSONL from MinIO/S3 landing prefix.
- Parquet from MinIO/S3 landing prefix.

For each format, assert:

- declarative source config compiles into executable ingestion.
- dlt runs with no mocks.
- Iceberg table exists in Polaris.
- row count matches fixture.
- schema matches expected fields and types.
- `IngestionResult.success` is true.
- `rows_loaded` is correct.
- rerun behavior matches configured `write_mode`.

Mandatory edge cases:

- missing file or prefix: clean source/path failure.
- empty file: standardized behavior, either success with zero rows or an
  explicit empty-source failure.
- malformed JSONL: clean parse failure and no silent partial success.
- CSV type drift: visible schema-contract behavior.
- Parquet schema mismatch: visible schema-contract behavior.
- duplicate rerun with `replace`: no duplicate rows.
- bad destination namespace or missing write grant: clean destination failure.
- bad MinIO/S3 credential or endpoint: clean platform/config failure.

Schema-contract E2E should start with `evolve` and `freeze`. Do not claim broad
`discard_value` coverage until the exact dlt file-reader path is proven against
real fixtures, because dlt documents nuances around contract modes and
validation.

## Error Handling

Errors should be actionable and route ownership correctly.

Data product errors should include source name, path or prefix, format,
destination table, and the failing field where available. Examples: missing
object, malformed JSONL, unsupported format, schema-contract violation.

Platform errors should identify the platform dependency. Examples: Polaris
unreachable, MinIO/S3 endpoint failure, missing write grants, invalid
credentials, or dlt destination configuration failure.

Tests should assert this distinction so failures do not collapse into generic
runtime exceptions.

## Observability

Each ingestion execution unit should emit:

- structured logs with source name, format, destination table, status, rows,
  bytes, and duration.
- OpenTelemetry spans for source construction, pipeline creation, and pipeline
  run.
- OpenLineage dataset events for source file/prefix to Iceberg raw table where
  current runtime support allows it.

If full lineage for ingestion is not available in this slice, it should be
tracked as follow-up and not block the Alpha ingestion MVP.

## Validation Sources

The design aligns with official documentation:

- dlt filesystem source supports local and remote storage, including S3-style
  paths, and natively supports CSV, JSONL, and Parquet.
- dlt filesystem destination supports S3-compatible storage such as MinIO and
  supports Iceberg table format.
- dlt Iceberg support uses PyIceberg and PyIceberg catalogs, including REST
  catalogs.
- Apache Polaris is an Apache Iceberg REST catalog implementation.
- Dagster's dlt integration represents dlt sources and pipelines as assets.
- dbt sources are the correct target semantic model for raw tables loaded by
  extract/load tools.

References:

- https://dlthub.com/docs/dlt-ecosystem/verified-sources/filesystem/basic
- https://dlthub.com/docs/dlt-ecosystem/destinations/filesystem
- https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
- https://polaris.incubator.apache.org/releases/latest/
- https://docs.dagster.io/integrations/libraries/dlt
- https://docs.dagster.io/guides/build/assets
- https://docs.getdbt.com/docs/build/sources

## Acceptance Criteria

- Customer 360 has a declared CSV ingestion path and passes its E2E demo flow
  through real dlt, Polaris, MinIO/S3, and dbt.
- The platform matrix E2E passes for CSV, JSONL, and Parquet from MinIO/S3.
- Edge-case E2E failures are deterministic and produce ownership-routed error
  messages.
- Runtime no longer rejects compiled JSON ingestion config solely because it
  lacks executable dlt source objects.
- E2E tests use isolated namespaces/prefixes and clean up Iceberg/S3 artifacts.
- No E2E ingestion test mocks dlt, Polaris, or MinIO/S3.
