# Composable Cube Semantic Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Floe semantic-layer configuration, deployment, validation, and consumption provider-neutral, with Cube as the first concrete backend adapter.

**Architecture:** Land the shared semantic contract foundation first, then split Cube adapter, publication UX, Helm/runtime, validation, and docs/release work into dependent worktrees. `CompiledArtifacts` carries secret-free desired state only; generated schema files, query results, and service health remain runtime evidence outside the compiled contract.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, Helm/chart-testing, Kubernetes/Kind, DevPod + Hetzner, Cube Core, dbt manifest metadata, OpenTelemetry/OpenLineage where existing.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-05-20-composable-cube-semantic-layer-design.md`
- Prior semantic datasource gap spec: `docs/superpowers/specs/2026-05-09-semantic-datasource-binding-design.md`
- Semantic plugin interface docs: `docs/architecture/interfaces/semantic-layer-plugin.md`
- Cube ADR: `docs/architecture/adr/0001-cube-semantic-layer.md`
- Cube/compute ADR to amend or supersede: `docs/architecture/adr/0032-cube-compute-integration.md`
- Current semantic ABC: `packages/floe-core/src/floe_core/plugins/semantic.py`
- Current composition resolver: `packages/floe-core/src/floe_core/composition/resolver.py`
- Current compiled artifact schema: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Current Cube plugin: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- Current Cube schema generator: `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- Current Dagster-hosted semantic sync implementation: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/semantic_sync.py`
- Current chart values: `charts/floe-platform/values.yaml`, `charts/floe-platform/values-test.yaml`, `charts/floe-platform/values-demo.yaml`
- Release package cutline: `release/floe-release.yaml`

## Orchestration Model

This is a global-orchestrated program. The orchestrating session owns:

- creating worktrees only when their dependencies are ready;
- writing root `PROMPT.md` files in those worktrees;
- keeping all `PROMPT.md` files untracked;
- reviewing worker PRs against the design spec and this plan;
- syncing `main` after each merge;
- deleting or stopping completed worktrees only after merge validation;
- running the final Kind and DevPod+Hetzner semantic proof before release-posture changes.

Worker sessions own implementation only inside their assigned worktree. They
must stop and ask before modifying files outside their owned write scope.

## Branch And Worktree Sequence

| Phase | Branch | Worktree | Timing | Dependency |
| --- | --- | --- | --- | --- |
| 1 | `feat/semantic-contracts-foundation` | `.worktrees/semantic-contracts-foundation` | Create now | Current `main` with approved spec and this plan |
| 2A | `feat/semantic-cube-adapter` | `.worktrees/semantic-cube-adapter` | Create after Phase 1 merge | Phase 1 |
| 2B | `feat/semantic-publication-ux` | `.worktrees/semantic-publication-ux` | Create after Phase 1 merge | Phase 1 |
| 3 | `feat/semantic-helm-runtime` | `.worktrees/semantic-helm-runtime` | Create after Phase 2A and 2B merge | Phase 2A, Phase 2B |
| 4 | `feat/semantic-validation-e2e` | `.worktrees/semantic-validation-e2e` | Create after Phase 3 merge | Phase 3 |
| 5 | `docs/semantic-alpha-release-posture` | `.worktrees/semantic-alpha-release-posture` | Create after Phase 4 evidence | Phase 4 |

Do not create Phase 2+ worktrees until the dependencies have merged into
`main`. Their prompts must reference merged contract names, not draft branch
names.

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

## Phase 1: Semantic Contract Foundation

**Branch:** `feat/semantic-contracts-foundation`

**Purpose:** Add provider-neutral semantic capability vocabulary, typed deployment bindings, resolver validation, schema versioning, and contract tests. This phase must not implement Cube rendering or runtime publication.

**Owned files:**

- `packages/floe-core/src/floe_core/composition/models.py`
- `packages/floe-core/src/floe_core/composition/resolver.py`
- `packages/floe-core/src/floe_core/composition/error_codes.py`
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- `packages/floe-core/src/floe_core/schemas/versions.py`
- `packages/floe-core/src/floe_core/plugins/semantic.py`
- `tests/contract/test_composition_capability_contract.py`
- `tests/contract/test_compiled_artifacts_schema.py`
- `tests/contract/test_core_to_semantic_contract.py`
- `tests/contract/test_semantic_layer_abc.py`
- `tests/fixtures/golden/v0.5_compiled_artifacts_with_semantic.json`

**Read-only files unless explicitly approved:**

- `plugins/floe-semantic-cube/**`
- `plugins/floe-orchestrator-dagster/**`
- `charts/floe-platform/**`
- `demo/**`
- `release/floe-release.yaml`

### Task 1: Add Semantic Composition Vocabulary

- [ ] **Step 1: Write failing resolver tests**

  Add tests to `tests/contract/test_composition_capability_contract.py` that
  construct semantic plugin requirements and prove:

  ```python
  PluginRequirements(
      plugin_type="semantic",
      plugin_name="cube",
      requirements=RequirementSet(
          protocols=["s3-compatible"],
          catalog_providers=["polaris"],
          table_formats=["iceberg"],
          semantic_api_families=["metadata", "query", "sql_http"],
          semantic_datasource_engines=["duckdb"],
      ),
  )
  ```

  passes when storage and catalog capabilities satisfy those values, and fails
  when the selected catalog has no compatible table format.

- [ ] **Step 2: Run the failing test**

  ```bash
  uv run pytest tests/contract/test_composition_capability_contract.py -q
  ```

  Expected: failure because `semantic_api_families` and
  `semantic_datasource_engines` are not yet valid `RequirementSet` fields.

- [ ] **Step 3: Add vocabulary to composition models**

  In `packages/floe-core/src/floe_core/composition/models.py`, add these
  provider-neutral fields to both `CapabilitySet` and `RequirementSet`:

  ```python
  semantic_api_families: list[str] = Field(default_factory=list)
  semantic_datasource_engines: list[str] = Field(default_factory=list)
  semantic_artifact_transports: list[str] = Field(default_factory=list)
  ```

  Keep `extra="forbid"` and do not add Cube-specific literals.

- [ ] **Step 4: Add semantic resolver checks**

  In `packages/floe-core/src/floe_core/composition/resolver.py`, route
  `requirement.plugin_type == "semantic"` to a new `_validate_semantic()` helper
  that validates:

  - storage is present when semantic requirements include protocols;
  - catalog is present when semantic requirements include catalog providers or
    table formats;
  - storage protocol compatibility;
  - catalog provider compatibility;
  - table format compatibility.

- [ ] **Step 5: Add failure codes**

  In `packages/floe-core/src/floe_core/composition/error_codes.py`, add stable
  constants:

  ```python
  COMPOSITION_SEMANTIC_STORAGE_MISSING = "COMPOSITION_SEMANTIC_STORAGE_MISSING"
  COMPOSITION_SEMANTIC_CATALOG_MISSING = "COMPOSITION_SEMANTIC_CATALOG_MISSING"
  COMPOSITION_SEMANTIC_PROTOCOL_UNSUPPORTED = "COMPOSITION_SEMANTIC_PROTOCOL_UNSUPPORTED"
  COMPOSITION_SEMANTIC_CATALOG_UNSUPPORTED = "COMPOSITION_SEMANTIC_CATALOG_UNSUPPORTED"
  COMPOSITION_SEMANTIC_TABLE_FORMAT_UNSUPPORTED = "COMPOSITION_SEMANTIC_TABLE_FORMAT_UNSUPPORTED"
  ```

- [ ] **Step 6: Re-run the contract test**

  ```bash
  uv run pytest tests/contract/test_composition_capability_contract.py -q
  ```

  Expected: pass.

### Task 2: Add `deployment.semantic` Desired-State Contract

- [ ] **Step 1: Write failing schema tests**

  Add tests to `tests/contract/test_compiled_artifacts_schema.py` and
  `tests/contract/test_core_to_semantic_contract.py` proving that:

  - `DeploymentConfig.semantic` is optional for backwards compatibility;
  - semantic bindings round-trip through JSON;
  - raw values matching secret keywords are rejected in semantic env/config maps;
  - runtime evidence keys such as `schema_artifacts`, `query_results`, and
    `health_status` are rejected by `DeploymentConfig.semantic`.

- [ ] **Step 2: Run the failing tests**

  ```bash
  uv run pytest tests/contract/test_compiled_artifacts_schema.py tests/contract/test_core_to_semantic_contract.py -q
  ```

  Expected: failure because semantic deployment models do not exist.

- [ ] **Step 3: Add semantic binding models**

  In `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`, add
  frozen `extra="forbid"` models for:

  - `SemanticDatasourceBinding`
  - `SemanticServiceEndpointBinding`
  - `SemanticApiBinding`
  - `SemanticArtifactBinding`
  - `SemanticPublicationBinding`
  - `SemanticAccessPolicyBinding`
  - `SemanticDeploymentBinding`

  These models must carry desired state only. They may contain endpoint URLs,
  driver names, logical API family names, env var names, credential refs,
  artifact mount paths, and publication policies. They must not contain
  generated file lists, query results, health status, raw tokens, raw
  passwords, or raw API secrets.

- [ ] **Step 4: Add `semantic` to deployment config**

  Add this optional field to `DeploymentConfig`:

  ```python
  semantic: SemanticDeploymentBinding | None = None
  ```

  Keep it additive and optional.

- [ ] **Step 5: Bump compiled artifact schema version**

  In `packages/floe-core/src/floe_core/schemas/versions.py`, change
  `COMPILED_ARTIFACTS_VERSION` from `0.16.0` to `0.17.0` and add history:

  ```python
  "0.17.0": "Add semantic deployment binding desired state",
  ```

- [ ] **Step 6: Export models where needed**

  If `packages/floe-core/src/floe_core/schemas/__init__.py` explicitly exports
  compiled-artifact models, add the new semantic binding models there.

- [ ] **Step 7: Re-run schema tests**

  ```bash
  uv run pytest tests/contract/test_compiled_artifacts_schema.py tests/contract/test_core_to_semantic_contract.py -q
  ```

  Expected: pass.

### Task 3: Make Semantic ABC Provider-Neutral

- [ ] **Step 1: Write failing ABC tests**

  Update `tests/contract/test_semantic_layer_abc.py` so the target interface
  includes methods for:

  - declaring composition capabilities;
  - declaring composition requirements;
  - rendering provider runtime config from `SemanticDeploymentBinding`;
  - reporting provider-neutral API endpoint families.

  The test must also assert the ABC docstring no longer says semantic plugins
  delegate connectivity to `ComputePlugin`.

- [ ] **Step 2: Run the failing ABC tests**

  ```bash
  uv run pytest tests/contract/test_semantic_layer_abc.py -q
  ```

  Expected: failure on old `get_datasource_config(compute_plugin)` contract.

- [ ] **Step 3: Update the ABC without breaking existing plugins abruptly**

  In `packages/floe-core/src/floe_core/plugins/semantic.py`:

  - add new abstract or default methods for the provider-neutral contract;
  - mark `get_datasource_config(compute_plugin)` and
    `get_helm_values_override()` as compatibility methods if they cannot be
    removed in this phase;
  - remove statements that make Dagster or concrete compute plugins semantic
    lifecycle owners;
  - document that orchestrator plugins may host semantic publication steps, but
    they do not own semantic contracts.

- [ ] **Step 4: Re-run ABC tests**

  ```bash
  uv run pytest tests/contract/test_semantic_layer_abc.py -q
  ```

  Expected: pass.

### Task 4: Validate And Commit Phase 1

- [ ] **Step 1: Run targeted contract suite**

  ```bash
  uv run pytest tests/contract/test_composition_capability_contract.py tests/contract/test_compiled_artifacts_schema.py tests/contract/test_core_to_semantic_contract.py tests/contract/test_semantic_layer_abc.py -q
  ```

- [ ] **Step 2: Run lint/type checks for touched Python**

  ```bash
  uv run ruff check packages/floe-core/src/floe_core/composition packages/floe-core/src/floe_core/schemas/compiled_artifacts.py packages/floe-core/src/floe_core/plugins/semantic.py tests/contract/test_composition_capability_contract.py tests/contract/test_compiled_artifacts_schema.py tests/contract/test_core_to_semantic_contract.py tests/contract/test_semantic_layer_abc.py
  uv run mypy packages/floe-core/src/floe_core/composition packages/floe-core/src/floe_core/schemas/compiled_artifacts.py packages/floe-core/src/floe_core/plugins/semantic.py
  ```

- [ ] **Step 3: Confirm no runtime evidence entered compiled artifacts**

  ```bash
  rg -n "schema_artifacts|query_results|health_status|generated_files" packages/floe-core/src/floe_core/schemas/compiled_artifacts.py tests/fixtures/golden/v0.5_compiled_artifacts_with_semantic.json
  ```

  Expected: no matches except in negative test names or comments.

- [ ] **Step 4: Commit**

  ```bash
  git add packages/floe-core/src/floe_core/composition packages/floe-core/src/floe_core/schemas packages/floe-core/src/floe_core/plugins/semantic.py tests/contract tests/fixtures/golden/v0.5_compiled_artifacts_with_semantic.json
  git commit -m "feat: add semantic deployment contract foundation"
  ```

## Phase 2A: Cube Adapter

**Branch:** `feat/semantic-cube-adapter`

**Purpose:** Make the Cube plugin consume `SemanticDeploymentBinding` and expose provider-neutral Floe semantic API descriptors backed by Cube endpoints.

**Owned files:**

- `plugins/floe-semantic-cube/src/floe_semantic_cube/config.py`
- `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- `plugins/floe-semantic-cube/src/floe_semantic_cube/errors.py`
- `plugins/floe-semantic-cube/tests/unit/test_config.py`
- `plugins/floe-semantic-cube/tests/unit/test_plugin.py`
- `plugins/floe-semantic-cube/tests/integration/test_health_check.py`
- `plugins/floe-compute-duckdb/tests/unit/test_cube_datasource.py` only to retire or quarantine legacy compatibility expectations

**Read-only files unless explicitly approved:**

- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- `packages/floe-core/src/floe_core/composition/**`
- `charts/floe-platform/**`
- `plugins/floe-orchestrator-dagster/**`

### Required Outcomes

- Add Cube adapter methods that translate `SemanticDeploymentBinding` into
  Cube env/config without taking a live compute plugin.
- Map Floe logical API families to Cube endpoints:
  - metadata -> `/cubejs-api/v1/meta`
  - query -> `/cubejs-api/v1/load`
  - sql_http -> `/cubejs-api/v1/cubesql`
  - sql_wire -> `CUBEJS_PG_SQL_PORT` plus SQL credentials
  - graphql -> `/cubejs-api/graphql`
  - health -> `/readyz` and `/livez`
- Replace `/cubejs-api/sql` assumptions with SQL wire or HTTP SQL mappings.
- Keep legacy `get_datasource_config(compute_plugin)` behind compatibility
  tests only; it must not be the primary implementation path.
- Add unit tests for DuckDB/S3-compatible env mapping, secret refs, health
  endpoints, API family descriptors, and unsupported binding shapes.

### Required Verification

```bash
uv run pytest plugins/floe-semantic-cube/tests/unit plugins/floe-semantic-cube/tests/integration/test_health_check.py -q
uv run pytest tests/contract/test_semantic_layer_abc.py tests/contract/test_core_to_semantic_contract.py -q
uv run ruff check plugins/floe-semantic-cube plugins/floe-compute-duckdb/tests/unit/test_cube_datasource.py
```

## Phase 2B: Semantic Publication UX

**Branch:** `feat/semantic-publication-ux`

**Purpose:** Define data engineer semantic publication metadata and make Cube schema generation deny-by-default.

**Owned files:**

- `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- `plugins/floe-semantic-cube/tests/unit/test_schema_generator.py`
- `testing/fixtures/semantic.py`
- `docs/architecture/interfaces/semantic-layer-plugin.md`

**Read-only files unless explicitly approved:**

- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- `charts/floe-platform/**`
- `plugins/floe-orchestrator-dagster/**`

### Required Outcomes

- Prefer dbt metadata namespace `meta.floe.semantic`.
- Require explicit model publication opt-in.
- Require explicit member publication opt-in for measures, dimensions, time
  dimensions, validation metrics, joins, and pre-aggregations.
- Treat unannotated, PII-like, and masked fields as unpublished by default.
- Preserve dbt as metadata source; do not introduce a separate Cube-first
  modeling language.
- Add tests proving Customer 360 can publish the intended public metrics
  without publishing email or other sensitive dimensions by default.

### Required Verification

```bash
uv run pytest plugins/floe-semantic-cube/tests/unit/test_schema_generator.py -q
uv run ruff check plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py plugins/floe-semantic-cube/tests/unit/test_schema_generator.py testing/fixtures/semantic.py
```

## Phase 3: Helm And Runtime Integration

**Branch:** `feat/semantic-helm-runtime`

**Purpose:** Render Cube runtime from semantic deployment bindings and mount generated provider artifacts into Cube API and refresh worker pods.

**Owned files:**

- `packages/floe-core/src/floe_core/cli/helm/generate.py`
- `charts/floe-platform/values.yaml`
- `charts/floe-platform/values.schema.json`
- `charts/floe-platform/values-test.yaml`
- `charts/floe-platform/templates/**` Cube-related templates only
- `charts/floe-platform/tests/**` Cube-related tests only
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/semantic_sync.py`
- `plugins/floe-orchestrator-dagster/tests/unit/test_semantic_sync_asset.py`
- `plugins/floe-orchestrator-dagster/tests/unit/test_semantic_wiring.py`

**Read-only files unless explicitly approved:**

- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- `release/floe-release.yaml`

### Required Outcomes

- Helm/renderers consume `deployment.semantic`, not semantic plugin config bags.
- Choose first artifact transport for Customer 360 and document limits in chart
  values. ConfigMap is allowed only with explicit size guard and rollout/reload
  behavior.
- Mount generated schema artifacts into both Cube API and refresh worker pods.
- Set `CUBEJS_SCHEMA_PATH` from the semantic artifact binding.
- Render Cube API secret and SQL credentials from Kubernetes Secret refs or
  generated K8s Secret values, never from `CompiledArtifacts` raw secrets.
- Keep semantic publication orchestrator-neutral in contracts. Dagster may host
  the current publication asset but must not become the contract owner.

### Required Verification

```bash
uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_semantic_sync_asset.py plugins/floe-orchestrator-dagster/tests/unit/test_semantic_wiring.py -q
helm unittest charts/floe-platform
uv run pytest tests/contract/test_core_to_semantic_contract.py tests/contract/test_no_hardcoded_credentials.py -q
```

## Phase 4: Semantic Validation And Live Proof

**Branch:** `feat/semantic-validation-e2e`

**Purpose:** Prove Customer 360 semantic APIs against materialized data and queryable observability evidence.

**Owned files:**

- `tests/e2e/test_customer360_observability_gate.py`
- `tests/e2e/test_demo_flow.py`
- `testing/ci/validate_customer_360_demo.py`
- `testing/ci/customer360_observability.py`
- `testing/demo/customer360_validator.py`
- `demo/customer-360/validation.yaml`
- `docs/demo/customer-360-validation.md` validation evidence sections only

**Read-only files unless explicitly approved:**

- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- `charts/floe-platform/**`
- `release/floe-release.yaml`

### Required Outcomes

- Add semantic evidence keys:
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
- Query Floe logical semantic APIs backed by Cube REST and SQL.
- Reject stale evidence, wrong product context, wrong run ID, and service-only
  health without metric proof.
- Separate product failures, semantic service failures, datasource binding
  failures, auth failures, infrastructure failures, wrong-context evidence,
  stale evidence, and contract gaps.
- Run Kind/local validation first, then DevPod+Hetzner.

### Required Verification

```bash
uv run pytest tests/e2e/test_customer360_observability_gate.py tests/e2e/test_demo_flow.py -q
uv run python -m testing.ci.validate_customer_360_demo --help
make demo
```

For DevPod+Hetzner, preserve the generated artifact directory and include the
artifact path, workspace status, and Hetzner machine status in the PR summary.

## Phase 5: Docs And Release Posture

**Branch:** `docs/semantic-alpha-release-posture`

**Purpose:** Update user-facing docs and release metadata after live evidence exists. This phase decides whether Cube remains excluded, becomes experimental, or enters the alpha package cutline.

**Owned files:**

- `README.md`
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
- `release/floe-release.yaml` only if Phase 4 evidence supports alpha-published status

### Required Outcomes

- Describe the provider-neutral Floe semantic API contract before Cube-specific
  endpoint details.
- Mark Cube posture accurately: excluded, experimental, or alpha-published.
- Keep the README alpha disclaimer intact and make Cube status clear.
- Supersede or amend ADR-0032 so direct semantic-to-compute plugin delegation
  is not documented as the target architecture.
- Add manual validation links and queries only after they were live-tested.
- Do not add `floe-semantic-cube` to `release/floe-release.yaml` unless the
  live evidence bundle proves it meets the alpha gate.

### Required Verification

```bash
git diff --check
rg -n "Dagster can generate|/cubejs-api/sql|all columns|production data|floe-semantic-cube" README.md docs plugins/floe-semantic-cube/README.md charts/floe-platform/README.md release/floe-release.yaml
pre-commit run --files README.md docs/demo/customer-360-validation.md docs/demo/customer-360.md docs/reference/plugin-catalog.md docs/architecture/interfaces/semantic-layer-plugin.md docs/architecture/capability-status.md docs/architecture/adr/0001-cube-semantic-layer.md docs/architecture/adr/0032-cube-compute-integration.md docs/contracts/observability-attributes.md plugins/floe-semantic-cube/README.md charts/floe-platform/README.md release/floe-release.yaml
```

## Global Acceptance Gate

The program is complete only when:

- all phase PRs have merged into `main`;
- `CompiledArtifacts` remains secret-free and carries only desired semantic
  state;
- no plugin imports or introspects another plugin's implementation details to
  build semantic datasource config;
- Helm/renderers consume `deployment.semantic`;
- Cube schema artifacts reach the Cube API and refresh worker pods;
- Customer 360 semantic REST and SQL proofs pass against materialized data;
- semantic evidence is queryable in the configured observability backends;
- docs describe the implemented release posture, not an aspirational future;
- DevPod+Hetzner live validation passes or produces clearly classified
  infrastructure failures with follow-up issues.
