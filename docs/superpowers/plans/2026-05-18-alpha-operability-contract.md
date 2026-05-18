# Alpha Operability Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Customer 360 prove a truthful alpha operability baseline across run control, traces, logs, metrics, lineage, storage, and curated dashboards.

**Architecture:** Implement this as a phased, multi-worktree program. Land the shared contract foundation first, then run validator, Grafana/Prometheus, and Marquez-depth workstreams in parallel against that merged foundation. Runtime telemetry expansion follows evidence from the validator and dashboard work.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, Click/CLI helpers where existing, Kubernetes/Helm, DevPod + Hetzner, OpenTelemetry, OpenLineage, Marquez API, Loki API, Prometheus API, Grafana API.

---

## Source Documents

- Spec: `docs/superpowers/specs/2026-05-18-alpha-operability-contract-design.md`
- Existing observability design: `docs/superpowers/specs/2026-05-17-platform-observability-defaults-design.md`
- Existing observability contract: `docs/contracts/observability-attributes.md`
- Customer 360 validation docs: `docs/demo/customer-360-validation.md`
- Customer 360 validation manifest: `demo/customer-360/validation.yaml`

## Orchestration Model

This is a global-orchestrated program. The orchestrating session owns:

- creating worktrees at the correct time;
- writing root `PROMPT.md` files in those worktrees;
- keeping `PROMPT.md` files untracked;
- monitoring worker PRs and CI;
- syncing trunk after merges;
- deleting or stopping completed worktrees only after merge validation;
- validating the final live DevPod/Hetzner proof.

Worker sessions own implementation only inside their assigned worktree and must
not modify files outside their declared write scope unless they stop and ask.

## Branch And Worktree Sequence

| Phase | Branch | Worktree | Timing | Dependency |
| --- | --- | --- | --- | --- |
| 1 | `feat/alpha-operability-contract-foundation` | `.worktrees/alpha-operability-contract-foundation` | Create now | Current `main` with this plan |
| 2A | `feat/alpha-operability-validator` | `.worktrees/alpha-operability-validator` | Create after Phase 1 merge | Phase 1 |
| 2B | `feat/alpha-operability-grafana-prometheus` | `.worktrees/alpha-operability-grafana-prometheus` | Create after Phase 1 merge | Phase 1 |
| 2C | `feat/alpha-operability-marquez-depth` | `.worktrees/alpha-operability-marquez-depth` | Create after Phase 1 merge | Phase 1 |
| 3 | `feat/alpha-operability-runtime-telemetry` | `.worktrees/alpha-operability-runtime-telemetry` | Create after Phase 2 evidence | Phase 2A/2B/2C |
| 4 | `feat/alpha-operability-release-gates` | `.worktrees/alpha-operability-release-gates` | Create after Phase 3 merge | Phase 3 |

Do not create Phase 2 worktrees until Phase 1 has merged into `main`. Their
prompts must reference the merged contract names, not the draft branch.

## Root PROMPT.md Rules

Each worktree gets a root `PROMPT.md` created by the orchestrating session.
`PROMPT.md` is a local session trigger and must not be committed.

Every prompt must include:

- branch and worktree path;
- source spec and plan paths;
- owned files;
- read-only files;
- explicit out-of-scope list;
- required skill invocation;
- acceptance tests;
- PR expectations;
- instruction to leave `PROMPT.md` untracked.

Before accepting any worker PR, the orchestrating session must check:

```bash
git status --short
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD
```

The output must not include `PROMPT.md`.

## Phase 1: Contract Foundation

**Branch:** `feat/alpha-operability-contract-foundation`

**Purpose:** Land the shared evidence vocabulary, docs, and manual inspection truth table that all later workstreams depend on.

**Owned files:**

- `docs/contracts/observability-attributes.md`
- `docs/demo/customer-360-validation.md`
- `docs/platform-engineers/validate-platform.md`
- `demo/customer-360/validation.yaml`
- `testing/ci/tests/` only if docs/manifest behavior needs test coverage

