# Platform Observability Defaults Design

## Objective

Make observability a default capability of every Floe data product.

Floe should automatically emit, collect, and expose traces, metrics, logs, and
lineage for runtime execution without requiring Data Engineers to configure
instrumentation or write observability code. Platform Engineers should choose
the observability backend profile once at deployment time; plugins and data
products must remain backend-neutral.

Issue #360 remains the immediate alpha proof point, but the design target is
broader than Customer 360. Customer 360 should prove that the platform-level
contract works for a real composed data product.

## Current System Map

The repository already has several observability pieces:

- ADR-0006 establishes OpenTelemetry as the enforced emission and collection
  standard for traces, metrics, and logs.
- ADR-0035 separates telemetry backends from lineage backends, preserving
  independent pluggability for OTLP and OpenLineage paths.
- `docs/contracts/observability-attributes.md` defines an initial `floe.*`
  attribute contract.
- `floe-core` includes tracer factories, span decorators, semantic convention
  models, sanitization helpers, metrics helpers, and instrumentation audit code.
- `floe-orchestrator-dagster` emits OpenLineage events for generated runtime
  assets, including trace-correlation facets when an active span exists.
- `floe-dbt-core` emits command-level spans around dbt compile/run and captures
  dbt event callback data.
- `floe-ingestion-dlt` emits ingestion run spans and can record rows, bytes,
  duration, and success/failure metadata.
- `floe-iceberg` traces some table lifecycle operations.
- `charts/floe-platform` deploys an OTel collector and alpha observability
  services, but current metrics and logs pipelines are not yet sufficient as
  a user-facing observability proof.
- The Customer 360 demo has proven lineage and minimal traces, but current
  live validation showed shallow trace depth and empty Prometheus/Grafana
  evidence for Floe-level application metrics.

The gap is not absence of observability code. The gap is that observability is
not yet a mandatory runtime contract across generated execution units and
plugin boundaries.

## Non-Negotiable Principles

- OpenTelemetry is the canonical telemetry emission path.
- OpenLineage remains the canonical data lineage path.
- Telemetry and lineage backends are independently pluggable.
- Data Engineers configure no observability for normal Floe products.
- Platform Engineers configure backend selection once through deployment
  bindings or manifest-backed platform configuration.
- Plugins emit standard signals and attributes; they do not know about backend
  implementations such as Loki, Datadog, CloudWatch, Tempo, or Jaeger.
- `CompiledArtifacts` remains secret-free.
- Runtime observability context must never include resolved credentials,
  tokens, passwords, secret values, or full connection strings.
- Metrics must avoid high-cardinality labels by default. Run IDs belong in
  traces, logs, lineage events, and exemplars, not ordinary Prometheus labels.
- Helm and renderers consume resolved deployment bindings. They must not
  rediscover plugin config or hard-code backend-specific assumptions.

## Approaches Considered

### Approach 1: Customer 360 Patch

Add just enough spans, metrics, and logs to make the Customer 360 demo look
better.

Pros:

- Fastest path to close the immediate issue.
- Low architectural surface area.

Cons:

- Solves the demo, not the platform.
- Encourages product-specific instrumentation.
- Risks leaking implementation details between plugins.
- Does not give future data products observability by default.

Decision: reject as the primary approach. Customer 360 should be proof of the
platform contract, not a special-case implementation.

### Approach 2: Plugin-By-Plugin Instrumentation

Require each plugin to add richer spans, logs, and metrics internally.

Pros:

- Improves real plugin internals.
- Fits plugin ownership boundaries.
- Can provide useful domain-specific details for dbt, dlt, Iceberg, catalog,
  storage, and semantic layers.

Cons:

- Does not guarantee every generated product gets a root runtime envelope.
- Can drift into inconsistent span names and attributes.
- Places too much burden on plugin authors unless a stronger shared contract
  and validation suite exists.

Decision: use this as one layer, not the whole solution.

### Approach 3: Layered Platform Observability Contract

Create a mandatory observability contract with:

- a standard runtime context;
- orchestrator-owned runtime envelopes;
- shared plugin instrumentation conventions;
- backend-neutral OTel and OpenLineage emission;
- deploy-time backend profiles;
- release gates that prove logs, traces, metrics, and lineage are queryable.

Pros:

