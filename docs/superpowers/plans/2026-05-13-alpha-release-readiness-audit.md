# Alpha Release Readiness Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an evidence-backed alpha release readiness report that defines the package cutline and identifies release blockers before any alpha tag is created.

**Architecture:** This is an audit/reporting plan, not a release-fix plan. The implementation gathers evidence from current `main`, recent post-composition PR history, workflows, package metadata, tests, and live validation artifacts, then writes a single report under `docs/analysis/`. Release workflow or package-list changes are captured as blockers/follow-ups, not silently implemented during the audit.

**Tech Stack:** Git, GitHub CLI, Markdown, Python/pytest metadata inspection, existing Makefile targets, DevPod + Hetzner validation, AWS provider live-test scripts.

---

## File Structure

- Create: `docs/analysis/2026-05-13-alpha-release-readiness-report.md`
  - Owns the final audit output: current state, package cutline, evidence ledger, workflow gaps, blockers, and go/no-go recommendation.
- Read: `docs/superpowers/specs/2026-05-13-alpha-release-readiness-audit-design.md`
  - Source design and acceptance criteria.
- Read: `pyproject.toml`
  - Workspace package source map and development package set.
- Read: `packages/*/pyproject.toml`
  - Core package metadata, versions, dependencies, package data, and typing markers.
- Read: `plugins/*/pyproject.toml`
  - Plugin metadata, versions, dependencies, and entry point groups.
- Read: `.github/workflows/ci.yml`
  - Current PR/main CI gates.
- Read: `.github/workflows/release.yml`
  - Normal `v*.*.*` release tag validation.
- Read: `.github/workflows/pypi-publish.yml`
  - Python package build/publish list and artifact count assertions.
- Read: `.github/workflows/helm-release.yaml`
  - Helm chart release triggers and packaging behavior.
- Read: `.github/workflows/helm-ci.yaml`
  - Helm validation gates.
- Read: `.github/workflows/weekly.yml`
  - Scheduled integration/E2E evidence source.
- Read: `RELEASING.md` and `.github/CI.md`
  - Documented release expectations to compare against executable workflows.
- Read: `TESTING.md`
  - Test lane definitions and required validation semantics.
- Read: `test-artifacts/`
  - Recent local DevPod/AWS validation artifacts, when relevant and traceable.

## Audit Decision States

Use exactly these package states in the report:

- `Alpha Included`
- `Alpha Included with Caveat`
- `Excluded from Alpha`
- `Blocked`

Use exactly these evidence levels in the ledger:

- `Static`
- `Contract`
- `Integration`
- `E2E`
- `Release`
- `Live Provider`

Use exactly these evidence freshness labels:

- `Current main`
- `Post-composition historical`
- `Stale or unproven`
- `Missing`

---

### Task 1: Establish Baseline And Report Skeleton

**Files:**
- Create: `docs/analysis/2026-05-13-alpha-release-readiness-report.md`

- [ ] **Step 1: Verify repo state**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git log --oneline -8
```

Expected:

- Branch is `main`.
- Working tree is clean before starting the report.
- Recent history includes PRs #332 through #337, or newer commits that already contain them.

- [ ] **Step 2: Verify remote validation resources are not active**

Run:

```bash
devpod list || true
```

Expected:

- No active DevPod workspaces appear.
- If DevPod prints an empty table, record that in the report as cleanup baseline evidence.

- [ ] **Step 3: Create the report skeleton**

Create `docs/analysis/2026-05-13-alpha-release-readiness-report.md` with this content:

```markdown
# Alpha Release Readiness Report

## Summary

Status: In progress
Current main SHA: record the full output of `git rev-parse HEAD` in Task 1 Step 4.
Audit date: 2026-05-13

This report defines the alpha package cutline for Floe. A package is included
only when current-main or post-composition historical evidence proves it works
through the implemented binding and composition model.

## Go/No-Go Recommendation

Recommendation: Audit evidence collection has started; final recommendation is completed in Task 6.

## Current State

- Branch:
- HEAD:
- Working tree:
- Current main CI:
- DevPod workspace state:
- AWS provider cleanup state:

## Release Artifact Inventory

Task 2 replaces this sentence with the artifact inventory.

## Package Cutline