**Read-only files unless explicitly approved:**

- `testing/ci/validate_customer_360_demo.py`
- `testing/ci/customer360_observability.py`
- `testing/demo/customer360_validator.py`
- `charts/floe-platform/**`
- runtime plugin code under `packages/` and `plugins/`

### Task 1: Document UI/API Truth

- [ ] **Step 1: Update backend surface table**

  Modify `docs/demo/customer-360-validation.md` so the manual inspection section explicitly classifies Dagster, MinIO, Marquez, Loki, Prometheus, Grafana, Jaeger, Polaris, and Cube as UI, API-only, or optional.

- [ ] **Step 2: Add exact Marquez and Loki curl examples**

  Include these API examples with placeholders for run ID where needed:

  ```bash
  curl -fsS http://localhost:5100/api/v1/namespaces/customer-360/jobs | jq .
  curl -fsS http://localhost:5100/api/v1/namespaces/customer-360/jobs/customer-360/runs | jq .
  curl -fsS http://localhost:5100/api/v1/namespaces/customer-360/datasets | jq .
  curl -fsS 'http://localhost:5100/api/v1/lineage?nodeId=dataset:customer-360:customer_360.main.mart_customer_360&depth=3' | jq .
  curl -fsS http://localhost:3101/ready
  ```

- [ ] **Step 3: Verify docs use current endpoint truth**

  Run:

  ```bash
  rg -n "Marquez|Loki|Grafana|Prometheus|Cube|Polaris" docs/demo/customer-360-validation.md docs/platform-engineers/validate-platform.md docs/contracts/observability-attributes.md
  ```

  Expected: no statement says Marquez or Loki root URLs are UI surfaces.

### Task 2: Define Evidence Key Vocabulary

- [ ] **Step 1: Extend the observability contract docs**

  In `docs/contracts/observability-attributes.md`, add a section named
  `Alpha Operability Evidence Keys` with the required key families:

  ```text
  run_control.*
  storage.*
  business.*
  observability.traces.*
  observability.logs.*
  observability.metrics.*
  observability.lineage.*
  observability.grafana.*
  ```

- [ ] **Step 2: Define failure classes**

  In the same section, document these failure classes:

  ```text
  product_failure
  platform_service_failure
  backend_unreachable
  no_fresh_evidence
  wrong_context
  stale_evidence
  dashboard_datasource_drift
  contract_gap
  ```

- [ ] **Step 3: Keep existing validator output compatible**

  State that existing `evidence.*` keys remain compatible during alpha, while
  new validators should classify failures using the expanded classes.

### Task 3: Align Validation Manifest Wording

- [ ] **Step 1: Review `demo/customer-360/validation.yaml`**

  Confirm the manifest still documents current default namespace assumptions.
  If changes are needed, only edit comments or explicit validation metadata.
  Do not change runtime commands in Phase 1 unless a doc test proves they are
  stale.

- [ ] **Step 2: Add namespace override note**

  In `docs/demo/customer-360-validation.md`, document that DevPod/Flux
  environments may deploy to `floe-test`, so operators should pass:

  ```bash
  FLOE_DEMO_NAMESPACE=floe-test
  ```

  and override storage/business commands when those commands embed a namespace.

### Task 4: Validate Phase 1

- [ ] **Step 1: Run targeted docs checks**

  ```bash
  git diff --check
  rg -n "TBD|TODO|FIXME" docs/contracts/observability-attributes.md docs/demo/customer-360-validation.md docs/platform-engineers/validate-platform.md
  ```

  Expected: `git diff --check` passes; `rg` returns no unresolved placeholders.

- [ ] **Step 2: Run relevant tests if changed**

  If only markdown changed:

  ```bash
  pre-commit run --files docs/contracts/observability-attributes.md docs/demo/customer-360-validation.md docs/platform-engineers/validate-platform.md
  ```

  If `demo/customer-360/validation.yaml` changed:

  ```bash
  uv run python -m testing.ci.validate_customer_360_demo --help
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add docs/contracts/observability-attributes.md docs/demo/customer-360-validation.md docs/platform-engineers/validate-platform.md demo/customer-360/validation.yaml
  git commit -m "docs: define alpha operability evidence"
  ```

