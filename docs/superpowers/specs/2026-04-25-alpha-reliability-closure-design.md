# Alpha Reliability Closure Design

Status: Proposed and approved in brainstorming
Date: 2026-04-25
Author: Codex

## Summary

floe's next alpha reliability pass should use the Dagster path collapse as the
central spine. The goal is not another broad architecture reset. The goal is to
prove the core alpha promise through one runtime path:

```text
manifest.yaml + floe.yaml
  -> CompiledArtifacts
  -> Dagster runtime loader
  -> dbt materialization
  -> Iceberg tables
  -> OpenLineage events
  -> Marquez-visible lineage
```

PR #257 made the validation lanes, manifest-driven test config, stale image
handling, and local/CI hook alignment much more trustworthy. The remaining
high-value failures are now product-runtime and platform-readiness issues:

- Dagster still has two integration paths that can diverge.
- Required configured capabilities can still be absent or broken without a
  crisp alpha failure model.
- Iceberg writes are the critical data-path proof and must not silently skip.
- OpenLineage and Marquez are required alpha proof points, not optional polish.
- Post-merge Helm CI showed a live Kind install failure that must be classified
  before closing platform readiness.

## Goals

- Collapse Dagster onto one real runtime path.
- Make configured required capabilities fail loudly.
- Prove YAML-to-Iceberg materialization using manifest-driven config.
- Prove valid OpenLineage lifecycle emission with Marquez as the E2E backend.
- Classify live Helm CI failures as bootstrap, chart readiness, external
  dependency, platform runtime, or transient.
- Keep the scope focused on alpha reliability, not full contract-layer
  generation.

## Non-Goals

- Build the full contract-layer generator before proving alpha.
- Preserve old generated orchestration behavior for compatibility.
- Hide failing E2E tests with skips or broad retries.
- Make Marquez optional for alpha E2E.
- Solve every open tech-debt issue before proving the alpha path.

## Decisions

### 1. Dagster runtime loader is the only real path

`CompiledArtifacts` loaded by the Dagster runtime loader is the canonical path
for building `Definitions`.

`generate_entry_point_code()` must stop generating product-specific executable
orchestration logic. If Dagster packaging still needs a `definitions.py`, it
should be a stable thin shim that delegates to the runtime loader. The shim must
not contain catalog, storage, export, lineage, or dbt orchestration logic.

`create_definitions()` and loader-based code should converge on the same
implementation or one should delegate to the other. There should be one place to
debug resource wiring, dbt assets, Iceberg export, and lineage behavior.

### 2. Configured capabilities are strict

Configured capabilities fail loudly. Explicitly unconfigured optional
capabilities may no-op only when they are not part of the selected alpha proof
profile.

For alpha, the required capabilities are:

- Dagster orchestrator
- dbt execution
- catalog plugin
- storage plugin
- Iceberg write path
- OpenLineage emission
- Marquez E2E validation backend

Failure rules:

- If catalog, storage, dbt, Dagster, or Iceberg is configured but cannot
  initialize, Dagster load or materialization must fail with a clear error.
- If OpenLineage or Marquez is configured and unreachable, invalid, or not
  visible in validation, the relevant materialization or E2E validation must
  fail.
- If lineage is not configured in a non-alpha profile, a no-op lineage resource
  is acceptable only when that absence is explicit.
- A successful dbt run without expected Iceberg tables is a failure.

### 3. Iceberg writes are the critical capability

The first product proof after path collapse is reliable Iceberg table creation
from manifest-driven config. The platform must reject any state where Dagster
reports success but expected Iceberg tables are missing.

The proof should validate:

- catalog and storage settings come from `CompiledArtifacts` and manifest-driven
  config, not hardcoded test constants
- dbt materialization runs through the unified runtime path
- expected namespaces and tables exist after materialization
- reset/idempotency failures are explicit precondition failures, not downstream
  dbt symptoms

### 4. OpenLineage and Marquez are required alpha proof

OpenLineage is required for alpha, and Marquez is required as the E2E proof
backend. The lineage proof can follow the Iceberg write proof, but it is still
blocking for alpha closure.

The proof should validate:

- valid `RunEvent.START` and completion/failure lifecycle events
- stable run identity and parent/child linkage where applicable
- events emitted from the unified Dagster runtime path
- events are visible through Marquez after materialization

### 5. Targeted research only

No broad research phase is needed. Prior audits and validation work already
identify the main shape of the problem.