| Package | Decision | Evidence Summary | Blockers / Caveats |
|---|---|---|---|

## Evidence Ledger

| Package | Static | Contract | Integration | E2E | Release | Live Provider | Freshness | Evidence References |
|---|---|---|---|---|---|---|---|---|

## Release Workflow Gaps

Task 4 replaces this sentence with release workflow gap findings.

## Composability And Security Findings

Task 6 replaces this sentence with composability and security findings.

## Required Changes Before Tagging

Task 6 replaces this sentence with the required pre-tag checklist.

## Excluded Packages

Task 6 replaces this sentence with excluded package decisions.

## Validation Commands Run

Each task appends the commands it executed and the observed result.
```

- [ ] **Step 4: Fill baseline fields**

Edit the `Current State` section using concrete values from Steps 1 and 2.

Use this shape:

```markdown
## Current State

- Branch: `main`
- HEAD: full SHA copied from `git rev-parse HEAD`
- Working tree: clean
- Current main CI: not checked in Task 1; Task 4 records the observed workflow state
- DevPod workspace state: no active workspaces reported by `devpod list`
- AWS provider cleanup state: Task 5 records whether cleanup was rerun in this audit
```

- [ ] **Step 5: Commit baseline report skeleton**

Run:

```bash
git add docs/analysis/2026-05-13-alpha-release-readiness-report.md
git commit -m "Start alpha release readiness report"
```

Expected:

- Commit succeeds.
- Only the report file is committed.

---

### Task 2: Build Release Artifact Inventory

**Files:**
- Modify: `docs/analysis/2026-05-13-alpha-release-readiness-report.md`
- Read: `pyproject.toml`
- Read: `.github/workflows/pypi-publish.yml`
- Read: `.github/workflows/release.yml`
- Read: `.github/workflows/helm-release.yaml`
- Read: `RELEASING.md`
- Read: `.github/CI.md`

- [ ] **Step 1: Count distributable package projects**

Run:

```bash
find packages plugins -mindepth 2 -maxdepth 2 -name pyproject.toml | sort
find packages plugins -mindepth 2 -maxdepth 2 -name pyproject.toml | wc -l
```

Expected:

- The command prints all package/plugin pyprojects.
- Current expected count is `26`; if it differs, record the observed count.

- [ ] **Step 2: Extract package names, versions, and entry points**

Run:

```bash
for f in packages/*/pyproject.toml plugins/*/pyproject.toml; do
  printf '%s | ' "$f"
  rg -n '^name =|^version =|floe-core|^\[project.entry-points' "$f" | sed 's/^/ /'
done
```

Expected:

- Each package shows `name` and `version`.
- Plugin packages show an entry point group.
- Packages depending on core show `floe-core>=0.1.0` or equivalent.

- [ ] **Step 3: Compare package projects to PyPI publish list**

Run:

```bash
comm -23 \
  <(find packages plugins -mindepth 2 -maxdepth 2 -name pyproject.toml | sed 's#/pyproject.toml##' | sort) \
  <(sed -n '/PACKAGES=(/,/)/p' .github/workflows/pypi-publish.yml | rg '^            (packages|plugins)/' | sed 's/^            //' | sort)

comm -13 \
  <(find packages plugins -mindepth 2 -maxdepth 2 -name pyproject.toml | sed 's#/pyproject.toml##' | sort) \
  <(sed -n '/PACKAGES=(/,/)/p' .github/workflows/pypi-publish.yml | rg '^            (packages|plugins)/' | sed 's/^            //' | sort)
```

Expected:

- First command lists package projects missing from PyPI publish workflow.
- Current expected missing packages are:
  - `plugins/floe-catalog-glue`
  - `plugins/floe-storage-aws-s3`
- Second command should be empty; if not, record extras as blockers.

- [ ] **Step 4: Identify release tag trigger mismatch**

Run:

```bash
rg -n "tags:|v\*\.\*\.\*|helm-v|charts-v|PyPI|Helm Release|Release" \
  .github/workflows/release.yml \
  .github/workflows/pypi-publish.yml \
  .github/workflows/helm-release.yaml \
  RELEASING.md \
  .github/CI.md