## Phase 2A: Validation Harness

**Branch:** `feat/alpha-operability-validator`

**Create after Phase 1 merge.**

**Purpose:** Expand automated Customer 360 validation so it proves operability depth, not just shallow backend reachability.

**Owned files:**

- `testing/ci/validate_customer_360_demo.py`
- `testing/ci/customer360_observability.py`
- `testing/demo/customer360_validator.py`
- `testing/ci/tests/test_*customer360*`
- `testing/demo/tests/` if existing patterns require it

**Read-only files unless approved:**

- `charts/floe-platform/**`
- Grafana dashboard JSON/templates
- runtime plugin emitters

### Task 1: Add Evidence Classifiers

- [ ] Add or extend tests for failure classes:

  ```bash
  uv run pytest testing/ci/tests -q -k "customer360 or observability"
  ```

- [ ] Implement deterministic classifier output for backend unreachable,
  no fresh evidence, wrong context, stale evidence, dashboard datasource drift,
  product failure, platform service failure, and contract gap.

- [ ] Preserve existing successful `status=PASS` output.

### Task 2: Add Backend Query Helpers

- [ ] Add tests for Marquez jobs, runs, datasets, and graph node ID helpers.
- [ ] Add tests for Loki `/ready` and `query_range` helpers.
- [ ] Add tests for Prometheus instant and range query behavior.
- [ ] Add tests for Grafana datasource and panel query extraction.

### Task 3: Add Contract Evidence Output

- [ ] Add evidence keys for run control, trace depth, log depth, metric family
  availability, lineage graph/facets, and Grafana validation when configured.
- [ ] Keep old evidence keys during alpha compatibility.

### Task 4: Validate Phase 2A

- [ ] Run:

  ```bash
  uv run pytest testing/ci/tests -q -k "customer360 or observability"
  uv run python -m testing.ci.validate_customer_360_demo --help
  ```

- [ ] If live DevPod is available, run a live validation against the current
  demo environment and attach evidence to the PR.

## Phase 2B: Prometheus And Grafana Alignment

**Branch:** `feat/alpha-operability-grafana-prometheus`

**Create after Phase 1 merge.**

**Purpose:** Make Grafana truthful by aligning datasources and dashboards with emitted alpha metrics.

**Owned files:**

- `charts/floe-platform/templates/*prometheus*`
- `charts/floe-platform/templates/*grafana*`
- `charts/floe-platform/templates/configmap-*dashboard*`
- `charts/floe-platform/values.yaml`
- chart tests under `tests/`, `testing/`, or `charts/` matching existing patterns

**Read-only files unless approved:**

- runtime plugin emitters
- Customer 360 validator internals, except documented integration points from
  Phase 2A if already merged

### Task 1: Inventory Dashboard Queries

- [ ] Extract dashboard panel queries through rendered templates or Grafana API.
- [ ] Classify each query as backed by emitted metric, intentionally hidden,
  unknown metric, wrong datasource, or invalid query.

### Task 2: Fix Datasource Strategy

- [ ] Prefer making monitoring Prometheus scrape Floe OTel metrics.
- [ ] If that is not feasible in one slice, provision explicit datasources and
  assign Floe dashboards to the datasource with Floe metrics.

### Task 3: Curate Dashboards

- [ ] Remove, hide, or rewrite panels for unimplemented metrics.
- [ ] Keep only panels backed by current contract metrics, or mark them as
  intentionally empty with clear panel text.

### Task 4: Validate Phase 2B

- [ ] Run Helm/chart rendering checks.
- [ ] Run any dashboard provisioning tests.
- [ ] In live DevPod, verify Grafana API reports datasources and dashboard
  panel queries that return data in the proof window.

## Phase 2C: Marquez Lineage Depth

