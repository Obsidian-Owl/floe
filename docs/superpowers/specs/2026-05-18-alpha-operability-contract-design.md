# Alpha Operability Contract Design

## Objective

Define the alpha operability contract that every supported Floe data product
must satisfy by default, then use Customer 360 as the live proof fixture.

This is not a demo polish task. The goal is to make the platform operable: a
Platform Engineer or Data Engineer should be able to answer what ran, what
changed, what failed, where data landed, and how lineage connects without
adding product-specific observability code.

## Current System Map

The merged alpha demo now emits and validates more than the first alpha proof:

- Dagster has a completed Customer 360 run:
  `9f08fa03-ec58-420f-ad9a-2430e0f73307`.
- Jaeger exposes service `customer-360`.
- Loki receives structured OpenTelemetry logs for Customer 360 asset start and
  completion events.
- The Floe chart Prometheus exposes Floe metrics such as
  `floe_asset_materializations_total` and `floe_ingestion_dlt_runs_total`.
- Marquez has a `customer-360` namespace, the product run, model/table jobs,
  datasets, schema facets, column-lineage facets, and parent-run linkage.
- MinIO/Iceberg contains Customer 360 table data and metadata.
- The Customer 360 validator can pass when pointed at the actual live namespace
  and services.

The live validation also exposed gaps:

- Marquez in the Floe chart is API/admin only. No Marquez UI surface is
  deployed. Root `/` returns `404`.
- Loki is API only. Root `/` returns `404`; `/ready` and
  `/loki/api/v1/query_range` are the meaningful surfaces.
- Grafana is deployed from `kube-prometheus-stack`, but its default Prometheus
  datasource points at the monitoring-stack Prometheus, while Floe application
  metrics are available from the Floe chart Prometheus.
- Several Grafana dashboards query aspirational or legacy metric names, such as
  `dagster_run_count_total`, `openlineage_event_total`,
  `dbt_test_pass_total`, and `dbt_model_row_count`, which are not emitted by
  the current alpha runtime.
- Marquez lineage graph data is usable through job inputs/outputs and dataset
  facets, but graph edge output is not yet a strong proof surface.

## Problem Statement

Floe currently has queryable observability evidence, but not yet a complete
operability baseline. A passing demo validator proves important signals exist,
while manual inspection still reveals drift between:

- emitted telemetry;
- dashboard queries;
- backend datasource wiring;
- documentation about UI versus API surfaces;
- what a user should expect when operating a data product.

Alpha should not publish empty or misleading dashboards. If a surface is present
in the demo, its data must be backed by validated live evidence.

## Non-Negotiable Principles

- OpenTelemetry remains the canonical path for traces, logs, and metrics.
- OpenLineage remains the canonical data-lineage path.
- Backends remain pluggable. Floe code emits portable signals and must not
  couple directly to Loki, Prometheus, Grafana, Jaeger, Tempo, or Marquez.
- Data Engineers configure no observability for normal Floe products.
- Platform Engineers choose backend profiles through deployment configuration.
- `CompiledArtifacts` remains secret-free.
- Runtime signals must never emit secrets, tokens, credential values, private
  keys, PII payloads, full environment dumps, or connection URLs with userinfo.
- Prometheus labels must remain bounded. Run IDs, trace IDs, span IDs, raw file
  paths, object keys, and table names do not belong in ordinary aggregate
  metric labels.
- Dashboards are part of the product surface only when their backing queries
  are live-validated.

## Approaches Considered

### Approach 1: API-Only Alpha Evidence

Keep the current validator centered on direct Dagster, Marquez, Jaeger, Loki,
Prometheus, and storage API queries. Document Grafana dashboards as best-effort.

Pros:

- Smallest near-term scope.
- Preserves backend-neutral validation.
- Avoids over-investing in Grafana before the metric contract stabilizes.

Cons:

- Leaves visible dashboards that can be empty or misleading.
- Does not give operators a polished baseline.
- Lets datasource drift persist.

Decision: insufficient as the long-term alpha baseline.

### Approach 2: Dashboard Patch

Rewrite Grafana dashboards to match only the metrics that currently exist.

Pros:

- Makes the visible demo feel healthier quickly.
- Forces dashboard queries to match current telemetry.

Cons:

- Can hide missing platform signals.
- Does not define the minimum observability contract.
- Risks locking the dashboard shape to today rather than the platform target.

Decision: useful as an implementation slice, but not the design center.

### Approach 3: Operability Contract With Live Proof

Define a minimum contract for run control, traces, logs, metrics, lineage,
storage evidence, and dashboards. Expand live validation so Customer 360 proves
the whole contract on a deployed DevPod/Hetzner environment.

Pros:

- Makes observability a platform guarantee, not a demo artifact.
- Preserves composability and backend pluggability.
- Prevents empty or aspirational dashboards.
- Gives release readiness a clear, repeatable gate.
- Scales to later data products and backend profiles.

Cons:

- Requires coordinated updates to emitters, chart wiring, dashboards, docs, and
  validation.
- Requires careful handling of Prometheus cardinality and backend-specific
  checks.

Decision: recommended.