- Applies to all data products by default.
- Preserves composability and plugin boundaries.
- Keeps backend choice pluggable.
- Gives alpha a clear proof gate.
- Scales to future orchestrators and providers.

Cons:

- Requires a coordinated implementation plan.
- Requires stronger contract tests and live validation.
- Requires deployment chart changes for log and metric backends.

Decision: recommended.

## Recommended Design

Floe should treat observability as a runtime contract with four layers.

### Layer 1: Runtime Observability Context

Introduce a canonical runtime context carried through generated execution:

- product name;
- product version;
- environment;
- namespace;
- run ID;
- asset key;
- stage;
- table name;
- plugin type;
- plugin name;
- lineage namespace;
- trace ID and span ID when present.

This context is derived from `CompiledArtifacts`, orchestrator runtime state,
and resolved non-secret deployment bindings. It is not a user-authored data
product concern.

The context should be available to:

- generated orchestrator assets and jobs;
- dbt plugin operations;
- ingestion plugin operations;
- Iceberg write/read/commit paths;
- catalog and storage operations;
- semantic layer materialization and validation;
- quality/business validation checks;
- lineage emission.

### Shared Plugin Lifecycle Instrumentation

All plugin categories share lifecycle points through `PluginMetadata` and the
plugin lifecycle manager:

- configuration validation and `configure()`;
- plugin activation through `startup()`;
- dependency-aware activation order;
- `health_check()`;
- `shutdown()`;
- plugin load/discovery failures.

These lifecycle points should emit structured logs, spans, and bounded metrics
for every plugin type. They should record plugin type, plugin name, version,
floe API version, lifecycle phase, status, duration, and sanitized error class.

Lifecycle observability is different from product runtime observability. It
answers whether the platform and selected plugins are deployable and healthy.
Runtime observability answers what happened during a data product run. Alpha
validation should cover both where they affect the Customer 360 proof.

### Plugin-Type Observability Requirements

The current `PluginType` enum defines 14 plugin categories. The source tree also
contains plugin interfaces for network security, secret scanning, and sink
connectors that are not all first-class `PluginType` enum members. The
implementation plan must explicitly reconcile that registry surface.

| Plugin category | Lifecycle points requiring observability | Alpha scope |
| --- | --- | --- |
| Compute | dbt profile generation, catalog attachment SQL, macro path discovery, connection validation, resource requirement selection, runtime availability checks | Required for active compute plugin; query execution internals only when owned by the plugin |
| Orchestrator | definition generation, asset/job/sensor/schedule creation, run start/end, asset materialization, retries, failure classification, lineage forwarding | Required |
| Catalog | connect, namespace create/list/delete, table create/list/load/drop, credential vending, deployment binding generation, health checks | Required for active catalog; credential values must never be emitted |
| Storage | FileIO creation, warehouse URI resolution, PyIceberg catalog config, dbt profile config, Dagster IO manager config, Helm overrides, deployment binding generation, object read/write/delete where owned by Floe | Required for active storage; low-level library IO may be summarized at Floe wrapper boundaries |
| Telemetry backend | exporter config generation, Helm values, collector pipeline validation, backend connection validation | Required as platform health evidence; backend internals remain plugin-owned |
| Lineage backend | transport config generation, namespace strategy, Helm values, connection validation, lineage event send/ack/failure | Required |
| DBT | compile, run, test, lint, manifest load, run result load, per-node model/test execution, callback event handling | Required for active dbt runtime |
| Semantic layer | dbt manifest sync, security context generation, datasource config generation, API endpoint exposure, Helm overrides, semantic API health/query readiness | Required when semantic layer is part of alpha demo proof, especially Cube |
| Ingestion | pipeline creation, source binding, run start/end, source load, destination table write, rows/bytes/duration/failure, deployment binding generation | Required for active ingestion plugin |
| Secrets | secret reference lookup, secret write if supported, multi-key lookup, pod env spec generation, backend availability, access denied/not found classification | Required for platform health; runtime proof should record only reference identity and outcome, never key values or secret names if they are sensitive |
| Identity | authentication, token validation, user info lookup, OIDC config discovery, issuer/realm availability, access-denied/token-expired classification | Required for configured identity paths; do not emit tokens or PII |
| Quality | config validation, quality gate validation, suite/check execution, expectation mapping, quality score calculation, quality lineage facets | Required for active quality checks |
| RBAC | service account, role, role binding, namespace, and pod security context generation | Required as compile/deploy evidence; not a Customer 360 runtime trace unless invoked during deployment validation |
| Alert channel | alert config validation, delivery attempt, retry, success/failure, destination type, contract violation correlation | Required for alert plugins selected in alpha; actual destinations may be mocked only in non-live tests |