**Branch:** `feat/alpha-operability-marquez-depth`

**Create after Phase 1 merge.**

**Purpose:** Make lineage validation prove graph and facet depth.

**Owned files:**

- `testing/ci/customer360_observability.py`
- `testing/ci/tests/test_*lineage*`
- `docs/demo/customer-360-validation.md`
- Marquez helper docs under `docs/` if needed

**Read-only files unless approved:**

- chart Marquez deployment templates
- runtime OpenLineage emitter code

### Task 1: Add Marquez Depth Tests

- [ ] Test node ID construction for product job, model job, and mart dataset.
- [ ] Test dataset facet extraction for schema and column lineage.
- [ ] Test parent-run facet assertion for model/table jobs.

### Task 2: Add Live Query Assertions

- [ ] Validate product run state.
- [ ] Validate model/table jobs and inputs/outputs.
- [ ] Validate mart dataset schema fields.
- [ ] Validate mart column lineage has upstream fields for expected columns.
- [ ] Validate trace-correlation facet exists where available.

### Task 3: Validate Phase 2C

- [ ] Run targeted tests.
- [ ] If live DevPod is available, run Marquez API checks against the current
  Customer 360 run and include summarized evidence in the PR.

## Phase 3: Runtime Telemetry Gap Closure

**Branch:** `feat/alpha-operability-runtime-telemetry`

**Create after Phase 2 evidence identifies exact gaps.**

**Purpose:** Add missing runtime metrics and spans only where the contract and validators prove a gap.

**Expected owned files:**

- `packages/floe-core/src/floe_core/telemetry/**`
- `plugins/floe-orchestrator-dagster/src/**`
- `plugins/floe-dbt-core/src/**`
- `plugins/floe-ingestion-dlt/src/**`
- `packages/floe-iceberg/src/**`
- matching unit and integration tests

Do not start this branch until Phase 2 has concrete failing evidence. This
prevents speculative metric work.

## Phase 4: Release Gate Integration

**Branch:** `feat/alpha-operability-release-gates`

**Create after Phase 3 merge.**

**Purpose:** Wire the expanded live operability validator into release and weekly validation lanes without adding long E2E checks to every PR.

**Owned files:**

- `.github/workflows/**`
- `scripts/**` release/live validation helpers
- `docs/demo/customer-360-validation.md`
- `docs/platform-engineers/validate-platform.md`

**Acceptance requirements:**

- PR CI does not run long live E2E validation by default.
- Release-tag validation runs the expanded operability gate before GitHub
  Release creation.
- Weekly validation runs the expanded gate.
- Failures create or update GitHub issues with logs and evidence.
- No GitHub Release is created until all release gates pass.

## Global Quality Gates

Every worker PR must provide:

- summary of changed files;
- tests run with command output summary;
- explicit skipped tests and reason;
- live validation evidence if the slice touches live backend behavior;
- confirmation that `PROMPT.md` is untracked and not in the PR.

The orchestrating session must not accept a PR as complete until:

```bash
gh pr checks <number> --watch
gh pr view <number> --comments
git fetch origin
git status --short --branch
```

After merge, the orchestrating session must:

```bash
git checkout main
git pull --ff-only origin main
git worktree list
git branch --merged main
```

Then decide whether to create the next dependent worktree.

## First Worktree Prompt

Create `.worktrees/alpha-operability-contract-foundation/PROMPT.md` with the
Phase 1 scope above. The prompt must tell the worker:

- use `superpowers:subagent-driven-development`;
- start from the root `PROMPT.md`;
- do not commit `PROMPT.md`;
- do not implement runtime telemetry, chart changes, or validator internals;
- keep the branch docs/manifest-focused;
- open a PR when done.

## Future Worktree Prompt Timing

Do not create future prompts now. Generate each prompt immediately before the
worker session starts so it can include:

- the latest merged `main` SHA;
- the exact predecessor PRs;
- any live validation evidence from earlier phases;
- updated file ownership based on what actually merged.
