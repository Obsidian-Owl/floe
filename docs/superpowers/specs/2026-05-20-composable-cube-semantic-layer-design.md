# Composable Cube Semantic Layer Design

Date: 2026-05-20
Status: Approved design, implementation not started; amended after
adversarial review

## Goal

Make Cube easy for platform engineers and data engineers to configure and use
through Floe's composition layer, without leaking Cube, compute, catalog, or
storage implementation details across plugin boundaries.

Customer 360 is the first proof fixture, but the feature is not Customer
360-specific. The outcome should be a reusable semantic-layer path for any Floe
data product that has a supported compute, catalog, storage, and semantic
selection.

The public consumption surface must also be semantic-provider-neutral. Users
should define, build, deploy, and consume Floe semantic APIs through stable
Floe contracts. Cube is the first backend implementation; a future dbt Semantic
Layer or other semantic plugin must not force users to rewrite data-product
definitions, platform deployment posture, or consumer-facing Floe API
contracts.

## Implemented System Map

The current system already has useful Cube primitives:

- `plugins/floe-semantic-cube` implements `SemanticLayerPlugin`.
- `CubeSchemaGenerator` converts dbt manifest model nodes into Cube YAML.
- `CubeSemanticPlugin.sync_from_dbt_manifest()` emits schema files and tracing
  attributes.
- `CubeSemanticPlugin.health_check()` checks the Cube API server.
- `plugins/floe-orchestrator-dagster` has a semantic sync Dagster asset that can
  call the semantic plugin after model materialization.
- `charts/floe-platform` includes a local Cube subchart with API, refresh
  worker, SQL service, secret, and optional Cube Store resources.
- `values-test.yaml` enables Cube for chart validation, while base
  `values.yaml` keeps Cube disabled.

The current system also has composition and release constraints that matter:

- `release/floe-release.yaml` excludes `floe-semantic-cube` from the alpha
  publish set because there is no proven semantic-layer E2E path yet.
- `docs/demo/customer-360-validation.md` explicitly says Cube is not part of the
  default alpha proof unless the platform enables it.
- `docs/superpowers/specs/2026-05-09-semantic-datasource-binding-design.md`
  already identifies the key contract gap: Cube datasource rendering is still
  static Helm values plus duck-typed compute discovery.
- `packages/floe-core/src/floe_core/composition` currently validates storage,
  catalog, ingestion, secret, and identity compatibility, but does not yet model
  semantic datasource requirements.
- The current semantic sync implementation is hosted by the Dagster
  orchestrator plugin, but the target semantic publication lifecycle must be
  expressed as an orchestrator-neutral runtime contract. Dagster may implement
  that contract as an asset; another orchestrator may implement it as an
  operator, task, job, or step.

## Current Gaps

1. `SemanticLayerPlugin.get_datasource_config(compute_plugin)` takes a live
   compute plugin instance. That is a leaky abstraction because the semantic
   plugin can discover compute implementation details.
2. `CubeSemanticPlugin.get_datasource_config()` duck-types
   `get_cube_datasource_config()` and falls back to a generic config bag.
3. `CubeSemanticPlugin.get_helm_values_override()` emits static
   `CUBEJS_DB_TYPE` and `CUBEJS_DB_NAME` values instead of consuming resolved
   deployment bindings.
4. The Cube chart can run, but it does not yet receive product-specific semantic
   model artifacts, datasource bindings, secret refs, SQL credentials, or API
   exposure through Floe contracts.
5. Data engineers do not have a Cube-neutral way to publish metrics,
   dimensions, access policy intent, or semantic API expectations.
6. Platform engineers do not have a repeatable manifest-level Cube profile that
   validates provider compatibility before deploy.
7. E2E validation does not prove semantic queries through Cube REST, GraphQL, or
   SQL against materialized product data.
8. Demo and dev values currently enable Cube while release docs classify Cube as
   outside the supported alpha proof. That is acceptable only if the service is
   explicitly documented as experimental and non-release-gating until semantic
   E2E evidence exists.

