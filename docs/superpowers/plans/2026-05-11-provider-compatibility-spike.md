# Provider Compatibility Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the provider compatibility spike artifacts that validate whether Floe's merged binding/composition model generalizes beyond the MinIO plus Polaris baseline.

**Architecture:** This plan is documentation-and-evidence first. It maps the implemented model, builds a provider compatibility matrix, classifies gaps, defines a live-service validation runbook, and produces a final recommendation without implementing production provider plugins.

**Tech Stack:** Python 3.10+, Pydantic v2, uv, pytest, ripgrep, Markdown validation scripts, DevPod/Hetzner remote validation, optional AWS CLI or SDK evidence for the later live lane.

---

## Scope Boundary

This plan implements the spike artifacts only. It does not implement AWS S3,
AWS Glue, Nessie, GCS, Azure, Hive, or new production plugin code.

The plan may run read-only code searches and existing tests. It may create or
edit Markdown evidence artifacts under `docs/validation/` and should update no
production source files unless a validation command exposes a blocker that the
user explicitly asks to fix.

The preferred live proof remains AWS S3 plus AWS Glue, but this plan only
defines the executable live runbook and readiness gate. Actual live AWS
execution requires explicit credentials and cleanup confirmation before a later
implementation session runs it.

## File Map

Create these evidence artifacts:

- `docs/validation/2026-05-11-provider-compatibility-system-map.md`
  - Owns the implemented-system map and source evidence from `main`.
- `docs/validation/2026-05-11-provider-compatibility-matrix.md`
  - Owns provider-by-provider compatibility decisions.
- `docs/validation/2026-05-11-provider-compatibility-gap-ledger.md`
  - Owns gap classification and next implementation recommendations.
- `docs/validation/2026-05-11-provider-compatibility-live-runbook.md`
  - Owns AWS S3 plus Glue and Nessie plus MinIO live validation runbooks.
- `docs/validation/2026-05-11-provider-compatibility-final-recommendation.md`
  - Owns the final recommendation and first follow-up implementation unit.

Read these source and docs surfaces:

- `docs/superpowers/specs/2026-05-11-provider-compatibility-spike-design.md`
- `docs/validation/2026-05-09-post-composition-plugin-matrix.md`
- `docs/validation/2026-05-09-post-composition-compatibility-ledger.md`
- `docs/validation/2026-05-09-post-composition-runtime-validation.md`
- `docs/architecture/plugin-composition-uplift-tracker.md`
- `packages/floe-core/src/floe_core/composition/models.py`
- `packages/floe-core/src/floe_core/composition/resolver.py`
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- `packages/floe-core/src/floe_core/runtime_catalog_connection.py`
- `packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py`
- `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py`
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/`
- `packages/floe-core/src/floe_core/cli/helm/generate.py`

## Task 1: Preflight And Implemented-System Evidence

**Files:**
- Read: `docs/superpowers/specs/2026-05-11-provider-compatibility-spike-design.md`
- Read: `packages/floe-core/src/floe_core/composition/models.py`
- Read: `packages/floe-core/src/floe_core/composition/resolver.py`
- Read: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- Read: `packages/floe-core/src/floe_core/runtime_catalog_connection.py`
- Read: `packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py`
- Create: `docs/validation/2026-05-11-provider-compatibility-system-map.md`

- [ ] **Step 1: Confirm trunk state**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git log --oneline -5
```

Expected:

- Branch is `main`.
- Worktree is clean before edits.
- Recent history includes `docs: add provider compatibility spike design`.

- [ ] **Step 2: Capture composition and binding source map**

Run:

```bash
rg -n "class (CapabilitySet|RequirementSet|PluginCapabilities|PluginRequirements|CompositionIssue|CompositionValidationResult)|class (StorageDeploymentBinding|CatalogDeploymentBinding|IngestionDeploymentBinding|RuntimeCatalogConnection|CredentialRef|DeploymentConfig)|def build_runtime_catalog_connection|def runtime_catalog_connection_to_pyiceberg_config" \
  packages/floe-core/src/floe_core/composition \
  packages/floe-core/src/floe_core/schemas/compiled_artifacts.py \
  packages/floe-core/src/floe_core/runtime_catalog_connection.py \
  packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py
```

Expected:

- Output identifies all current composition and typed binding symbols.
- `RuntimeCatalogConnection` exists in `compiled_artifacts.py`.
- Runtime catalog derivation and PyIceberg translation functions exist.

- [ ] **Step 3: Capture provider implementation source map**

Run:

```bash
rg -n "def get_deployment_binding|def get_storage_requirements|def build_catalog_deployment|def get_composition_requirements|def build_deployment_binding|def augment_dbt_profile|RuntimeCatalogConnection|build_runtime_catalog_connection|runtime_catalog_connection_to_pyiceberg_config" \
  plugins/floe-storage-minio/src \
  plugins/floe-catalog-polaris/src \
  plugins/floe-ingestion-dlt/src \
  plugins/floe-compute-duckdb/src \
  plugins/floe-orchestrator-dagster/src \
  packages/floe-core/src/floe_core/cli/helm/generate.py
```

Expected:

- Output shows MinIO emits storage binding.
- Output shows Polaris declares requirements and emits catalog binding.
- Output shows dlt declares requirements and emits ingestion binding.
- Output shows DuckDB augments dbt profiles from deployment bindings.
- Output shows Dagster and Iceberg consume runtime catalog connection.
- Output shows Helm rendering uses deployment bindings.

- [ ] **Step 4: Create the system-map artifact**

Create `docs/validation/2026-05-11-provider-compatibility-system-map.md` with this structure and fill it from Steps 1-3:

```markdown
# Provider Compatibility Implemented-System Map

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Branch: `main`
Purpose: Source map for the provider compatibility spike.

## Current Head

| Item | Evidence |
| --- | --- |
| Branch | `main` |
| HEAD | Record the exact SHA printed by `git rev-parse HEAD` in Step 1 |
| Recent commits | Record the five commit subjects printed by `git log --oneline -5` in Step 1 |

## Composition Contracts

| Contract | Source | Role |
| --- | --- | --- |
| `CapabilitySet` | `packages/floe-core/src/floe_core/composition/models.py` | Provider capability declaration |
| `RequirementSet` | `packages/floe-core/src/floe_core/composition/models.py` | Provider requirement declaration |
| `CompositionResolver` | `packages/floe-core/src/floe_core/composition/resolver.py` | Compatibility validation |
| `COMPOSITION_*` diagnostics | `packages/floe-core/src/floe_core/composition/error_codes.py` | Operator-facing composition failures |

## Typed Bindings

| Binding | Source | Role |
| --- | --- | --- |
| `StorageDeploymentBinding` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Secret-free storage deployment state |
| `CatalogDeploymentBinding` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Secret-free catalog deployment state |
| `IngestionDeploymentBinding` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Secret-free ingestion runtime state |
| `RuntimeCatalogConnection` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Neutral Iceberg runtime catalog projection |
| `CredentialRef` | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | Secret-free credential reference |

## Current Provider Consumers

| Consumer | Source | Current behavior |
| --- | --- | --- |
| MinIO storage | `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py` | Emits `StorageDeploymentBinding` |
| Polaris catalog | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | Declares storage requirements and emits `CatalogDeploymentBinding` |
| dlt ingestion | `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py` | Declares storage/catalog requirements and emits `IngestionDeploymentBinding` |
| DuckDB compute | `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py` | Augments dbt profile from deployment bindings |
| Dagster runtime | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/` | Consumes `RuntimeCatalogConnection` |
| Helm renderer | `packages/floe-core/src/floe_core/cli/helm/generate.py` | Renders from deployment bindings |

## Baseline Conclusion

MinIO plus Polaris is the control path. New provider compatibility must either reuse the current neutral contracts or justify a new capability, binding, runtime translator, or renderer dimension.
```

- [ ] **Step 5: Commit the system-map artifact**

Run:

```bash
git add docs/validation/2026-05-11-provider-compatibility-system-map.md
git commit -m "docs: map provider compatibility baseline"
```

Expected: commit succeeds and hooks pass.

## Task 2: Provider Compatibility Matrix

**Files:**
- Read: `docs/validation/2026-05-11-provider-compatibility-system-map.md`
- Read: `docs/validation/2026-05-09-post-composition-plugin-matrix.md`
- Read: `docs/architecture/plugin-composition-uplift-tracker.md`
- Create: `docs/validation/2026-05-11-provider-compatibility-matrix.md`

- [ ] **Step 1: Inventory existing plugin entry points**

Run:

```bash
python - <<'PY'
from pathlib import Path
import tomllib