```

Expected:

- `release.yml` and `pypi-publish.yml` trigger on `v*.*.*`.
- `helm-release.yaml` triggers on `helm-v*` and `charts-v*`, not normal `v*.*.*`.
- Record the Helm tag mismatch as a release workflow gap unless the alpha release explicitly excludes Helm publishing.

- [ ] **Step 5: Update Release Artifact Inventory section**

Replace the Task 1 text under `## Release Artifact Inventory` with concrete observed values:

```markdown
## Release Artifact Inventory

### Python Packages

- Distributable package projects discovered: 26 if the package count still matches Task 2 Step 1; otherwise use the observed count.
- PyPI workflow package entries: 24 if the workflow still matches Task 2 Step 3; otherwise use the observed count.
- Missing from PyPI workflow: `plugins/floe-catalog-glue`, `plugins/floe-storage-aws-s3` unless Task 2 Step 3 proves this has changed.
- Extra in PyPI workflow: none unless Task 2 Step 3 prints extra paths.

### Release Workflows

- `release.yml`: record the `v*.*.*` trigger and the validation jobs it actually executes.
- `pypi-publish.yml`: record the `v*.*.*` trigger, package list source, and wheel/sdist count assertions.
- `helm-release.yaml`: record the `helm-v*` and `charts-v*` triggers and chart packaging behavior.
- `helm-ci.yaml`: record the PR/main Helm validation behavior.

### Documented Expectations

- `RELEASING.md`: summarize the documented alpha release procedure and validation expectations.
- `.github/CI.md`: summarize the documented CI/release pipeline expectations.

### Inventory Findings

- Python publishing currently needs an explicit alpha cutline decision because the workflow package list and discovered package projects differ.
- Helm publishing currently uses separate release tags from normal Python alpha tags.
```

- [ ] **Step 6: Commit artifact inventory**

Run:

```bash
git add docs/analysis/2026-05-13-alpha-release-readiness-report.md
git commit -m "Document alpha release artifact inventory"
```

Expected:

- Commit contains only report updates.

---

### Task 3: Build Package Evidence Ledger

**Files:**
- Modify: `docs/analysis/2026-05-13-alpha-release-readiness-report.md`
- Read: package and plugin `pyproject.toml` files
- Read: `tests/`, `packages/*/tests/`, `plugins/*/tests/`

- [ ] **Step 1: Summarize test distribution by package**

Run:

```bash
find tests packages plugins -path '*/test_*.py' -print | sort |
awk 'BEGIN{FS="/"} {
  if ($1=="tests") key=$1"/"$2;
  else key=$1"/"$2"/"$3"/"$4;
  count[key]++
}
END{ for (k in count) print count[k], k }' | sort -k2
```

Expected:

- Root `tests/contract`, `tests/integration`, `tests/e2e`, and package/plugin test counts are listed.
- Record counts as evidence, not as automatic inclusion.

- [ ] **Step 2: Identify packages without package-local integration/E2E directories**

Run:

```bash
for d in packages/* plugins/*; do
  [ -d "$d" ] || continue
  if [ ! -d "$d/tests/integration" ] && [ ! -d "$d/tests/e2e" ]; then
    echo "$d"
  fi
done
```

Expected:

- Packages with only unit tests are listed.
- Treat this as a prompt to look for root-level E2E or contract evidence, not immediate exclusion.

- [ ] **Step 3: Map root tests to likely alpha packages**

Run:

```bash
for pkg in \
  floe-core \
  floe-iceberg \
  floe-orchestrator-dagster \
  floe-catalog-polaris \
  floe-storage-minio \
  floe-compute-duckdb \
  floe-dbt-core \
  floe-ingestion-dlt \
  floe-lineage-marquez \
  floe-telemetry-jaeger \
  floe-quality-gx \
  floe-rbac-k8s \
  floe-network-security-k8s \
  floe-storage-aws-s3 \
  floe-catalog-glue; do
  echo "=== ${pkg}"
  rg -n "${pkg}|${pkg//-/_}|${pkg#floe-}" tests packages plugins docs/superpowers/specs || true
done
```

Expected:

- Each package has matching test or documentation references.
- Missing direct references are recorded as evidence gaps.

- [ ] **Step 4: Fill the Package Cutline table**

Edit `## Package Cutline` and create one row for every distributable package.