## Design Principles

- Capabilities, requirements, typed bindings, and resolver validation own
  cross-plugin contracts.
- Semantic plugins must not import or introspect concrete compute, catalog,
  storage, secrets, or identity implementations.
- `CompiledArtifacts` must remain secret-free.
- Helm/renderers must consume resolved deployment bindings instead of
  rediscovering plugin config.
- dbt remains the source of truth for SQL compilation and model metadata.
- Cube is the first implementation proof, not the only semantic provider the
  contract should allow.
- Platform engineer configuration belongs in `manifest.yaml`; data engineer
  semantic intent belongs in dbt metadata and/or `floe.yaml`.
- Customer 360 proves the platform path, but no contract should hardcode
  Customer 360 names, metrics, tables, or URLs.
- Orchestrator plugins may host semantic publication work, but semantic
  contracts must not name Dagster or depend on Dagster asset semantics.
- Consumer-facing Floe semantic APIs must remain stable across semantic
  provider implementations. Provider-specific endpoints are adapter details.

## Recommended Approach

Use a binding-first, provider-neutral semantic runtime with Cube as the first
backend adapter.

Floe core should derive semantic datasource, service, and model bindings from
the selected plugin graph after resolver validation. Cube then renders its
runtime configuration from those bindings. The semantic plugin receives a
secret-free, typed contract and never reaches into the active compute, catalog,
or storage plugin.

The design has two distinct planes:

- Compile-time desired state: secret-free semantic runtime bindings,
  publication intent, access policy intent, provider-neutral API descriptors,
  and expected artifact mount/publication targets.
- Runtime evidence: generated schema files, model publication status, semantic
  query results, freshness checks, and backend health evidence.

Runtime evidence must not be written back into `CompiledArtifacts`. It belongs
in validator output, run artifacts, observability backends, and release
evidence bundles.

This is preferred over demo-only Cube wiring because it preserves composition
and creates a reusable platform feature. It is also preferred over implementing
provider parity for every future semantic layer immediately, because Cube can
prove the contract first while the binding remains provider-neutral.

## Target Contracts

Exact class names can change during implementation, but the contract families
should be explicit.

The implementation plan must add an additive `deployment.semantic` contract to
`CompiledArtifacts` with a schema/version migration. It must not smuggle the
new bindings through `plugins.semantic.config`, because that would bypass
secret-free deployment validation and make renderers rediscover plugin config.

### Semantic Datasource Binding

Describes how the semantic layer reaches product data.

Required capabilities:

- datasource name, with `default` available for Cube compatibility
- engine or driver family, for example `duckdb`, `postgres`, `snowflake`, or
  `trino`
- catalog/table format context, for example Iceberg REST catalog URI, catalog
  name, warehouse, namespace, and table format
- storage projection facts needed by the compute driver, for example endpoint,
  region, path-style access, and server-side access mode
- environment variable refs and credential refs, not raw secrets
- optional initialization statements or config fragments owned by the resolved
  binding, not discovered by the semantic plugin

For the first Cube proof, the datasource binding must not rely on a local
`/tmp` DuckDB file unless that file is explicitly provided through a shared,
mounted runtime volume. The preferred proof path is a runtime-safe Iceberg or
object-storage-backed datasource binding that the semantic service pod can
reach independently of the orchestrator/code-location filesystem.

### Semantic Service Binding

Describes the provider-neutral semantic service surface exposed to users and
tools.

Required capabilities:

- internal service URL
- REST base path
- GraphQL path
- SQL host, port, database, user ref, and password ref when SQL wire protocol
  is enabled
- HTTP SQL path when the provider supports SQL over HTTP
- health endpoint
- auth mode and token/secret refs
- optional port-forward and docs metadata for demo/manual inspection
- stable Floe logical endpoint names, such as `metadata`, `query`, `sql_http`,
  `sql_wire`, and `graphql`, mapped to provider-specific paths by the semantic
  plugin adapter