for path in sorted(Path("plugins").glob("*/pyproject.toml")):
    data = tomllib.loads(path.read_text())
    entry_points = data.get("project", {}).get("entry-points", {})
    floe_groups = {
        group: sorted(entries)
        for group, entries in entry_points.items()
        if group.startswith("floe.")
    }
    if floe_groups:
        print(path.parent.name)
        for group, names in floe_groups.items():
            print(f"  {group}: {', '.join(names)}")
PY
```

Expected:

- Output includes `floe-storage-minio`, `floe-catalog-polaris`, `floe-ingestion-dlt`, `floe-compute-duckdb`, `floe-orchestrator-dagster`, and the security/observability plugin families.
- Output does not include AWS S3, AWS Glue, Nessie, GCS, Azure, or Hive provider plugins.

- [ ] **Step 2: Create the matrix artifact**

Create `docs/validation/2026-05-11-provider-compatibility-matrix.md` with this structure:

```markdown
# Provider Compatibility Matrix

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Purpose: Provider-by-provider assessment against the merged binding/composition model.

## Level Definitions

| Level | Meaning | Evidence required |
| --- | --- | --- |
| 0 | Discoverable plugin only | Entry point, metadata, config schema |
| 1 | Declares capabilities and requirements | `PluginCapabilities`, `PluginRequirements`, resolver tests |
| 2 | Emits or consumes typed bindings | Contract model, schema tests, secret-free artifacts |
| 3 | Runtime/deployment translated and validated | Resolver tests, binding output, renderer/runtime translation, E2E or live proof where applicable |

## Matrix

| Provider combination | Storage protocol | Catalog protocol | Credential mode | Identity mode | Endpoint shape | Warehouse ownership | Server-side storage access | Current expressibility | Required model change | Target level | Live proof |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MinIO + Polaris | `s3-compatible` | Iceberg REST via Polaris | Kubernetes Secret | none | explicit internal/external endpoint, path-style | storage binding plus Polaris warehouse | yes, via referenced MinIO credentials | Expressed today | none | Level 3 | Existing DevPod/Hetzner E2E control path |
| AWS S3 + AWS Glue | `s3` | Glue Catalog | workload identity or secret-backed AWS credentials | IRSA, AWS Pod Identity, or external AWS credentials | regional AWS endpoints, optional custom endpoint for tests | S3 bucket/prefix plus Glue database/table metadata | yes, through AWS IAM | Partially expressible conceptually; provider plugins absent | native S3 storage plugin, Glue catalog binding, AWS identity/credential requirements, PyIceberg Glue translation proof | Level 3 target after implementation | Preferred live proof |
| AWS S3 + Iceberg REST or Polaris | `s3` | Iceberg REST | workload identity or secret-backed AWS credentials | IRSA, AWS Pod Identity, or external AWS credentials | AWS S3 regional endpoint plus REST catalog URI | storage owns bucket/prefix, catalog owns warehouse reference | depends on catalog deployment | Partially expressible conceptually; native S3 plugin absent | native S3 storage binding plus catalog-specific requirements | Level 2 or 3 depending on live catalog | Optional second proof |
| MinIO + Nessie | `s3-compatible` | Nessie Iceberg catalog | Kubernetes Secret | none | MinIO path-style endpoint plus Nessie REST endpoint | storage bucket/prefix plus Nessie catalog branch/namespace | yes, if Nessie service accesses storage | MinIO side expressed; Nessie provider absent | Nessie catalog plugin and typed catalog binding | Level 3 fallback target | Fallback live proof |
| AWS S3 + Nessie | `s3` | Nessie Iceberg catalog | workload identity or secret-backed AWS credentials | IRSA, AWS Pod Identity, or external AWS credentials | AWS S3 endpoint plus Nessie REST endpoint | S3 bucket/prefix plus Nessie branch/namespace | yes, if Nessie service accesses storage | Not implemented | native S3 storage plugin, Nessie catalog plugin, identity/credential binding proof | Level 3 second-wave target | Deferred live proof |
| GCS + future catalog | `gcs` | provider-specific | workload identity or secret-backed service account | GCP Workload Identity or service account reference | GCS bucket URI and regional/multi-region behavior | GCS bucket/prefix plus catalog metadata | provider-dependent | Not implemented | GCS storage capability, credential mode, runtime translator pressure test | Level 1 or 2 design target | No first live proof |
| Azure Blob or ADLS + future catalog | `abfs` or provider-specific | provider-specific | workload identity or secret-backed identity | Azure Workload Identity or managed identity | account/container/path endpoint | container/path plus catalog metadata | provider-dependent | Not implemented | Azure storage capability, identity mode, runtime translator pressure test | Level 1 or 2 design target | No first live proof |
| Hive catalog | object-store dependent | Hive metastore | provider-dependent | provider-dependent | metastore URI plus object-store endpoint | storage path plus Hive metadata | yes | Not implemented and no concrete alpha trigger | defer until deployment path exists | Level 0 deferred | No live proof |