Use this exact decision hypothesis unless evidence from Steps 1-3 proves a different state:

```markdown
| Package | Decision | Evidence Summary | Blockers / Caveats |
|---|---|---|---|
| `floe-core` | Alpha Included | Core schemas, compilation, contracts, and root E2E coverage. | Verify current-main CI and release build. |
| `floe-iceberg` | Alpha Included | Iceberg runtime and writer contracts plus integration/unit coverage. | Verify current-main integration evidence. |
| `floe-orchestrator-dagster` | Alpha Included | Dagster plugin is exercised by demo/E2E and package tests. | Verify release E2E gate covers it. |
| `floe-catalog-polaris` | Alpha Included | Polaris plugin has package integration and root E2E coverage. | Verify current-main integration evidence. |
| `floe-storage-minio` | Alpha Included | MinIO is the in-cluster storage path for platform E2E. | Package-local integration is thin; root E2E must count directly. |
| `floe-compute-duckdb` | Alpha Included | DuckDB compute has integration coverage and demo path use. | Verify package build/install. |
| `floe-dbt-core` | Alpha Included | dbt core path has integration and E2E profile coverage. | Verify release gate includes relevant E2E. |
| `floe-ingestion-dlt` | Alpha Included | dlt ingestion has integration plus Customer 360 and format-matrix E2E coverage. | Verify latest post-composition run evidence. |
| `floe-lineage-marquez` | Alpha Included with Caveat | Marquez is part of observability/lineage E2E evidence. | Package-local integration is absent; root E2E evidence must be cited. |
| `floe-telemetry-jaeger` | Alpha Included | Jaeger telemetry has integration and observability E2E evidence. | Verify current-main observability evidence. |
| `floe-quality-gx` | Alpha Included with Caveat | GX is exercised by quality E2E evidence. | Package-local integration absent; cite root E2E. |
| `floe-rbac-k8s` | Alpha Included | RBAC plugin has integration and contract coverage. | Verify Helm/RBAC release gates. |
| `floe-network-security-k8s` | Alpha Included | Network security plugin has integration/E2E/performance coverage. | Verify alpha scope includes network policies. |
| `floe-storage-aws-s3` | Alpha Included with Caveat | Recent live AWS S3 + Glue validation covers provider path. | Missing from PyPI publish workflow; release blocker until intentional inclusion/exclusion is applied. |
| `floe-catalog-glue` | Alpha Included with Caveat | Recent live AWS S3 + Glue validation covers provider path. | Missing from PyPI publish workflow; release blocker until intentional inclusion/exclusion is applied. |
| `floe-alert-slack` | Excluded from Alpha | Unit/plugin registration evidence only. | Needs composed alert-channel integration/E2E. |
| `floe-alert-email` | Excluded from Alpha | Unit/plugin registration evidence only. | Needs composed alert-channel integration/E2E. |
| `floe-alert-alertmanager` | Excluded from Alpha | Unit/plugin registration evidence only. | Needs composed alert-channel integration/E2E. |
| `floe-alert-webhook` | Excluded from Alpha | Unit/plugin registration evidence only. | Needs composed alert-channel integration/E2E. |
| `floe-identity-keycloak` | Excluded from Alpha | Integration evidence exists but not alpha runtime path evidence. | Needs concrete alpha identity composition path. |
| `floe-secrets-infisical` | Excluded from Alpha | Integration evidence exists but not alpha runtime path evidence. | Needs concrete alpha secrets backend path. |
| `floe-secrets-k8s` | Excluded from Alpha | Integration evidence exists but not alpha runtime path evidence. | Needs concrete alpha secrets backend path. |
| `floe-semantic-cube` | Excluded from Alpha | Integration exists but alpha composed runtime path is not proven. | Needs semantic-layer E2E path. |
| `floe-dbt-fusion` | Excluded from Alpha | Integration exists but alpha runtime should rely on `floe-dbt-core`. | Needs explicit Fusion alpha decision and E2E. |
| `floe-telemetry-console` | Excluded from Alpha | Unit/plugin registration evidence only. | Console telemetry is dev utility, not alpha runtime target unless proven otherwise. |
| `floe-quality-dbt` | Excluded from Alpha | Unit/plugin registration evidence only. | Needs composed quality plugin path. |
```