Additional interfaces and registry gaps:

- Network security plugins expose policy, default-deny, DNS egress, pod security,
  container security, and writable-volume generation. They have an entry point
  in existing plugin packages and should be observable as security deployment
  evidence. The implementation plan should decide whether to add
  `PluginType.NETWORK_SECURITY` or document a separate extension path.
- Secret scanner plugins expose file and directory scanning. They should emit
  scan duration, finding counts by severity/type, and sanitized failure details
  when enabled. They should not emit file contents or secret material.
- Sink connectors expose sink discovery, sink creation, writes, and source
  config generation. When implemented by an ingestion plugin, sink writes should
  be traced as egress operations with rows, bytes, destination type, and status.

This does not mean every plugin category must receive deep runtime
instrumentation in the first alpha implementation. It does mean every plugin
category must have an explicit observability decision: required now, compile or
deployment evidence only, deferred until the plugin enters the alpha cutline, or
registry contract cleanup first.

### Layer 2: Orchestrator Runtime Envelopes

The orchestrator plugin owns the default runtime envelope because it generates
the execution units.

For Dagster, every generated asset or job should create a standard parent span
and structured log scope before calling plugin-specific work. The envelope must
record:

- execution start and finish;
- status;
- duration;
- error classification;
- asset key;
- run ID;
- product identity;
- plugin category;
- table identity when known.

This creates default observability even when a plugin has not yet added rich
child spans.

### Layer 3: Plugin Domain Instrumentation

Plugins add child spans, metrics, and logs for their own domain. They should use
shared Floe semantic conventions rather than inventing per-plugin attribute
names.

Required alpha plugin coverage:

- dbt: command spans plus per-node model/test execution spans from dbt events
  or run results.
- dlt: source-load spans with source, destination table, write mode, rows,
  bytes, duration, and failure metadata.
- Iceberg: table create, load, write, commit, read validation, and failure
  spans.
- catalog: connect, namespace/table/catalog API operation spans, credential
  vending outcomes, and health checks with sanitized endpoint identity.
- storage: deployment binding/config generation plus object/prefix operation
  spans and metrics using logical storage identity, never credentials.
- lineage: OpenLineage event emission spans and correlation attributes.
- secrets and identity: security-sensitive lifecycle and access outcomes with
  no tokens, secret values, or PII.
- quality/business validation: check-level spans, pass/fail metrics, and
  structured logs.

Plugin instrumentation should remain optional for unreleased plugins, but alpha
published packages must meet the contract for their advertised runtime paths.

### Layer 4: Backend Profiles And Collection

All telemetry flows through the OTel collector. Backend profiles configure
export, storage, and visualization.

The alpha self-hosted proof profile should be:

- Grafana as the primary inspection UI;
- Prometheus-compatible metrics;
- Loki-compatible log storage and query;
- the existing trace backend for traces, or Tempo if a Grafana-native trace
  backend is adopted in the same implementation plan;
- Marquez for OpenLineage.

The implementation should not hard-code this stack into plugins. It should be a
deployment profile resolved into chart values and collector pipelines.

Longer-term backend profiles may include:

- Grafana Cloud;
- Datadog;
- AWS CloudWatch/X-Ray;
- Honeycomb;
- self-hosted Tempo/Loki/Mimir;
- custom OTLP-compatible backends.

## Signal Requirements

### Traces

Every product run must produce a queryable trace tree with:

- run root span;
- generated asset spans;
- dbt model/test spans;
- ingestion source spans;
- Iceberg table operation spans;
- catalog/storage operation spans;
- lineage emission spans;
- quality/business validation spans;
- error status and sanitized exception details.

### Logs

Logs are a first-class alpha proof signal.

Every runtime log emitted by Floe-managed execution should be structured and
queryable in the configured log backend. Logs must include enough correlation
fields to answer:

- which product emitted this log;
- which run emitted this log;
- which asset/table/plugin emitted this log;
- which trace/span this log belongs to;
- whether this log represents product failure or infrastructure failure.