Cube-specific mapping for the first backend:

- REST query proof uses `/cubejs-api/v1/load`.
- REST metadata proof uses `/cubejs-api/v1/meta`.
- REST HTTP SQL, if used, goes through `/cubejs-api/v1/cubesql`.
- SQL wire protocol requires `CUBEJS_PG_SQL_PORT`, `CUBEJS_SQL_USER`, and
  `CUBEJS_SQL_PASSWORD`.
- GraphQL uses `/cubejs-api/graphql`, but it is optional for the first release
  proof unless an explicit GraphQL metric query is added.
- `/readyz` and `/livez` are unprefixed health endpoints.

These details are Cube adapter behavior, not Floe's provider-neutral user API.

### Semantic Model Publication Binding

Describes desired semantic model publication, expected artifact targets, and
runtime mount expectations. It must not contain runtime-generated file lists
inside `CompiledArtifacts`.

Required capabilities:

- source dbt manifest path
- expected generated schema artifact directory or mount path
- artifact transport mode, for example `configmap`, `pvc`, `object-store`, or
  `oci-artifact`
- artifact size and lifecycle constraints for the chosen transport
- model include/exclude policy
- metric and dimension publication policy
- ownership and product metadata for observability and lineage
- provider schema path setting, such as Cube's `CUBEJS_SCHEMA_PATH`
- reload or rollout semantics when published model artifacts change

The first implementation must choose one artifact transport for Customer 360
and document its limits. A Kubernetes ConfigMap is acceptable only for small
generated model sets with explicit size guards and rollout/reload behavior. A
PVC, object-store bundle, or OCI artifact should be used when generated model
artifacts exceed ConfigMap limits or need stronger lifecycle guarantees.

### Semantic Access Policy Binding

Describes access policy intent without tying data engineers to Cube internals.

Required capabilities:

- typed identity claims source
- role/group names
- namespace validation
- row-level filters expressed in product terms where possible
- member-level include/exclude policy
- masking intent for sensitive fields
- default-deny publication and access semantics
- mapping to Cube security context as a renderer concern

The current Cube implementation accepts arbitrary namespace and role strings
and treats `"admin"` as a bypass role. That behavior is not acceptable as the
target contract. The implementation plan must define typed identity claims,
role mapping, namespace validation, unknown-role behavior, and explicit
admin-bypass semantics before Cube access policies become a supported path.

### Semantic Consumption API Contract

Describes how users and downstream tools consume semantic data through Floe
rather than through provider internals.

Required capabilities:

- logical API families: metadata, metric query, SQL query, optional GraphQL,
  and health
- supported query dialects and capability flags per provider
- provider-neutral request/response evidence fields for validation
- auth scopes required by each logical API family
- stable documentation labels and port-forward names
- provider adapter mapping to concrete endpoints and credentials

The first implementation can expose direct Cube URLs in demo docs, but those
URLs must be presented as the Cube adapter's current realization of Floe
semantic API bindings. Data-product definitions and platform manifests must not
depend on those URLs.

### Runtime Semantic Evidence

Describes runtime outputs that prove the semantic path worked. This is not a
compiled artifact contract.

Required evidence:

- generated schema artifact count and artifact target
- semantic model publication status
- semantic service health
- REST query status and metric values
- SQL query status and metric values when SQL is enabled
- exact product, run, model/table, and metric context
- freshness window and cache mode
- failure classification

## Configuration UX

### Platform Engineers

Platform engineers choose the semantic provider and runtime posture in
`manifest.yaml`.

The platform-level shape should answer:

- Is a semantic layer enabled?
- Which provider is selected?
- Which compute/catalog/storage combinations are allowed?
- Is REST, GraphQL, SQL, or all three exposed?
- Which auth/secret mode is required?
- Is Cube Store enabled, memory-only, or disabled?
- What are resource and persistence defaults?
- Which semantic signals are required for observability?