## Entry Point Evidence

Record the Step 1 entry point inventory summary here. Use it to prove which providers exist today and which are future provider paths.

## Matrix Conclusion

AWS S3 plus Glue is the preferred first live target because it stresses native cloud storage, managed catalog semantics, IAM, and PyIceberg runtime translation. Nessie plus MinIO is the fallback because it validates catalog variation without cloud-provider setup.
```

- [ ] **Step 3: Search for provider-specific assumptions**

Run:

```bash
rg -n '"minio"|polaris|s3-compatible|path-style|path_style|Glue|glue|Nessie|nessie|GCS|Azure|ADLS|abfs|s3.endpoint|warehouse' \
  packages plugins tests docs/contracts docs/architecture \
  -g '*.py' -g '*.md' -g '*.yaml' -g '*.yml' -g '*.json'
```

Expected:

- Output identifies current MinIO/Polaris assumptions.
- Output does not show production AWS Glue or Nessie provider implementations.
- Add a short "Provider-specific assumption search" section to the matrix artifact with the main findings.

- [ ] **Step 4: Commit the provider matrix**

Run:

```bash
git add docs/validation/2026-05-11-provider-compatibility-matrix.md
git commit -m "docs: add provider compatibility matrix"
```

Expected: commit succeeds and hooks pass.

## Task 3: Gap Classification Ledger

**Files:**
- Read: `docs/validation/2026-05-11-provider-compatibility-matrix.md`
- Read: `docs/validation/2026-05-09-post-composition-compatibility-ledger.md`
- Create: `docs/validation/2026-05-11-provider-compatibility-gap-ledger.md`

- [ ] **Step 1: Search for compatibility helpers and runtime rediscovery paths**

Run:

```bash
rg -n "get_pyiceberg_catalog_config|get_helm_values_override|artifacts\\.plugins\\.(storage|catalog)\\.config|runtime_catalog_connection|RuntimeCatalogConnection|build_runtime_catalog_connection|runtime_catalog_connection_to_pyiceberg_config" \
  packages plugins tests docs \
  -g '*.py' -g '*.md'
```

Expected:

- Output shows first-party runtime paths now prefer `RuntimeCatalogConnection`.
- Deprecated helpers may still exist as compatibility surfaces, but should not be recommended as new provider contracts.

- [ ] **Step 2: Search for secret-sensitive binding fields**

Run:

```bash
rg -n "CredentialRef|StorageCredentialBinding|SecretReference|SecretStr|access_key|secret_key|client_secret|token|password|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY" \
  packages/floe-core/src/floe_core/schemas \
  packages/floe-core/src/floe_core/composition \
  plugins/floe-storage-minio/src \
  plugins/floe-catalog-polaris/src \
  plugins/floe-ingestion-dlt/src \
  tests/contract \
  -g '*.py'
```

Expected:

- Output shows compiled artifact credential material represented by references or env names.
- Output should not justify adding raw credential values to `CompiledArtifacts`.

- [ ] **Step 3: Create the gap ledger artifact**

Create `docs/validation/2026-05-11-provider-compatibility-gap-ledger.md` with this structure:

```markdown
# Provider Compatibility Gap Ledger

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Purpose: Classify provider compatibility gaps before implementation.

## Gap Categories

| Category | Meaning |
| --- | --- |
| No change | Current model already expresses the provider path |
| Capability-only gap | Resolver needs another compatibility dimension |
| Typed binding gap | Current bindings cannot carry required secret-free state |
| Provider plugin gap | Model is sufficient, but provider plugin does not exist |
| Runtime translator gap | Binding exists, but runtime library translation is missing |
| Renderer gap | Deployment output cannot be generated from bindings yet |
| Live validation gap | Real service proof is missing |
| Out of scope | Provider path lacks a concrete composition trigger |