- [ ] **Step 5: Fill Evidence Ledger**

For each package, add a row under `## Evidence Ledger`.

Use concise evidence labels:

```markdown
| `floe-storage-aws-s3` | pyproject + entry point | storage binding contract | root AWS live integration | DevPod AWS provider lane | missing from PyPI workflow | PR #336/#337 live evidence | Post-composition historical | `tests/integration/test_aws_provider_live.py`; `test-artifacts/devpod-run-20260513T011349Z-10567` |
```

Expected:

- Every package in the cutline table has a matching evidence ledger row.
- Excluded packages explicitly show why evidence is insufficient.

- [ ] **Step 6: Commit package evidence ledger**

Run:

```bash
git add docs/analysis/2026-05-13-alpha-release-readiness-report.md
git commit -m "Add alpha package evidence ledger"
```

Expected:

- Commit contains only report updates.

---

### Task 4: Review Release Gate Enforcement

**Files:**
- Modify: `docs/analysis/2026-05-13-alpha-release-readiness-report.md`
- Read: `.github/workflows/*.yml`
- Read: `.github/workflows/*.yaml`
- Read: `.github/CI.md`
- Read: `RELEASING.md`

- [ ] **Step 1: Verify current main CI status**

Run:

```bash
gh run list --repo Obsidian-Owl/floe --branch main --limit 20 \
  --json databaseId,workflowName,status,conclusion,headSha,createdAt,displayTitle,event \
  --jq '.[] | {databaseId, workflowName, status, conclusion, headSha: .headSha[:8], event, createdAt, displayTitle}'
```

Expected:

- Runs for current `main` HEAD are visible.
- Record any queued/in-progress/failing workflows.
- Do not mark alpha ready while current-main required workflows are incomplete or failed.

- [ ] **Step 2: Inspect release workflow for E2E gap**

Run:

```bash
rg -n "test-e2e|test-e2e-full|E2E|e2e|devpod|test-aws-provider-live|devpod-test-aws-provider" \
  .github/workflows/release.yml \
  .github/CI.md \
  RELEASING.md
```

Expected:

- `release.yml` comments mention E2E, but no executed `test-e2e-full` or DevPod lane exists.
- Record as a release-blocking workflow gap if alpha requires E2E at tag time.

- [ ] **Step 3: Inspect PyPI workflow package count assertions**

Run:

```bash
rg -n "PACKAGES=|WHEEL_COUNT|SDIST_COUNT|Expected 24|packages/floe-core|plugins/floe-storage-aws-s3|plugins/floe-catalog-glue" \
  .github/workflows/pypi-publish.yml
```

Expected:

- Workflow asserts 24 wheels and 24 sdists.
- AWS S3 and Glue packages are absent unless fixed after this plan was written.
- Record whether this is a blocker or intentional alpha exclusion.

- [ ] **Step 4: Inspect Helm release trigger mismatch**

Run:

```bash
rg -n "tags:|helm-v|charts-v|v\*\.\*\.\*" .github/workflows/helm-release.yaml RELEASING.md .github/CI.md
```

Expected:

- Helm chart release uses separate tag namespace from Python alpha.
- Report whether alpha requires a paired `charts-v...`/`helm-v...` tag or a workflow change.

- [ ] **Step 5: Update Release Workflow Gaps section**

Replace the Task 1 text under `## Release Workflow Gaps` with this table and fill each evidence cell with the file/line or command output observed in Steps 1-4:

```markdown
## Release Workflow Gaps

| Gap | Severity | Evidence | Required Before Tagging |
|---|---|---|---|
| PyPI alpha package list does not yet encode the approved alpha cutline. | Blocker | Use the observed `pypi-publish.yml` package-list lines and package-count comparison. | Update the publish workflow or explicitly exclude packages from alpha before tagging. |
| AWS S3/Glue packages exist but are missing from the current PyPI workflow package list. | Blocker if included in alpha | Use Task 2 Step 3 output. | Either include them in the alpha publish list or mark them excluded from alpha. |
| Normal `v*.*.*` release tag does not trigger Helm chart release. | High | Use observed `helm-release.yaml` tag triggers. | Decide whether alpha has no Helm release, uses a paired Helm tag, or needs workflow consolidation. |
| `release.yml` does not execute full E2E/DevPod validation at tag time. | Blocker if alpha gate requires current E2E. | Use Task 4 Step 2 output. | Add the gate or require a traceable pre-tag DevPod artifact in the release checklist. |
```