The platform engineer should not write Cube datasource env vars directly for a
normal Floe deployment. Those values should be rendered from resolved bindings.

### Data Engineers

Data engineers publish semantic intent through dbt metadata and/or `floe.yaml`.

The first implementation should prefer a typed dbt metadata namespace,
`meta.floe.semantic`, because dbt remains the source of truth for model
metadata. If `floe.yaml` also participates, the spec and implementation must
define precedence rules explicitly.

The data-product-level shape should answer:

- Which dbt models are semantic-published?
- Which measures and dimensions are published?
- Which metrics are validation gates?
- Which time dimensions and grains are expected?
- Which access policy groups apply?
- Which semantic APIs must be validated for the product?

Data engineers should not configure Cube deployment internals, service ports,
database credentials, or storage/catalog endpoints.

Semantic publication must be deny-by-default at both model and member level.
Unannotated columns, PII-like fields, and masked fields must not be published
as semantic dimensions or measures unless explicitly allowed by policy. The
current generator's "every column becomes a member" behavior must be retired or
quarantined before Cube becomes a supported semantic path.

## Runtime Flow

1. Platform manifest selects Cube and allowed datasource capability families.
2. Data product config marks models and metrics for semantic publication.
3. Core compilation validates semantic requirements against selected compute,
   catalog, storage, secrets, and identity capabilities.
4. Core compilation emits secret-free semantic datasource, service, model, and
   access policy bindings.
5. The selected orchestrator plugin hosts a semantic publication step using the
   common semantic publication contract. Dagster may implement this as an
   asset; other orchestrators may implement it differently.
6. The semantic publication step reads the dbt manifest and product semantic
   intent, then publishes provider model artifacts to the configured artifact
   target.
7. Helm/renderers mount or fetch published schema artifacts according to the
   resolved binding and render Cube env/config from the resolved bindings.
8. Runtime validation queries Cube REST and SQL APIs for product metrics.
9. Observability validation proves semantic sync, Cube service readiness, query
   execution, and product metric evidence are visible in logs, metrics, traces,
   and lineage where supported.

The runtime flow must never feed generated semantic artifact details back into
`CompiledArtifacts`; it emits runtime evidence instead.

## Validation Strategy

### Static And Contract Tests

- Schema tests for semantic datasource/service/model/access policy bindings.
- Resolver tests for compatible and incompatible semantic plugin graphs.
- Secret-free artifact tests for all semantic bindings.
- `CompiledArtifacts` versioning and `deployment.semantic` migration tests.
- Regression tests proving Cube no longer depends on duck-typed compute plugin
  discovery as the primary contract.
- Golden artifact tests for a semantic-enabled data product.
- Negative tests proving semantic runtime evidence is not serialized into
  `CompiledArtifacts`.

### Cube Plugin Tests

- Binding-to-Cube env/config rendering tests.
- Cube datasource env mapping tests for the first supported datasource family,
  including DuckDB database path, S3 endpoint, region, path-style setting,
  extension config, and secret refs.
- Schema generation tests from dbt manifests with measures, dimensions, joins,
  pre-aggregations, and access policies.
- Health check tests.
- API endpoint metadata tests.
- Negative tests for unsupported binding shapes.
- Deny-by-default publication tests proving unannotated and sensitive columns
  are not published.

### Helm And Runtime Tests

- Helm template tests prove Cube values are rendered from bindings.
- Chart tests prove secrets are references or Kubernetes Secret values, never
  compiled raw secrets.
- Kind integration proves Cube pods start, schema artifacts mount, REST health
  passes, and SQL service is exposed when enabled.
- Runtime tests prove both Cube API and refresh worker can access the same
  published model artifacts.
- SQL tests prove SQL wire protocol is enabled only when `CUBEJS_PG_SQL_PORT`
  and SQL credentials are supplied through secret refs.

### E2E And Live Validation