## Gaps

| Gap | Provider path | Category | Evidence | Recommended next action |
| --- | --- | --- | --- | --- |
| Native AWS S3 storage provider absent | AWS S3 + Glue; AWS S3 + Nessie | Provider plugin gap | Entry point inventory has no `floe-storage-aws-s3` plugin | Design native S3 storage plugin after matrix approval |
| AWS credential and identity modes need proof against resolver | AWS S3 + Glue | Capability-only gap | Current composition model includes credential and identity modes but AWS provider declarations do not exist | Define AWS provider requirements and resolver tests in the first implementation unit |
| Glue catalog binding absent | AWS S3 + Glue | Provider plugin gap and typed binding gap | Entry point inventory has no Glue catalog plugin and current catalog binding has Polaris-specific provider detail only | Design Glue catalog provider-owned binding before implementation |
| PyIceberg Glue translation not proven from `RuntimeCatalogConnection` | AWS S3 + Glue | Runtime translator gap | Current runtime translator handles generic URI/warehouse/S3 properties, not proven Glue catalog properties | Add translator proof or a Glue-specific runtime projection in a follow-up spec |
| Nessie catalog provider absent | MinIO + Nessie; AWS S3 + Nessie | Provider plugin gap and typed binding gap | Entry point inventory has no Nessie catalog plugin | Design Nessie catalog binding if selected as fallback live proof |
| GCS and Azure credential/endpoint models are unproven | GCS; Azure | Capability-only gap and typed binding pressure test | No current provider plugin or runtime translation evidence | Keep as design pressure tests, not first implementation |
| Hive lacks concrete alpha path | Hive | Out of scope | No current deployment trigger in the approved spike | Defer until a product path exists |

## Compatibility Helper Decision

Do not use deprecated helper APIs as new provider contracts. New provider work must flow through capabilities, requirements, typed bindings, resolver validation, and runtime/renderer translators.

## Secret-Free Decision

Provider compatibility is invalid if it requires raw access keys, secret keys, tokens, client secrets, passwords, or bearer tokens inside `CompiledArtifacts`.

## First Follow-Up Recommendation

Recommend one implementation unit and one live validation lane based on the matrix:

- Primary path: AWS S3 plus AWS Glue provider compatibility design if AWS credentials and cleanup controls are available.
- Fallback path: Nessie plus MinIO provider compatibility design if AWS access is unavailable.
```

- [ ] **Step 4: Commit the gap ledger**

Run:

```bash
git add docs/validation/2026-05-11-provider-compatibility-gap-ledger.md
git commit -m "docs: classify provider compatibility gaps"
```

Expected: commit succeeds and hooks pass.

## Task 4: Live Validation Runbook

**Files:**
- Read: `scripts/devpod-test.sh`
- Read: `docs/validation/2026-05-09-post-composition-runtime-validation.md`
- Read: `docs/validation/2026-05-11-provider-compatibility-gap-ledger.md`
- Create: `docs/validation/2026-05-11-provider-compatibility-live-runbook.md`

- [ ] **Step 1: Capture DevPod remote lane command shape**

Run:

```bash
rg -n "DEVPOD_WORKSPACE|DEVPOD_REMOTE_E2E_MAKE_TARGET|DEVPOD_REMOTE_E2E_TIMEOUT|devpod list|Hetzner|hcloud|servers|volumes|ssh_keys|load_balancers|floating_ips" \
  scripts/devpod-test.sh docs/validation/2026-05-09-post-composition-runtime-validation.md
```

Expected:

- Output identifies the remote validation command pattern.
- Output identifies direct Hetzner inventory requirements.

- [ ] **Step 2: Create the live validation runbook**

Create `docs/validation/2026-05-11-provider-compatibility-live-runbook.md` with this structure:

```markdown
# Provider Compatibility Live Validation Runbook

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Purpose: Executable live-service validation plan for the provider compatibility spike.

## Preconditions

- Run from `main`.
- Worktree is clean before validation.
- DevPod is installed and has the Hetzner provider initialized.
- `.env` contains `DEVPOD_HETZNER_TOKEN` or the environment contains `HCLOUD_TOKEN`.
- AWS live proof requires explicit user approval that AWS credentials are available and scoped for the test.
- Do not run live AWS cleanup commands against shared resources unless the resource names match the current run prefix.