Research only external behavior that affects implementation choices:

- Helm v4 install, readiness, timeout, and rollback behavior
- Marquez health/readiness endpoints and expected startup behavior
- OpenLineage event semantics and Marquez visibility expectations

## Milestones

### Milestone 1: Classify the live Helm CI failure

Post-merge Helm CI failed in the live Kind integration install step. Helm timed
out waiting for Dagster webserver and daemon readiness while Marquez returned
HTTP 500 on probes during teardown.

Classify this before broad runtime work:

- Helm timeout/resource pressure
- Marquez readiness or dependency failure
- chart dependency/readiness bug
- Dagster readiness bug
- external/transient CI issue

The output should be a short diagnosis with evidence and a decision about
whether the fix belongs in chart readiness, CI timeout/resource tuning, Marquez
configuration, or runtime architecture.

### Milestone 2: Collapse the Dagster path

Replace generated executable orchestration with the runtime loader path.

Acceptance criteria:

- generated `definitions.py`, if present, is a thin stable shim
- direct `create_definitions()` and shim/loader path share one implementation
- tests prove the shim path and direct loader path produce equivalent resource
  and asset wiring
- generated code contains no product-specific catalog/storage/export logic

### Milestone 3: Make resource wiring strict

Codify capability semantics.

Acceptance criteria:

- configured-broken catalog fails loudly
- configured-broken storage fails loudly
- configured-broken dbt fails loudly
- configured-broken lineage/Marquez fails in the alpha profile
- explicitly unconfigured optional lineage can no-op outside the alpha proof
  profile
- error messages identify the missing or broken capability

### Milestone 4: Prove Iceberg writes

Run the demo path through the unified runtime loader until expected Iceberg
tables exist.

Acceptance criteria:

- demo config is pulled from manifests/compiled artifacts
- dbt materialization succeeds through the unified Dagster path
- expected namespaces and Iceberg tables exist
- stale state is reset or rejected before the run
- missing Iceberg output fails validation even if dbt reports success

### Milestone 5: Prove OpenLineage with Marquez

Validate lineage through the same unified runtime path.

Acceptance criteria:

- lifecycle events are valid OpenLineage events
- required start/complete/fail semantics are covered
- Marquez receives and exposes events for the demo run
- failed lineage emission does not masquerade as a successful alpha run

### Milestone 6: Close CI and demo validation

Run the full validation ladder after the unified path, strict resources,
Iceberg proof, and lineage proof are in place.

Acceptance criteria:

- local pre-push remains aligned with CI
- GitHub CI is green or intentionally skipped by lane policy
- Helm CI integration failure is resolved or explicitly classified with a
  tracked follow-up
- DevPod/Hetzner demo validation has evidence
- remaining failures are catalogued by class: bootstrap, platform runtime,
  lineage, chart dependency, external/transient, or non-alpha tech debt

## Guardrails

- No hardcoded demo config. Use manifests, compiled artifacts, or centralized
  helpers.
- No silent fallback across execution contexts.
- No duplicate Dagster path behavior.
- No success state without expected Iceberg tables.
- No alpha success state without Marquez-visible lineage evidence.
- Do not add compatibility shims for unreleased behavior unless Dagster
  discovery requires a stable shim file.
- Keep validation additions lane-aware and local/CI aligned.

## Risks

### Runtime collapse touches broad code

The Dagster plugin currently owns asset construction, resource wiring, code
generation, and runtime loading. Collapsing paths can create broad diffs.

Mitigation: use tests to lock equivalence first, then replace generated logic
with a shim incrementally.

### Helm CI failure may be environment-sensitive

The post-merge failure may involve resource pressure or external image/startup
timing rather than a deterministic chart bug.

Mitigation: classify from logs first, then decide between readiness fix,
timeout/resource tuning, or rerun evidence.

### OpenLineage proof can expose model gaps

Valid lineage may require changes to run identity, parent run semantics, or
Marquez query helpers.

Mitigation: treat lineage as a required product proof after Iceberg writes, not
as a side quest during path collapse.

## Success Definition

Alpha reliability closure is complete when a user can run the demo through the
unified Dagster path and prove:

- the platform loads from `CompiledArtifacts`
- dbt materializes through Dagster
- expected Iceberg tables exist
- valid OpenLineage events are emitted
- Marquez shows the lineage
- CI failures, if any, are classified and not caused by duplicate runtime paths
  or silent resource degradation