The alpha proof must allow a user to query Customer 360 logs in Grafana by
product and run ID.

### Metrics

Floe should emit low-cardinality metrics for:

- product run count;
- product run duration;
- product run failures;
- asset materialization count and duration;
- dbt node count, duration, and failures;
- ingestion rows/bytes/duration/failures;
- Iceberg write/read/commit counts and failures;
- catalog/storage operation duration and failures;
- quality/business validation pass/fail counts.

Metrics should use bounded labels such as product, environment, plugin type,
plugin name, asset kind, status, and table namespace. They should avoid raw run
IDs, raw paths, raw SQL, customer identifiers, or secret-bearing values as
labels.

### Lineage

OpenLineage remains independent from OTel but must be correlated with the same
product, run, asset, and trace context.

The Customer 360 proof should show that a user can move from:

- product or table in lineage;
- to the run ID;
- to trace/log/metric evidence for the same execution.

## Alpha Customer 360 Proof Gate

Customer 360 validation should prove the platform contract end to end.

Required manual proof:

- Grafana can query Customer 360 logs by product and run ID.
- Grafana can show Customer 360 metrics for runs, duration, failures, rows, and
  checks.
- The trace backend can show a model/table-level trace tree for the same run.
- Marquez can show lineage jobs/datasets for the same run.
- A reviewer can correlate a table or model across lineage, traces, logs, and
  metrics without reading source code.

Required automated proof:

- demo validation captures a fresh run ID;
- trace assertions verify required spans and attributes for the fresh run;
- log assertions verify queryable structured logs for the fresh run;
- metric assertions verify expected Floe series exist and have fresh samples;
- lineage assertions verify OpenLineage jobs/datasets for the fresh run;
- failure messages distinguish product failures from infrastructure failures.

The validation must fail loudly when a backend is reachable but lacks fresh
evidence. Stale seeded telemetry must not satisfy the release gate.

## Documentation Updates

The implementation plan should update:

- README alpha observability claims;
- demo manual validation guide;
- Customer 360 walkthrough;
- observability attributes contract;
- telemetry backend plugin documentation;
- chart/backend profile documentation;
- release gate documentation;
- troubleshooting docs for missing traces, logs, metrics, or lineage;
- any docs that currently imply Jaeger-only observability or stdout-only logs.

Docs should clearly distinguish:

- enforced emission standard: OpenTelemetry;
- enforced collection standard: OTel collector;
- pluggable telemetry backend: Grafana/Loki/Prometheus/Jaeger/Tempo/Datadog/etc.;
- pluggable lineage backend: Marquez/Atlan/OpenMetadata/etc.

## Out Of Scope

- Building a custom observability UI.
- Requiring Data Engineers to annotate data product code.
- Making one commercial backend mandatory.
- Full production retention, alerting, SLO, and incident-management policy.
- Provider-specific deep metrics unless exposed through a plugin contract.
- Emitting secrets, raw SQL with sensitive literals, credentials, or PII into
  telemetry.
- Making unreleased or non-alpha plugins satisfy the alpha runtime proof gate.

## Implementation Workstreams

This design should be implemented through separate bounded plans:

1. Observability context and semantic convention cleanup.
2. Plugin registry surface reconciliation for network security, secret
   scanning, and sink connector observability decisions.
3. Orchestrator runtime envelopes for generated execution units.
4. Plugin instrumentation uplift for dbt, dlt, Iceberg, catalog, storage,
   lineage, and validation paths.
5. Security-sensitive lifecycle instrumentation for secrets, identity, RBAC,
   alert channels, and network security deployment evidence.
6. OTel collector and backend profile wiring for traces, metrics, and logs.
7. Customer 360 proof gate and release validation uplift.
8. Documentation and troubleshooting updates.

These workstreams should be planned separately before implementation to avoid a
large, hard-to-review observability rewrite.

## Acceptance Criteria

- Every alpha data product receives default observability from platform runtime
  generation, not product-authored instrumentation.
- Customer 360 proves queryable traces, metrics, logs, and lineage for one fresh
  run.
- Logs are queryable in an observability backend, not merely visible as pod
  stdout.
- Backend choice is pluggable through platform deployment configuration.
- Plugins emit backend-neutral signals using shared conventions.
- `CompiledArtifacts` remains secret-free.
- Release validation rejects stale telemetry and distinguishes product failures
  from infrastructure failures.