## Failure Classification

| Classification | Meaning |
| --- | --- |
| Product failure | Floe resolver, binding, runtime translation, renderer, or plugin behavior is wrong |
| Provider failure | AWS, Glue, S3, Nessie, or catalog provider rejects auth, permissions, region, endpoint, warehouse, or API usage |
| Infrastructure failure | DevPod, Hetzner, Kind, Flux, network, or provisioning fails before product validation |
| Cleanup failure | Billable or test resources remain after the run |
| Tooling warning | Non-fatal wrapper or tunnel behavior occurs after artifacts and cleanup prove the result |

## Preferred Lane: AWS S3 Plus AWS Glue

### Resource Naming

Use a unique run prefix:

```bash
export FLOE_PROVIDER_SPIKE_RUN="floe-provider-$(date -u +%Y%m%dT%H%M%SZ)"
```

All AWS resources created for the proof must include `${FLOE_PROVIDER_SPIKE_RUN}` in the name or tags.

### Readiness Checks

```bash
git status --short --branch
devpod list
aws sts get-caller-identity
aws s3api list-buckets --query 'Buckets[].Name' --output text
aws glue get-databases --max-results 1
```

Expected:

- Git branch is `main`.
- DevPod list is empty or has no current-run workspace.
- AWS caller identity succeeds.
- S3 and Glue list commands succeed with the intended test account.

### Product Validation Shape

The live proof should preserve these artifacts:

- Compiled artifact JSON.
- Resolver decision output.
- Runtime catalog connection projection.
- PyIceberg or runtime config derived from bindings.
- Live create/list/read/write output.
- Secret scan output for artifacts and logs.

### AWS Cleanup

Cleanup must verify these resource classes:

```bash
aws glue get-databases
aws glue get-tables --database-name "${FLOE_PROVIDER_SPIKE_RUN}"
aws s3api list-objects-v2 --bucket "${FLOE_PROVIDER_SPIKE_RUN}" --max-items 10
aws s3api head-bucket --bucket "${FLOE_PROVIDER_SPIKE_RUN}"
aws iam list-roles --query "Roles[?contains(RoleName, '${FLOE_PROVIDER_SPIKE_RUN}')].RoleName"
aws iam list-policies --scope Local --query "Policies[?contains(PolicyName, '${FLOE_PROVIDER_SPIKE_RUN}')].Arn"
```

Expected after cleanup:

- Glue database and tables created for the run are absent.
- S3 bucket or prefix created for the run is absent or empty and retained only if explicitly approved.
- IAM roles and policies created for the run are absent.
- Any external reusable credential or role is named in the final evidence and not deleted by the runbook.

## Fallback Lane: Nessie Plus MinIO

Use this lane when AWS access is unavailable or not safe for the first proof.

Expected proof:

- Nessie catalog service is deployed in the remote validation environment.
- MinIO remains the storage provider.
- Resolver accepts MinIO plus Nessie only when catalog requirements match storage capabilities.
- Runtime catalog connection is derived from deployment bindings.
- Iceberg table create/list/read/write succeeds.
- DevPod and Hetzner resources are directly inventoried after cleanup.

## DevPod And Hetzner Cleanup

Use the existing remote lane shape:

```bash
DEVPOD_WORKSPACE="${FLOE_PROVIDER_SPIKE_RUN}" DEVPOD_REMOTE_E2E_MAKE_TARGET=test-e2e-full make devpod-test
devpod list
```

Direct Hetzner inventory must check these resource classes for the current run prefix:

```bash
servers
volumes
ssh_keys
load_balancers
floating_ips
```

Final evidence must state whether each class has no current-run resources remaining.
```

- [ ] **Step 3: Commit the live runbook**

Run:

```bash
git add docs/validation/2026-05-11-provider-compatibility-live-runbook.md
git commit -m "docs: add provider compatibility live runbook"
```

Expected: commit succeeds and hooks pass.

## Task 5: Final Recommendation And Verification

**Files:**
- Read: `docs/validation/2026-05-11-provider-compatibility-system-map.md`
- Read: `docs/validation/2026-05-11-provider-compatibility-matrix.md`
- Read: `docs/validation/2026-05-11-provider-compatibility-gap-ledger.md`
- Read: `docs/validation/2026-05-11-provider-compatibility-live-runbook.md`
- Create: `docs/validation/2026-05-11-provider-compatibility-final-recommendation.md`

- [ ] **Step 1: Create the final recommendation artifact**

Create `docs/validation/2026-05-11-provider-compatibility-final-recommendation.md` with this structure:

```markdown
# Provider Compatibility Final Recommendation

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Purpose: Closeout recommendation for the provider compatibility spike.