## Recommended Design

### Contract Scope

The alpha operability contract has six proof areas.

1. Run control:
   Dagster must expose the data-product run, final state, product/job identity,
   run ID, and correlation tags.

2. Traces:
   A trace backend must expose a run root span plus child spans for ingestion,
   dbt/model materialization, catalog/storage/Iceberg lifecycle, and lineage
   emission where those lifecycle points occur.

3. Logs:
   A Loki-compatible backend must expose structured start, completion, and
   failure events for product runtime work, queryable by product and run ID.

4. Metrics:
   A Prometheus-compatible backend must expose bounded, aggregate metrics for
   data-product runs, asset/materialization outcomes, ingestion runs and
   durations, lineage emission outcomes, and quality checks when quality checks
   are part of the product.

5. Lineage:
   Marquez/OpenLineage must expose the product namespace, product run,
   model/table jobs, datasets, schema facets, column-lineage facets,
   `ParentRunFacet` linkage, and trace-correlation facets.

6. Dashboard truthfulness:
   Grafana dashboards may be part of the alpha demo only when every panel query
   is either backed by live data or explicitly hidden from the curated demo.

### Backend Surface Expectations

Each backend must be documented as either UI-capable or API-only for the alpha
profile.

| Backend | Alpha surface | Required proof |
| --- | --- | --- |
| Dagster | UI and GraphQL/API | Run exists, completed, and carries product/run context |
| Marquez | API/admin only in current chart | Namespace, jobs, runs, datasets, facets, and lineage graph query |
| Jaeger | UI and API | Service and run traces with required Floe attributes |
| Loki | API only | `/ready` succeeds and `query_range` returns structured product/run logs |
| Prometheus | API and optional UI | Contract metrics return live samples over the proof window |
| Grafana | UI | Datasources and dashboard panel queries are validated before demo exposure |
| MinIO/Iceberg | UI/API plus command proof | Expected table data and metadata are readable |
| Cube | API in current demo | If included in the proof, queries must validate semantic access, not only process health |

Root `404` responses are not failures for API-only backends when documented
health and query endpoints pass.

### Metrics Contract

The current alpha metric contract is too small for a useful operating baseline.
The next implementation plan should add or validate these families:

| Metric family | Required dimensions | Notes |
| --- | --- | --- |
| Data-product run count | product, environment, namespace, status, orchestrator plugin | No run ID label |
| Data-product run duration | product, environment, namespace, status, orchestrator plugin | Histogram preferred |
| Asset materialization count | product, environment, namespace, stage, plugin type/name, status | Existing `floe_asset_materializations_total` is the starting point |
| Asset materialization duration | product, environment, namespace, stage, plugin type/name, status | Needed for runtime dashboards |
| Asset failure count | product, environment, namespace, stage, plugin type/name, sanitized error type | Existing failure counter should be validated |
| dlt ingestion count/duration | product, environment, namespace, source type, status | Current `floe_product_name="unknown"` must be fixed or explicitly excluded |
| Lineage emission count/duration | product, environment, namespace, lineage backend, event type, status | Needed for Marquez/OpenLineage dashboards |
| dbt model execution count/duration | product, environment, namespace, model status, dbt plugin | Required before model-level dashboards are promoted |
| Quality check count/duration | product, environment, namespace, check suite, status | Required only when quality checks are part of alpha proof |

Grafana dashboards must query these contract metrics or be removed from the
curated alpha dashboard set.

### Lineage Contract

The validator must prove lineage at three levels:

1. Product run:
   `namespace=customer-360`, `job=customer-360`, and the Dagster run ID are
   present with final state `COMPLETED`.

2. Model/table jobs:
   Staging, intermediate, and mart jobs exist with expected inputs and outputs.
   `mart_customer_360` must be present.

3. Dataset detail:
   Datasets expose schema facets, column-lineage facets, and current versions.
   The mart dataset must show upstream links to the expected intermediate and
   staging datasets.

Graph API checks should use Marquez node IDs such as:

```text
dataset:customer-360:customer_360.main.mart_customer_360
job:customer-360:customer-360.model.customer_360.mart_customer_360
```

The graph proof should not depend only on the `edges` response field until the
Marquez API behavior is confirmed. Job `inputs` and `outputs`, dataset facets,
and parent-run facets are currently more reliable proof surfaces.

### Logs Contract

The log proof must query Loki using the Loki API, not the root URL.

Minimum query shape:

```logql
{service_name=~".+"} |= "customer-360" |= "<dagster.run_id>"
```

The validator should require:

- at least one start event;
- at least one completion or failure event;
- matching `floe.product.name`;
- matching `floe.run.id`;
- trace and span IDs on records emitted inside spans;
- asset/table context where known.

### Trace Contract

The trace proof should require:

- service `customer-360`;
- a run root span with `floe.run.id`;
- ingestion spans;
- dbt/model spans;
- catalog/storage/Iceberg spans;
- lineage emission spans;
- error/status attributes where applicable.

The validator should fail when evidence only proves a generic backend hit or a
single shallow trace.

### Grafana Contract

Grafana is release-demo eligible only if all curated dashboard panels pass.