Include at least these evaluated rows:

- PyPI alpha package list does not yet encode the approved alpha cutline.
- AWS S3/Glue packages exist but are missing from current PyPI workflow package list.
- Normal `v*.*.*` release tag does not trigger Helm chart release.
- `release.yml` does not execute the full E2E/DevPod validation gate despite comments/docs mentioning E2E.

- [ ] **Step 6: Commit release gate review**

Run:

```bash
git add docs/analysis/2026-05-13-alpha-release-readiness-report.md
git commit -m "Document alpha release gate gaps"
```

Expected:

- Commit contains only report updates.

---

### Task 5: Validate Historical And Fresh Runtime Evidence

**Files:**
- Modify: `docs/analysis/2026-05-13-alpha-release-readiness-report.md`
- Read: `test-artifacts/`
- Read: `tests/integration/test_aws_provider_live.py`
- Read: `scripts/aws-provider-test-cleanup.sh`
- Read: `scripts/devpod-test.sh`

- [ ] **Step 1: Locate recent DevPod and AWS artifacts**

Run:

```bash
find test-artifacts -maxdepth 2 -type f \( -name output.log -o -name exit-code -o -name run.sh \) -print | sort | tail -80
```

Expected:

- Recent DevPod artifact directories are visible.
- If `test-artifacts/devpod-run-20260513T011349Z-10567` exists, record it as AWS provider DevPod evidence for PR #336/#337.

- [ ] **Step 2: Inspect AWS provider DevPod output if present**

Run:

```bash
if [ -f test-artifacts/devpod-run-20260513T011349Z-10567/output.log ]; then
  tail -80 test-artifacts/devpod-run-20260513T011349Z-10567/output.log
else
  echo "AWS provider DevPod output artifact not present locally"
fi
```

Expected:

- If present, output shows `tests/integration/test_aws_provider_live.py ... [100%]` and `3 passed`.
- Record artifact path and result.

- [ ] **Step 3: Verify no remote env artifact remains in AWS DevPod bundle**

Run:

```bash
if [ -d test-artifacts/devpod-run-20260513T011349Z-10567 ]; then
  find test-artifacts/devpod-run-20260513T011349Z-10567 -name '*remote-env*' -print
else
  echo "AWS provider DevPod artifact directory not present locally"
fi
```

Expected:

- No files are printed when the artifact directory exists.
- Record as credential artifact evidence.

- [ ] **Step 4: Verify AWS cleanup for last known run if env is available**

Run only when `/tmp/floe-aws-provider-env.sh` and `/tmp/floe-provider-pr336-devpod-run-id` exist:

```bash
set -euo pipefail
set -a
. /tmp/floe-aws-provider-env.sh
set +a
export FLOE_PROVIDER_SPIKE_RUN="$(cat /tmp/floe-provider-pr336-devpod-run-id)"
AWS_PROFILE=floe-aws-bootstrap scripts/aws-provider-test-cleanup.sh
```

Expected:

- Cleanup prints `Cleanup checks passed`.
- If env files are absent, record cleanup as not rerun in this audit and cite the prior evidence only if traceable.

- [ ] **Step 5: Decide fresh full E2E requirement**

Do not automatically run the full DevPod lane in this task. Instead, update the report with one of these decisions:

```markdown
- Fresh full DevPod E2E required before tagging: yes
- Reason: release gate currently does not enforce `make test-e2e-full`; historical evidence exists but alpha tag should have a current-main artifact.
```

or:

```markdown
- Fresh full DevPod E2E required before tagging: no
- Reason: accepted post-composition artifact `test-artifacts/devpod-run-20260513T011349Z-10567` covers the alpha path and current-main changes since then do not affect runtime behavior.
```

Default recommendation:

```markdown
- Fresh full DevPod E2E required before tagging: yes
```

- [ ] **Step 6: Update Validation Commands Run section**

Replace the Task 1 text under `## Validation Commands Run` with a bullet list of every command run during the audit and its result:

```markdown
## Validation Commands Run

- `git status --short --branch`: pass, clean `main`
- `devpod list`: pass, no active workspaces
- `gh run list --repo Obsidian-Owl/floe --branch main --limit 20 ...`: record pass, fail, or incomplete with the observed workflow conclusions.
- `find test-artifacts -maxdepth 2 ...`: record whether recent DevPod/AWS artifacts were present.
- `scripts/aws-provider-test-cleanup.sh`: record pass only if it was rerun in this audit; otherwise record `not run in this audit` and explain why.
```

- [ ] **Step 7: Commit runtime evidence review**

Run:

```bash
git add docs/analysis/2026-05-13-alpha-release-readiness-report.md
git commit -m "Record alpha runtime validation evidence"
```

Expected:

- Commit contains only report updates.

---

### Task 6: Finalize Go/No-Go And Follow-Up Work

**Files:**
- Modify: `docs/analysis/2026-05-13-alpha-release-readiness-report.md`

- [ ] **Step 1: Fill Composability And Security Findings**

Replace the Task 1 text under `## Composability And Security Findings` with this table and cite concrete evidence for each row:

```markdown
## Composability And Security Findings

| Finding | Impact | Evidence | Required Action |
|---|---|---|---|
| Alpha-included packages must use capabilities, requirements, typed bindings, and resolver validation for cross-plugin contracts. | Prevents plugin-to-plugin implementation coupling. | Cite contract tests, resolver tests, or package code references found during the audit. | Block alpha inclusion for packages that rely on implementation-specific peer plugin details. |
| `CompiledArtifacts` must remain secret-free. | Prevents credential leakage into render outputs and persisted artifacts. | Cite schema tests, artifact assertions, or DevPod/AWS validation evidence. | Add or require regression coverage before tagging if any secret-bearing field is found. |
| DevPod AWS credential transfer must avoid persisted artifacts and scrub remote workspace files. | Prevents cloud credential leakage during live validation. | Cite PR #337 behavior and any current artifact scan from Task 5 Step 3. | Require artifact scrub evidence for AWS live validation before tagging. |
| Release workflow must not publish excluded packages by accident. | Prevents unsupported plugins from being distributed as alpha-ready. | Cite package inventory and PyPI workflow package-list comparison. | Align publish workflow with the approved package cutline. |
```

Include rows for:

- alpha-included packages must use typed bindings/resolver validation
- `CompiledArtifacts` must remain secret-free
- DevPod AWS credential transfer must avoid artifacts and scrub remote workspace files
- release workflow must not publish excluded packages by accident

- [ ] **Step 2: Fill Required Changes Before Tagging**

Replace the Task 1 text under `## Required Changes Before Tagging` with a checklist:

```markdown
## Required Changes Before Tagging

- [ ] Current `main` CI is green for the full SHA recorded in the Current State section.
- [ ] Alpha PyPI package list exactly matches the approved cutline.
- [ ] Package build dry-run passes for the alpha cutline.
- [ ] Full integration evidence is current or accepted historical.
- [ ] Full E2E/DevPod evidence is current or accepted historical.
- [ ] AWS provider live evidence is current or accepted historical.
- [ ] Helm release strategy is explicit for alpha.
- [ ] Excluded packages are not published by the alpha tag.
```

- [ ] **Step 3: Fill Excluded Packages**

Replace the Task 1 text under `## Excluded Packages` with:

```markdown
## Excluded Packages

| Package | Exclusion Reason | Evidence Needed For Future Inclusion |
|---|---|---|
| `floe-alert-slack` | No composed alpha runtime path. | Alert-channel integration/E2E through the composition model. |
| `floe-alert-email` | No composed alpha runtime path. | Alert-channel integration/E2E through the composition model. |
| `floe-alert-alertmanager` | No composed alpha runtime path. | Alert-channel integration/E2E through the composition model. |
| `floe-alert-webhook` | No composed alpha runtime path. | Alert-channel integration/E2E through the composition model. |
| `floe-identity-keycloak` | Not part of alpha runtime path. | Concrete identity composition path plus integration/E2E. |
| `floe-secrets-infisical` | Not part of alpha runtime path. | Concrete secret backend path plus integration/E2E. |
| `floe-secrets-k8s` | Not part of alpha runtime path. | Concrete secret backend path plus integration/E2E. |
| `floe-semantic-cube` | Semantic-layer E2E not proven for alpha. | Semantic-layer composed runtime E2E. |
| `floe-dbt-fusion` | Fusion is not the alpha dbt execution path. | Explicit Fusion cutline decision plus E2E. |
| `floe-telemetry-console` | Dev utility evidence only. | Alpha runtime telemetry path or explicit dev-only release policy. |
| `floe-quality-dbt` | Quality plugin composition path not proven. | Composed quality plugin integration/E2E. |
```