## Evidence Artifacts

| Artifact | Role |
| --- | --- |
| `docs/validation/2026-05-11-provider-compatibility-system-map.md` | Implemented model and source map |
| `docs/validation/2026-05-11-provider-compatibility-matrix.md` | Provider matrix and Level decisions |
| `docs/validation/2026-05-11-provider-compatibility-gap-ledger.md` | Gap classification and next action |
| `docs/validation/2026-05-11-provider-compatibility-live-runbook.md` | Live AWS/Glue and Nessie/MinIO validation plan |

## Recommendation

Proceed with AWS S3 plus AWS Glue as the first provider compatibility implementation design if AWS credentials and cleanup controls are available. Otherwise proceed with Nessie plus MinIO as the first live proof while keeping AWS S3 plus Glue as the primary provider matrix target.

## First Implementation Unit

Recommended first implementation unit:

- Design native AWS S3 storage binding and AWS Glue catalog binding against the current composition model.
- Add resolver tests for AWS credential and identity modes.
- Add secret-free compiled artifact tests.
- Add runtime translator proof for PyIceberg Glue config derived from typed bindings.
- Keep live AWS validation behind the runbook readiness gate.

## Fallback Implementation Unit

Recommended fallback implementation unit:

- Design Nessie catalog binding that composes with existing MinIO storage binding.
- Add resolver tests for MinIO plus Nessie compatibility.
- Add runtime translator proof for Nessie Iceberg catalog config.
- Use the fallback live lane to validate catalog variation without AWS resources.

## Explicit Deferrals

- GCS and Azure remain design pressure tests until a concrete provider path exists.
- Hive remains deferred until a concrete deployment path exists.
- Deprecated compatibility helpers are not new provider contracts.
- Raw credentials in `CompiledArtifacts` remain forbidden.

## Closeout Status

The spike is complete when this document references all evidence artifacts and the worktree is clean after the final commit.
```

- [ ] **Step 2: Run Markdown and content validation**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
git diff --check
```

Expected:

- Docs navigation validation passes.
- Docs content validation passes.
- `git diff --check` prints no whitespace errors.

- [ ] **Step 3: Search for plan red flags in generated artifacts**

Run:

```bash
python - <<'PY'
from pathlib import Path

terms = [
    "T" + "BD",
    "TO" + "DO",
    "FIX" + "ME",
    "raw access" + " key",
    "raw secret" + " key",
    "hardcoded credential",
]
failed = False
for path in sorted(Path("docs/validation").glob("2026-05-11-provider-compatibility-*.md")):
    text = path.read_text()
    for line_no, line in enumerate(text.splitlines(), 1):
        for term in terms:
            if term in line:
                print(f"{path}:{line_no}: {term}: {line}")
                failed = True
if failed:
    raise SystemExit(1)
PY
```

Expected:

- No output for incomplete-work markers.
- If `raw access key`, `raw secret key`, or `hardcoded credential` appears, it appears only in a rule forbidding those patterns.

- [ ] **Step 4: Commit final recommendation**

Run:

```bash
git add docs/validation/2026-05-11-provider-compatibility-final-recommendation.md
git commit -m "docs: recommend provider compatibility path"
```

Expected: commit succeeds and hooks pass.

- [ ] **Step 5: Final closeout check**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected:

- Worktree is clean.
- Recent commits include the system map, matrix, gap ledger, live runbook, and final recommendation commits.

## Post-Plan Execution Notes

Use `superpowers:subagent-driven-development` for execution. Good task splits:

- Worker 1: Task 1 system map.
- Worker 2: Task 2 provider matrix.
- Worker 3: Task 3 gap ledger.
- Worker 4: Task 4 live runbook.
- Parent session: Task 5 final recommendation and validation, integrating prior artifacts.

Do not dispatch workers to modify the same evidence file concurrently.