Customer 360 becomes the first proof fixture:

- Run the product pipeline.
- Validate generated semantic schema artifacts for the materialized mart.
- Query the Floe semantic query API, backed by Cube REST, for Customer 360
  metrics.
- Query the Floe semantic SQL API, backed by Cube SQL wire protocol or HTTP SQL,
  for equivalent metrics.
- Confirm the metric values match the current command-based Iceberg proof.
- Confirm evidence matches the exact product, run ID, model/table, metric, and
  freshness window. Stale Cube cache results or another product's schema must
  not satisfy the proof.
- Confirm failure taxonomy separates product failures, semantic service
  failures, datasource binding failures, auth failures, infrastructure
  failures, wrong-context evidence, stale evidence, and contract gaps.
- Run through DevPod+Hetzner before changing the release cutline.

Suggested validator keys:

- `semantic.cube.schema_artifacts.status`
- `semantic.cube.schema_artifacts.count`
- `semantic.cube.rest.status`
- `semantic.cube.rest.customer_count`
- `semantic.cube.rest.total_lifetime_value`
- `semantic.cube.sql.status`
- `semantic.cube.sql.customer_count`
- `semantic.cube.sql.total_lifetime_value`
- `semantic.cube.auth.status`
- `semantic.cube.run_id`
- `semantic.cube.freshness.status`

## Observability Requirements

The semantic path should emit or expose:

- semantic schema generation spans
- Cube readiness checks
- semantic query validation spans
- product name, run ID, model/table, metric, and provider attributes
- Cube service metrics when available through Prometheus-compatible scraping
- clear validator evidence keys for semantic REST and SQL query proof

Dashboards are not the proof. Queryable backend evidence is the proof.

Signal cardinality must follow the existing observability contract. Product,
run ID, model/table, and metric names can appear in traces, logs, lineage, and
validator evidence. Prometheus-compatible metrics must use bounded labels only
and must not add high-cardinality run IDs, table names, or arbitrary metric
names as labels.

## Documentation Updates

Required docs updates after implementation:

- README alpha scope and implemented primitives
- `docs/demo/customer-360-validation.md`
- `docs/demo/customer-360.md`
- `docs/reference/plugin-catalog.md`
- `docs/architecture/interfaces/semantic-layer-plugin.md`
- `docs/architecture/capability-status.md`
- `docs/architecture/adr/0001-cube-semantic-layer.md`
- `docs/architecture/adr/0032-cube-compute-integration.md`
- `docs/contracts/observability-attributes.md`
- `plugins/floe-semantic-cube/README.md`
- `charts/floe-platform/README.md`
- platform engineer guide for enabling semantic layer profiles
- data engineer guide for publishing semantic metrics
- release checklist and package cutline when Cube becomes eligible for alpha

ADR-0032 must be amended or superseded because direct semantic-to-compute
plugin delegation is no longer the target contract.

## Workstream Breakdown

1. Contract and resolver design
   - Add semantic capability and requirement vocabulary.
   - Add `deployment.semantic` binding models and schema/version migration.
   - Add resolver validation for semantic requirements.
   - Define failure codes.

2. Cube binding-aware rendering
   - Add binding-to-Cube config translation.
   - Add Cube REST, SQL wire, HTTP SQL, GraphQL, health, schema path, and auth
     endpoint mapping.
   - Quarantine legacy static Helm override behavior.
   - Remove primary duck-typed compute discovery.

3. Semantic model generation UX
   - Define data engineer semantic publication metadata, preferably
     `meta.floe.semantic`.
   - Define deny-by-default publication and masking rules.
   - Extend schema generation to respect product semantic intent.
   - Preserve dbt as source of truth.

4. Helm/runtime integration
   - Render Cube from semantic bindings.
   - Choose and implement the first artifact transport.
   - Mount generated schemas into API and refresh worker pods.
   - Set provider schema path, such as `CUBEJS_SCHEMA_PATH`.
   - Wire REST, GraphQL, SQL, health, and secrets.