- [ ] **Step 4: Finalize Go/No-Go Recommendation**

Set one of these recommendations:

```markdown
## Go/No-Go Recommendation

Recommendation: No-go for alpha tag until release workflow blockers are fixed.

Reasons:

- The alpha package publish list does not yet match the approved evidence-based cutline.
- A current-main full E2E/DevPod release artifact is required or the release checklist must explicitly accept the named historical artifact.
```

or:

```markdown
## Go/No-Go Recommendation

Recommendation: Go for alpha tag after the listed validation commands are rerun from current `main`.

Reasons:

- Current `main` CI, integration, E2E/DevPod, and live-provider evidence satisfy the release gate.
- Release workflows and publish lists match the approved alpha cutline.
```

Default recommendation unless the audit proves otherwise:

```markdown
Recommendation: No-go for alpha tag until release workflow blockers are fixed.
```

- [ ] **Step 5: Self-review report**

Run:

```bash
rg -n "Audit evidence collection has started|Task [0-9] replaces|not checked in Task 1" docs/analysis/2026-05-13-alpha-release-readiness-report.md || true
```

Expected:

- No draft-marker matches remain.
- If matches remain, replace them with concrete evidence or an explicit `Not run in this audit` statement.

- [ ] **Step 6: Commit final report**

Run:

```bash
git add docs/analysis/2026-05-13-alpha-release-readiness-report.md
git commit -m "Finalize alpha release readiness audit"
```

Expected:

- Commit contains only report updates.

---

### Task 7: Verification And Handoff

**Files:**
- Read: `docs/analysis/2026-05-13-alpha-release-readiness-report.md`
- Read: `docs/superpowers/specs/2026-05-13-alpha-release-readiness-audit-design.md`

- [ ] **Step 1: Verify spec coverage**

Run:

```bash
python - <<'PY'
from pathlib import Path
report = Path("docs/analysis/2026-05-13-alpha-release-readiness-report.md").read_text()
required = [
    "Release Artifact Inventory",
    "Package Cutline",
    "Evidence Ledger",
    "Release Workflow Gaps",
    "Composability And Security Findings",
    "Required Changes Before Tagging",
    "Excluded Packages",
    "Validation Commands Run",
]
missing = [section for section in required if f"## {section}" not in report]
if missing:
    raise SystemExit(f"missing sections: {missing}")
print("report sections present")
PY
```

Expected:

- Prints `report sections present`.

- [ ] **Step 2: Verify package rows cover all distributable packages**

Run:

```bash
python - <<'PY'
from pathlib import Path
import re

packages = []
for pyproject in sorted(Path("packages").glob("*/pyproject.toml")) + sorted(Path("plugins").glob("*/pyproject.toml")):
    text = pyproject.read_text()
    match = re.search(r'^name = "([^"]+)"', text, re.MULTILINE)
    if match:
        packages.append(match.group(1))

report = Path("docs/analysis/2026-05-13-alpha-release-readiness-report.md").read_text()
missing = [pkg for pkg in packages if f"`{pkg}`" not in report]
if missing:
    raise SystemExit(f"missing package names in report: {missing}")
print(f"all {len(packages)} packages mentioned")
PY
```

Expected:

- Prints `all 26 packages mentioned`, or the current package count if it changed.

- [ ] **Step 3: Check final git state**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected:

- Working tree is clean.
- Latest commits include the audit report commits.

- [ ] **Step 4: Final handoff**

Prepare a concise handoff message with:

- report path
- current branch and HEAD
- package cutline summary
- go/no-go recommendation
- release blockers
- validation commands that passed
- validation commands not run
- whether any DevPod/AWS resources need cleanup

Do not tag a release in this task.