For each curated dashboard panel, the live validator should extract the panel
query through the Grafana API, execute it against the panel datasource, and
classify the result:

| Classification | Meaning | Release-demo handling |
| --- | --- | --- |
| `backed_by_data` | Query returns data in the proof window | Keep panel |
| `valid_empty` | Query is valid but intentionally empty for this scenario | Panel must explain this or be hidden from alpha |
| `unknown_metric` | Metric does not exist | Remove or fix panel |
| `wrong_datasource` | Query works elsewhere but not through Grafana datasource | Fix datasource/provisioning |
| `invalid_query` | Backend rejects the query | Fix panel before release |

The current split between the Floe chart Prometheus and the monitoring-stack
Prometheus must be resolved by either:

- making Grafana query the Prometheus instance that scrapes Floe OTel metrics;
- making the monitoring-stack Prometheus scrape the Floe OTel metrics; or
- provisioning two explicit datasources and assigning each dashboard to the
  correct datasource.

The recommended alpha path is to make the monitoring-stack Prometheus scrape
Floe OTel metrics and keep Grafana's default datasource on the monitoring
Prometheus. That aligns with how operators expect kube-prometheus-stack to work.

### Validation Harness

The Customer 360 live validator should become the release proof harness for
this contract. It should produce deterministic evidence keys for:

- run control;
- storage outputs;
- business metrics;
- trace depth;
- log depth;
- metric families;
- lineage graph and facets;
- Grafana datasource health;
- Grafana panel query health when Grafana is in scope.

The harness should separate failures into:

- product failure;
- platform service failure;
- backend unreachable;
- no fresh evidence;
- wrong context;
- stale evidence;
- dashboard/datasource drift;
- contract gap.

This classification matters for DevPod/Hetzner validation because a broken
data product, a broken backend, and an empty dashboard are different failures.

## Workstreams

### Workstream 1: Contract And Evidence Matrix

Update the observability contract docs and Customer 360 validation docs to
define the required evidence in one place. Include the UI/API truth table and
explicitly document Marquez and Loki as API-only in the current alpha profile.

Deliverables:

- updated contract documentation;
- Customer 360 manual inspection guide;
- explicit accepted/failed evidence examples.

### Workstream 2: Metric And Trace Emitter Gap Closure

Map existing emitted series and spans against the contract, then add missing
runtime metrics and child spans through shared runtime/plugin boundaries.

Deliverables:

- data-product run metrics;
- asset duration metrics;
- lineage emission metrics;
- dbt/model metrics;
- fixed ingestion product labels;
- stronger trace depth for active Customer 360 lifecycle points.

### Workstream 3: Prometheus And Grafana Alignment

Resolve datasource drift and curate dashboards so they only show validated
metrics.

Deliverables:

- monitoring Prometheus scrape path for Floe OTel metrics, or explicit dual
  datasources;
- curated alpha dashboard list;
- removed or hidden aspirational panels;
- live panel-query validation.

### Workstream 4: Marquez Lineage Depth Validation

Expand lineage validation beyond "job exists" into graph, dataset, schema,
column lineage, parent-run, and trace-correlation evidence.

Deliverables:

- Marquez API proof helpers;
- graph-depth assertions;
- dataset facet assertions;
- documented API curl examples.

### Workstream 5: Release Gate Integration

Wire the expanded validator into release and weekly live validation lanes
without adding long-running E2E checks to every PR.

Deliverables:

- release-cycle live operability validation;
- weekly live operability validation;
- issue creation with logs/evidence on failure;
- no GitHub Release until all release gates pass.

## Testing And Validation Evidence

Required evidence before declaring this complete:

- unit tests for any new query builders and evidence classifiers;
- contract tests for emitted metric names, labels, and forbidden high-cardinality
  labels;
- integration tests for Prometheus/Loki/Jaeger/Marquez API query helpers;
- dashboard validation tests that prove curated panel queries are backed by live
  data or intentionally hidden;
- DevPod/Hetzner live run of Customer 360 showing the full evidence matrix;
- docs review confirming all manual links and UI/API claims match deployed
  surfaces.

## Out Of Scope

- Replacing Marquez with a different lineage backend.
- Replacing Loki, Prometheus, Jaeger, or Grafana.
- Making Grafana the canonical source of truth. API-queryable backend evidence
  remains the source of truth; Grafana is a curated presentation surface.
- Adding production-grade alerting and SLOs in this slice.
- Instrumenting every deferred plugin category beyond the active alpha cutline.
- Publishing aspirational dashboards that are not backed by emitted telemetry.

## Open Decisions

1. Whether to deploy a Marquez UI in the contributor demo or keep Marquez
   API-only for alpha.
2. Whether Grafana should use one Prometheus datasource that scrapes both
   Kubernetes and Floe metrics, or separate explicit datasources.
3. Whether Cube semantic queries enter the alpha operability contract now or
   remain a separate semantic-layer proof workstream.

## Recommended Next Step

Create an implementation plan from this spec with Workstreams 1, 3, and 4 as
the first slice. Those slices make the demo truthful and testable before adding
new runtime telemetry volume.