5. Validation and observability
   - Add contract, unit, Helm, integration, and E2E tests.
   - Add Customer 360 semantic proof via Floe semantic APIs backed by Cube REST
     and SQL.
   - Add queryable observability evidence for semantic runs.

6. Docs and release posture
   - Update docs after code evidence exists.
   - Decide whether `floe-semantic-cube` remains excluded, becomes
     experimental, or enters the alpha publish cutline.

7. Semantic API abstraction
   - Define stable Floe semantic API descriptors for consumers.
   - Map Cube endpoints behind the provider adapter.
   - Add compatibility tests proving future semantic providers can expose the
     same Floe API families without changing data-product definitions.

## Out Of Scope

- Cube Cloud.
- Production support guarantees.
- BI-tool-specific onboarding for Tableau, Power BI, Superset, or Metabase.
- Full provider parity for dbt Semantic Layer or other semantic backends.
- Replacing dbt metadata with a separate Floe-only semantic modeling language.
- Hardcoding Customer 360 logic into core semantic contracts.
- Adding raw passwords, tokens, access keys, or API secrets to
  `CompiledArtifacts`.
- Requiring Dagster for semantic publication. Dagster is one implementation
  host, not the semantic lifecycle owner.

## Acceptance Criteria

The design is ready for implementation planning when:

- The first implementation plan can be split into independent worktrees.
- The first worktree can start with semantic binding models and resolver tests.
- The Cube worktree can consume those bindings without touching unrelated
  compute, storage, or catalog plugin internals.
- The validation worktree can define Customer 360 as a fixture without making
  the platform contract Customer 360-specific.

The feature is ready to change release posture only when:

- Cube is configured through composition, not static demo-specific values.
- Floe semantic API proof backed by Cube REST and SQL passes against a
  materialized data product.
- DevPod+Hetzner E2E evidence exists.
- Docs accurately describe the supported semantic path.
- The release manifest package cutline is updated only after the evidence
  supports publishing `floe-semantic-cube`.

Release posture thresholds:

- Excluded: Cube may exist in source, charts, or dev/demo values, but is not
  published as supported and no release promise is made.
- Experimental: Cube may be enabled by documented opt-in profiles and visible
  in demos, but must be labeled non-production and non-release-gating unless
  the semantic E2E gate is explicitly run. Experimental status still requires
  secret-safe configuration and no misleading docs.
- Alpha-published: `release/floe-release.yaml` includes `floe-semantic-cube`
  only after package dry-run, current-main CI, Kind semantic runtime proof,
  DevPod+Hetzner semantic proof, docs updates, and release evidence bundle all
  pass.

## Cube Reference Constraints

These Cube-specific constraints inform the first adapter implementation:

- Cube REST API endpoints are prefixed by `/cubejs-api` by default; `/v1/load`
  executes queries and `/v1/meta` introspects the model.
- Cube uses JWT API tokens in the `Authorization` header outside development
  mode.
- Cube SQL API can use a Postgres-compatible protocol and is disabled by
  default in Cube Core until `CUBEJS_PG_SQL_PORT` is set.
- Cube SQL credentials are configured with `CUBEJS_SQL_USER` and
  `CUBEJS_SQL_PASSWORD`.
- Cube also supports HTTP SQL through `/cubejs-api/v1/cubesql`.
- DuckDB datasource configuration uses environment variables such as
  `CUBEJS_DB_TYPE=duckdb`, `CUBEJS_DB_DUCKDB_DATABASE_PATH`,
  `CUBEJS_DB_DUCKDB_S3_ENDPOINT`, `CUBEJS_DB_DUCKDB_S3_REGION`,
  `CUBEJS_DB_DUCKDB_S3_URL_STYLE`, and secret-backed S3 credential variables.
- Cube loads model files from `CUBEJS_SCHEMA_PATH`, which defaults to `model`
  in current Cube versions.
