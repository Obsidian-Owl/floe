# Code Complexity Analysis Report: floe Codebase

**Generated:** 2026-05-14
**Commit:** `109ede88` (local `main`; `origin/main` is one commit ahead at `8e9e004` / PR #338, which changes only `pyproject.toml` version bumps — no `.py` source diverges, so these numbers apply to both)
**Tool:** radon 6.0.1 (cyclomatic + raw) + AST-based nesting depth
**Scope:** `packages/` and `plugins/` (production code only — tests excluded)
**Files analysed:** 366 | **SLOC:** 55,415 | **Functions:** 2,459 | **Classes:** 631
**Status:** GOOD — 84.3% of functions are LOW complexity (≤5); the codebase has grown 2.5× since January and complexity has scaled proportionally, but a small cluster of compilation / promotion / governance functions has drifted into critical territory.

## Executive Summary

| Metric | Count | % of total | Status |
|--------|-------|-----------|--------|
| Critical complexity (>20) | 12 | 0.49% | CRITICAL |
| High complexity (15–20) | 28 | 1.14% | HIGH |
| Medium complexity (10–14) | 79 | 3.21% | MEDIUM |
| Deep nesting (>4) | 26 | 1.06% | MEDIUM |
| Long functions (>100 lines) | 76 | 3.09% | HIGH |
| Large classes (>20 methods) | 12 | 1.90% | HIGH |
| Parse errors | 0 | — | OK |

**Trend vs 2026-01-22:** Codebase has 2.5× more functions (982 → 2,459) and 2.2× more classes (282 → 631). Critical count grew 1 → 12; high count grew 7 → 28; long-function count grew 25 → 76. The proportional shift is modest (low-complexity share moved 87.8% → 84.3%) but the absolute concentration of complexity now sits clearly in `floe-core/compilation/`, `floe-core/oci/promotion.py`, and the CLI command surface.

## Critical Issues (Immediate Action)

These functions cross the 20-cyclomatic threshold and combine high length, deep nesting, or both. Every one is a refactor target.

### 1. `_build_storage_deployment_binding()` — Cyclomatic 57 (was untracked)
**File:** [packages/floe-core/src/floe_core/compilation/stages.py:275](packages/floe-core/src/floe_core/compilation/stages.py:275)
**Length:** 632 lines | **Nesting:** 3
**Issue:** A single function compiles every storage-plugin / deployment-target combination in one place. It is by far the largest single function in the codebase and the single biggest contributor to compiler complexity.
**Refactor:** Decompose by storage backend (one function per backend) plus a small dispatcher. Move per-deployment-target branches into the plugin layer where they belong (composition resolver). Effort: 1–2 days; high-leverage because the compiler is the contract producer.

### 2. `compile_pipeline()` — Cyclomatic 42, Nesting 7
**File:** [packages/floe-core/src/floe_core/compilation/stages.py:910](packages/floe-core/src/floe_core/compilation/stages.py:910)
**Length:** 451 lines
**Issue:** The top-level compile orchestration is a 451-line procedural pipeline with seven-deep nesting. It mixes I/O, validation, stage dispatch, and error mapping.
**Refactor:** Extract each compile stage into a strategy object with a uniform `run(context) -> StageResult` interface; the top-level function shrinks to a fold over the stage list. Effort: 1 day.

### 3. `_eval_node()` — Cyclomatic 37, Nesting 16
**File:** [packages/floe-core/src/floe_core/governance/policy_evaluator.py:417](packages/floe-core/src/floe_core/governance/policy_evaluator.py:417)
**Length:** 111 lines
**Issue:** Recursive AST evaluator using a long `if/elif/elif/...` chain on `isinstance(node, ast.X)`. The nesting metric of 16 is an AST artefact of the elif chain — semantically flat dispatch, but every branch is one of the highest-friction places for future maintainers.
**Refactor:** Replace the elif ladder with a dispatch dict `{ast.Constant: _eval_constant, ast.Name: _eval_name, ...}`. Drops complexity to single digits in one PR. Effort: 1–2 hours.

### 4. `execute()` (availability check) — Cyclomatic 28
**File:** [packages/floe-core/src/floe_core/contracts/monitoring/checks/availability.py:71](packages/floe-core/src/floe_core/contracts/monitoring/checks/availability.py:71)
**Length:** 218 lines | **Nesting:** 3
**Refactor:** Split into health-collection, threshold-evaluation, and result-construction phases.

### 5. `generate_command()` (helm) — Cyclomatic 25, Nesting 5
**File:** [packages/floe-core/src/floe_core/cli/helm/generate.py:283](packages/floe-core/src/floe_core/cli/helm/generate.py:283)
**Length:** 128 lines
**Refactor:** Extract per-resource branches into private helpers; CLI commands should stay near 10 cyclomatic.

### 6. `promote_command()` — Cyclomatic 24
**File:** [packages/floe-core/src/floe_core/cli/platform/promote.py:186](packages/floe-core/src/floe_core/cli/platform/promote.py:186) | **Length:** 182
**Refactor:** Push gate-evaluation and rollback-trigger code out of the CLI entry into `PromotionController`.

### 7. `validate_version_change()` — Cyclomatic 24, Nesting 4
**File:** [packages/floe-core/src/floe_core/enforcement/validators/versioning.py:155](packages/floe-core/src/floe_core/enforcement/validators/versioning.py:155) | **Length:** 191
**Refactor:** Group rules by version-bump type (MAJOR/MINOR/PATCH) into separate validators.

### 8. `run()` (DLT plugin) — Cyclomatic 24, Nesting 9
**File:** [plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py:555](plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py:555) | **Length:** 241
**Refactor:** Nine-deep nesting is the deepest in any plugin. Lift retry / dataset-iteration / write-disposition decisions into separate methods; the body should read like a sequence of phase calls.

### 9. `rollback_command()` — Cyclomatic 23
**File:** [packages/floe-core/src/floe_core/cli/platform/rollback.py:203](packages/floe-core/src/floe_core/cli/platform/rollback.py:203) | **Length:** 184
**Refactor:** Mirror the `promote_command` refactor — move logic into `PromotionController.rollback()`.

### 10. `promote()` (OCI controller) — Cyclomatic 22, Nesting 5
**File:** [packages/floe-core/src/floe_core/oci/promotion.py:2044](packages/floe-core/src/floe_core/oci/promotion.py:2044) | **Length:** 280
**Refactor:** Already a method on `PromotionController` (35 methods) — the class is at capacity. Split into a `PromotionPipeline` strategy.

### 11. `deploy_command()` — Cyclomatic 21
**File:** [packages/floe-core/src/floe_core/cli/platform/deploy.py:147](packages/floe-core/src/floe_core/cli/platform/deploy.py:147) | **Length:** 177
**Refactor:** Same pattern as `promote_command` / `rollback_command` — thin the CLI layer.

### 12. `_assert_no_dbt_profile_secret_material()` — Cyclomatic 21, Length 40
**File:** [packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:290](packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:290)
**Refactor:** A short but dense secret-detector. Drive from a table of `(pattern, message)` tuples evaluated by one loop.

**Footprint:** All 12 critical functions live in `packages/floe-core` except `run()` in `floe-ingestion-dlt`. The compiler (`compilation/stages.py`) hosts two of the top three. `floe-core/oci/` and `floe-core/cli/platform/` together hold five more.

## High Complexity Functions (15–20)

| Function | File | CC | Nest | Length | Refactor hint |
|---|---|---|---|---|---|
| `build_runtime_catalog_connection` | [runtime_catalog_connection.py:14](packages/floe-core/src/floe_core/runtime_catalog_connection.py:14) | 20 | 3 | 82 | Backend dispatch table |
| `compile_command` | [cli/platform/compile.py:146](packages/floe-core/src/floe_core/cli/platform/compile.py:146) | 19 | 2 | 154 | Move logic into `Compiler.compile_with_options()` |
| `validate_command` (network) | [cli/network/validate.py:227](packages/floe-core/src/floe_core/cli/network/validate.py:227) | 19 | 4 | 94 | Extract per-policy validators |
| `run_validation_with_timeout` | [plugins/floe-quality-gx/.../executor.py:141](plugins/floe-quality-gx/src/floe_quality_gx/executor.py:141) | 19 | 4 | 135 | Split timeout, retry, and result-mapping |
| `__getattr__` (rbac) | [rbac/__init__.py:44](packages/floe-core/src/floe_core/rbac/__init__.py:44) | 18 | 1 | 75 | Dispatch dict (same recommendation as Jan) |
| `validate_command` (rbac) | [cli/rbac/validate.py:90](packages/floe-core/src/floe_core/cli/rbac/validate.py:90) | 18 | 4 | 132 | Extract role/permission/policy validators |
| `generate_command` (network) | [cli/network/generate.py:87](packages/floe-core/src/floe_core/cli/network/generate.py:87) | 18 | 3 | 129 | Mirror `cli/helm/generate` split |
| `_validate_identity` | [composition/resolver.py:325](packages/floe-core/src/floe_core/composition/resolver.py:325) | 18 | 2 | 99 | Extract per-claim validators |
| `run_enforce_stage` | [compilation/stages.py:1363](packages/floe-core/src/floe_core/compilation/stages.py:1363) | 18 | 3 | 158 | Part of the compile-stage refactor |
| `calculate_compliance` | [contracts/monitoring/sla.py:268](packages/floe-core/src/floe_core/contracts/monitoring/sla.py:268) | 17 | 1 | 108 | Per-SLO scoring functions |
| `_run_all_gates` | [oci/promotion.py:991](packages/floe-core/src/floe_core/oci/promotion.py:991) | 17 | 4 | 158 | Gate iterator + reducer |
| `_format_status_table` | [cli/platform/status.py:38](packages/floe-core/src/floe_core/cli/platform/status.py:38) | 17 | 3 | 64 | Move column formatters into Status model |
| `_analyze_files_for_compaction` | [floe-iceberg/.../compaction.py:174](packages/floe-iceberg/src/floe_iceberg/compaction.py:174) | 17 | 7 | 80 | Same item still open from Jan report |
| `_resolve_duckdb_path_from_profiles` | [.../export/iceberg.py:58](plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py:58) | 17 | 2 | 68 | Replace nested try/except with explicit precedence list |
| `route` | [contracts/monitoring/alert_router.py:64](packages/floe-core/src/floe_core/contracts/monitoring/alert_router.py:64) | 16 | 3 | 90 | Channel dispatch table |
| `parse_trivy_output` | [oci/security_gate.py:74](packages/floe-core/src/floe_core/oci/security_gate.py:74) | 16 | 6 | 130 | Stream parser + record builder |
| `validate_mode_sources` | [schemas/compiled_artifacts.py:746](packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:746) | 16 | 2 | 30 | High CC in 30 lines — short but dense; split by mode |
| `detect_circular_deps` | [enforcement/validators/semantic.py:175](packages/floe-core/src/floe_core/enforcement/validators/semantic.py:175) | 16 | 3 | 65 | Topological-sort-based detector is simpler than ad-hoc DFS |
| `execute` (schema_drift) | [.../monitoring/checks/schema_drift.py:52](packages/floe-core/src/floe_core/contracts/monitoring/checks/schema_drift.py:52) | 15 | 3 | 197 | Same pattern as availability/quality checks |
| `status_command` | [cli/platform/status.py:204](packages/floe-core/src/floe_core/cli/platform/status.py:204) | 15 | 3 | 130 | Move presentation logic out of CLI |
| `_detect_cni` | [cli/network/check_cni.py:138](packages/floe-core/src/floe_core/cli/network/check_cni.py:138) | 15 | 3 | 78 | CNI detector dict |
| `sbom_command` | [cli/artifact/sbom.py:124](packages/floe-core/src/floe_core/cli/artifact/sbom.py:124) | 15 | 5 | 49 | Five-deep nesting in 49 lines |
| `_print_formatted` | [cli/artifact/inspect.py:202](packages/floe-core/src/floe_core/cli/artifact/inspect.py:202) | 15 | 5 | 53 | Same — flatten via early returns |
| `validate` (composition) | [composition/resolver.py:27](packages/floe-core/src/floe_core/composition/resolver.py:27) | 15 | 2 | 48 | Split happy-path from constraint checks |
| `run_checks` | [governance/integrator.py:60](packages/floe-core/src/floe_core/governance/integrator.py:60) | 15 | 1 | 90 | Check registry + iteration |
| `run_dbt_tests_with_timeout` | [plugins/floe-quality-dbt/.../executor.py:130](plugins/floe-quality-dbt/src/floe_quality_dbt/executor.py:130) | 15 | 3 | 156 | Mirror gx executor refactor |
| `generate_dbt_profile` | [plugins/floe-compute-duckdb/.../plugin.py:398](plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py:398) | 15 | 6 | 123 | Build profile dict via per-section builders |
| `export_dbt_to_iceberg` | [.../export/iceberg.py:145](plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py:145) | 15 | 3 | 123 | Split discovery, transform, and write phases |

**Concentration:** 34 of the 40 high+critical functions live in `packages/`; 6 in plugins. The compiler (`floe-core/compilation/stages.py`), the promotion controller (`floe-core/oci/promotion.py`), the CLI command surface (`floe-core/cli/platform/`), and the monitoring checks (`floe-core/contracts/monitoring/`) account for the majority.

## Cyclomatic Complexity Distribution

| Bucket | Count | % | Δ vs 2026-01-22 |
|---|---|---|---|
| 1–5 (Low) | 2,073 | 84.3% | 87.8% → 84.3% (-3.5 pts) |
| 6–10 (Medium) | 292 | 11.9% | 10.0% → 11.9% (+1.9 pts) |
| 11–20 (High) | 82 | 3.3% | 2.1% → 3.3% (+1.2 pts) |
| 21+ (Critical) | 12 | 0.49% | 0.1% → 0.49% (+0.4 pts) |

**Read:** The shape is still healthy — five out of every six functions are trivial — but the slope has moved the wrong way at every bucket. Most of the drift is in the upper-middle band (6–10), which is the leading indicator: those functions will roll into the high bucket if they keep accreting branches.

## Top 10 Classes by Method Count

| Class | Methods | File | Note |
|---|---|---|---|
| `OCIClient` | 51 | [floe-core/oci/client.py:107](packages/floe-core/src/floe_core/oci/client.py:107) | Up from 27 in Jan; needs splitting (pull / push / verify / cache / auth) |
| `PromotionController` | 35 | [floe-core/oci/promotion.py:137](packages/floe-core/src/floe_core/oci/promotion.py:137) | New entry; hosts `promote()` cc=22 and `_run_all_gates` cc=17 |
| `DltIngestionPlugin` | 33 | [floe-ingestion-dlt/.../plugin.py:90](plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py:90) | Plugin facade — hosts the deepest-nested function in the repo |
| `PolarisCatalogPlugin` | 27 | [floe-catalog-polaris/.../plugin.py:70](plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py:70) | Plugin facade |
| `K8sNetworkSecurityPlugin` | 27 | [floe-network-security-k8s/.../plugin.py:26](plugins/floe-network-security-k8s/src/floe_network_security_k8s/plugin.py:26) | Plugin facade |
| `PolicyEnforcer` | 26 | [floe-core/enforcement/policy_enforcer.py:42](packages/floe-core/src/floe_core/enforcement/policy_enforcer.py:42) | 20 → 26 since Jan |
| `InfisicalSecretsPlugin` | 26 | [floe-secrets-infisical/.../plugin.py:99](plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py:99) | Plugin facade |
| `DagsterOrchestratorPlugin` | 25 | [floe-orchestrator-dagster/.../plugin.py:80](plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:80) | Plugin facade |
| `IcebergTableManager` | 24 | [floe-iceberg/.../manager.py:67](packages/floe-iceberg/src/floe_iceberg/manager.py:67) | Stable since Jan (23 → 24) |
| `KeycloakIdentityPlugin` | 24 | [floe-identity-keycloak/.../plugin.py:38](plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py:38) | 22 → 24 |

**Observation:** Six of the top ten are plugin facades — that pattern is structural (each plugin implements a defined ABC) and largely unavoidable. The non-plugin entries (`OCIClient`, `PromotionController`, `PolicyEnforcer`, `IcebergTableManager`) are the real candidates for splitting. `OCIClient` at 51 methods is the most urgent.

## Nesting Depth Outliers (>4 levels)

26 functions exceed depth 4 (1.06% of all functions). Top offenders:

| Function | Depth | CC | Length | Location |
|---|---|---|---|---|
| `_eval_node` | 16 | 37 | 111 | [governance/policy_evaluator.py:417](packages/floe-core/src/floe_core/governance/policy_evaluator.py:417) — AST-artefact (elif chain), fix with dispatch dict |
| `run` (DLT plugin) | 9 | 24 | 241 | [floe-ingestion-dlt/.../plugin.py:555](plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py:555) — genuine nesting; phase extraction needed |
| `_apply_real_schema_changes` | 8 | 14 | 42 | [floe-iceberg/.../_schema_manager.py:197](packages/floe-iceberg/src/floe_iceberg/_schema_manager.py:197) — short but 8-deep; cleanest near-term refactor |
| `compile_pipeline` | 7 | 42 | 451 | [compilation/stages.py:910](packages/floe-core/src/floe_core/compilation/stages.py:910) |
| `_analyze_files_for_compaction` | 7 | 17 | 80 | [floe-iceberg/.../compaction.py:174](packages/floe-iceberg/src/floe_iceberg/compaction.py:174) — still open from Jan |
| `get_status` | 6 | 13 | 125 | [oci/promotion.py:2695](packages/floe-core/src/floe_core/oci/promotion.py:2695) |
| `notify` | 6 | 13 | 171 | [oci/webhooks.py:182](packages/floe-core/src/floe_core/oci/webhooks.py:182) |
| `parse_trivy_output` | 6 | 16 | 130 | [oci/security_gate.py:74](packages/floe-core/src/floe_core/oci/security_gate.py:74) |
| `generate_dbt_profile` | 6 | 15 | 123 | [floe-compute-duckdb/.../plugin.py:398](plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py:398) |

The remaining 17 are at depth 5 — mostly CLI commands and parsers. Extracting inner loops into helpers reliably brings them down a level.

## Long Functions (>100 lines)

76 functions exceed 100 lines (up from 25 in January). The top concentration is the same compiler + promotion + monitoring cluster identified in the cyclomatic analysis — every critical-CC function above 200 lines is also a length outlier. The five longest:

1. `_build_storage_deployment_binding` — 632 lines ([compilation/stages.py:275](packages/floe-core/src/floe_core/compilation/stages.py:275))
2. `compile_pipeline` — 451 lines ([compilation/stages.py:910](packages/floe-core/src/floe_core/compilation/stages.py:910))
3. `promote` — 280 lines ([oci/promotion.py:2044](packages/floe-core/src/floe_core/oci/promotion.py:2044))
4. `run` (DLT) — 241 lines ([floe-ingestion-dlt/.../plugin.py:555](plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py:555))
5. `execute` (availability) — 218 lines ([contracts/monitoring/checks/availability.py:71](packages/floe-core/src/floe_core/contracts/monitoring/checks/availability.py:71))

Several long functions are intentional template/payload builders with low cyclomatic (e.g., `rollback` at 147 lines / cc=5, `_run_security_gate` at 181 lines / cc=10). Those are acceptable as-is; the report flags them but they should not block work.

## Action Plan

### Priority 1 — Before next minor release (the bleeding edge)

- [ ] **Decompose `_build_storage_deployment_binding`** in [compilation/stages.py:275](packages/floe-core/src/floe_core/compilation/stages.py:275) — 632 lines / cc=57 single-handedly distorts compiler quality metrics.
- [ ] **Refactor `compile_pipeline`** in [compilation/stages.py:910](packages/floe-core/src/floe_core/compilation/stages.py:910) into stage-strategy form; this is the public compiler entry point.
- [ ] **Replace `_eval_node` elif chain** in [governance/policy_evaluator.py:417](packages/floe-core/src/floe_core/governance/policy_evaluator.py:417) with a dispatch dict — 1–2 hours, large readability win.
- [ ] **Thin `promote_command` / `rollback_command` / `deploy_command`** (CLI layer) by moving logic into `PromotionController` / `DeploymentController`.

### Priority 2 — This quarter

- [ ] **Split `OCIClient`** (51 methods) by responsibility (pull / push / verify / cache / auth).
- [ ] **Split `PromotionController`** (35 methods) — its `promote()` method is already cc=22 and the class will keep growing as gates are added.
- [ ] **Carry the January punch-list forward** that is still open: `_analyze_files_for_compaction` (depth 7, [floe-iceberg/.../compaction.py:174](packages/floe-iceberg/src/floe_iceberg/compaction.py:174)) and `__getattr__` in [rbac/__init__.py:44](packages/floe-core/src/floe_core/rbac/__init__.py:44).
- [ ] **Unify the monitoring `execute()` checks** ([availability.py:71](packages/floe-core/src/floe_core/contracts/monitoring/checks/availability.py:71), [schema_drift.py:52](packages/floe-core/src/floe_core/contracts/monitoring/checks/schema_drift.py:52), [quality.py:93](packages/floe-core/src/floe_core/contracts/monitoring/checks/quality.py:93)) on a shared phase template; each is independently 169–218 lines.

### Priority 3 — Background hygiene

- [ ] **Plug a CC ceiling into `/sw-verify`** (e.g., fail on cc > 20 for changed files) to prevent fresh critical entries.
- [ ] **Review the 76 long functions** by category — many CLI commands are long because their option matrix is wide; consider a CLI option-table pattern.
- [ ] **Audit deep-nesting depth-5 functions** (17 left after fixing depth-6+) opportunistically as they get touched.

## Quality Assessment

**Overall grade: GOOD (B)**

The floe codebase has tripled in production code since January 22 while preserving a healthy complexity profile — 84.3% of 2,459 functions remain at low cyclomatic complexity, parse cleanly with no errors, and the nesting / class-size outliers are concentrated in a small, well-known set of files rather than scattered. The structural pattern is sound: plugin facades dominate the large-class list (a deliberate architectural choice tied to the 15 plugin ABCs), and tests are not contributing noise because they are excluded from the analysis. The weak spots are concrete: `compilation/stages.py` hosts the two longest and most complex functions in the repo and is the public compiler contract surface, `oci/promotion.py` has a controller class that has outgrown its method limit, and the `cli/platform/` commands have absorbed business logic that belongs in the controller layer. Twelve critical-complexity functions is a noticeable jump from one, but every entry is a recognizable refactor target with a clear path; none represent architectural mistakes, only growth that hasn't been groomed yet. The codebase remains maintainable, and the action plan above is deliberately small and high-leverage — fixing the top three Priority-1 items would move the critical count from 12 back into the low single digits in roughly a week of focused work.

---

**Headline numbers for blog/release notes:**

- 2,459 functions, 631 classes, 55,415 SLOC across 366 production files
- 84.3% of functions at low complexity (CC ≤ 5)
- 12 critical-complexity functions (CC > 20), 28 high (15–20), 79 medium (10–14)
- 26 functions with nesting depth > 4; 76 functions over 100 lines; 12 classes with > 20 methods
- Codebase has grown 2.5× in function count since 2026-01-22 while holding the low-complexity share within four percentage points
