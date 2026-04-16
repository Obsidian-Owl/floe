# Design: E2E Alpha Stability — Closing the Last 7 Failures

**Status**: PROPOSED
**Branch**: `feat/e2e-alpha-stability`
**Research**: `.specwright/research/e2e-alpha-stability-20260327.md`

---

## Problem Statement

The E2E suite passes 223/230 tests (96.5%). The 7 remaining failures fall into two categories:

- **4 production code bugs**: Dagster materialization (profiles.yml path), OpenLineage parentRun facet wiring, requests CVE sync gap
- **3 infra/timing flakes**: Helm pre-upgrade hook image-pull timeout cascading to 3 upgrade tests

All 7 have identified root causes. None require architectural changes. This design addresses them as durable, long-term fixes — not band-aids.

---

## Approach

### Guiding Principle

Every fix must be **self-maintaining**: it should not require manual intervention when dependencies update, chart versions bump, or CI environments change. Where a fix addresses a symptom, the design also addresses the root cause.

### Fix Summary

| ID | Fix | Tests Fixed | Approach | Self-Maintaining? |
|----|-----|-------------|----------|-------------------|
| A | Add `GHSA-gc5v-m9x4-r6x2` to `.vuln-ignore` | #4 | Sync gap fix | Yes (until upstream unblocks bump) |
| B | Change `profiles.yml` `path` to `:memory:` in 3 demos | #1, #2 | Align baked profile with compiled output | Yes |
| C | Wire `context.run.run_id` as parent in `plugin.py` | #3 | One-line caller fix | Yes |
| D | Replace `bitnami/kubectl` hook with `curlimages/curl` + K8s REST API | #5, #6, #7 | Eliminate image-pull dependency | Yes |

---

## Fix A: requests CVE Sync Gap

### What

Add `GHSA-gc5v-m9x4-r6x2` to `.vuln-ignore` with rationale comment.

### Why

`test_pip_audit_clean` reads `.vuln-ignore`, not `pyproject.toml`. The CVE is already documented and accepted in `pyproject.toml` (lines 233-238) with rationale: not exploitable because floe never calls `extract_zipped_paths()`. The `.vuln-ignore` file was simply never updated.

### How

```
# requests 2.32.5 — GHSA-gc5v-m9x4-r6x2 (not exploitable, extract_zipped_paths unused)
# Blocked by datacontract-cli <2.33 pin. Track: upstream issue on datacontract-cli.
GHSA-gc5v-m9x4-r6x2
```

### Long-term

Open an upstream issue on `datacontract-cli` to relax the `requests<2.33` pin. When unblocked, bump requests and remove the ignore entry. Track via GitHub issue with `tech-debt` label.

### Risk: NONE

This is purely a synchronization fix. The justification already exists.

---

## Fix B: Demo profiles.yml DuckDB Path

### What

Change `path: "target/demo.duckdb"` to `path: ":memory:"` in all 3 demo products:
- `demo/customer-360/profiles.yml`
- `demo/iot-telemetry/profiles.yml`
- `demo/financial-risk/profiles.yml`

### Why

K8s run pods have `readOnlyRootFilesystem: true` (security hardening). When dbt executes in-cluster, it reads `profiles.yml` which says `path: "target/demo.duckdb"` — a writable file path. DuckDB tries to create this file and fails.

The compiled artifacts already produce `path: ":memory:"` (validated by `test_dbt_profile_correct_for_in_cluster_execution`), but the actual `profiles.yml` baked into the Docker image was never aligned.

### How

Each `profiles.yml` changes one line:

```yaml
# Before
path: "target/demo.duckdb"

# After
path: ":memory:"
```

DuckDB `:memory:` mode has no filesystem requirement and is correct for ephemeral compute (K8s jobs that write to Iceberg, not local files).

### Why this is sufficient

The auto-generated `definitions.py` uses `DbtCliResource(profiles_dir=PROJECT_DIR)`, which reads `profiles.yml` from the demo product directory at runtime. The Dockerfile copies demo directories (including `profiles.yml`) into the image as-is. So the baked-in `profiles.yml` IS the file that dbt reads in-cluster. Changing it to `:memory:` directly fixes the runtime behavior.

### Long-term

The plugin generator (`plugin.py:~1198`) should write a K8s-specific `profiles.yml` into the Docker image at build time, using the compiled artifacts' profile values. This ensures the baked profile always matches the compiled output, even for non-demo products. Track via GitHub issue with `enhancement` label.

### Risk: LOW

DuckDB `:memory:` is well-supported. The compiled artifacts already use it. This aligns the source profile with what was always intended.

### Cascading Impact

Fixes both #1 (`test_trigger_asset_materialization`) and #2 (`test_iceberg_tables_exist_after_materialization`).

---

## Fix C: OpenLineage parentRun Facet Wiring

### What

In `plugin.py:582`, pass the Dagster orchestrator run ID instead of the asset-level OpenLineage UUID as the parent run ID for per-model lineage events.

### Why

`extract_dbt_model_lineage()` receives `run_id` — the UUID returned by `lineage.emit_start()`. This is an asset-level OpenLineage UUID, not the Dagster orchestrator run ID (`context.run.run_id`). The OpenLineage ParentRunFacet spec requires the actual parent orchestrator run ID to tie per-model events into the Dagster run lineage graph.

The facet builder (`ParentRunFacetBuilder.from_parent()`) and extraction function are both correctly implemented. Only the caller passes the wrong ID.

### How

```python
# plugin.py, in _asset_fn(), around line 582
# Before (wrong — asset-level OpenLineage UUID):
events = extract_dbt_model_lineage(
    result.project_dir, run_id, model_name, lineage.namespace
)

# After (correct — Dagster orchestrator run ID):
from uuid import UUID as _UUID
dagster_parent_id = _UUID(context.run.run_id)
events = extract_dbt_model_lineage(
    result.project_dir, dagster_parent_id, model_name, lineage.namespace
)
```

### Why `context.run.run_id`?

- `context.run.run_id` is the Dagster pipeline run UUID — it's the true orchestrator parent
- All per-model OpenLineage events should reference this as their `parentRun` so lineage tools (Marquez, DataHub) can reconstruct the full execution tree
- `run_id` from `emit_start()` is the per-asset lineage UUID, which is a *sibling* concept, not a parent

### Risk: LOW

One-line change. The UUID conversion is safe (Dagster run IDs are valid UUIDs). The downstream facet builder already handles the `UUID` type correctly.

### Testing

Existing `test_openlineage_four_emission_points` validates the parentRun facet presence via Marquez API. The fix makes this test pass by providing the correct parent ID.

---

## Fix D: Helm Pre-Upgrade Hook — Replace bitnami/kubectl with curl + K8s REST API

### What

Replace the `bitnami/kubectl:1.32.0` container in the pre-upgrade hook with `curlimages/curl:8.5.0` using the K8s REST API directly for StatefulSet deletion.

### Why (3 compounding problems)

1. **Image pull latency**: `bitnami/kubectl` is a separate image. In Kind/CI, image pull can exceed `activeDeadlineSeconds`, leaving the release stuck in `pending-upgrade`.
2. **Bitnami supply chain risk**: Bitnami has stopped publishing new kubectl tags ([bitnami/charts#36357](https://github.com/bitnami/charts/issues/36357)). This will break when K8s advances past 1.32.
3. **`pending-upgrade` is sticky**: Helm 3 known issue ([helm/helm#7476](https://github.com/helm/helm/issues/7476)) — once stuck, requires manual rollback.

### Why curl specifically?

- `curlimages/curl:8.5.0` is **already pre-loaded** into Kind by `setup-cluster.sh:135`
- It's a minimal, distroless image (~5MB) maintained by the curl project
- The K8s API for StatefulSet deletion is a single REST call — no kubectl binary needed
- No supply chain dependency on Bitnami

### How — New hook script

```bash
set -e
TOKEN="$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)"
CACERT="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
API="https://kubernetes.default.svc"
STS_NAME="{{ include "floe-platform.fullname" . }}-postgresql"
NS="{{ .Release.Namespace }}"

# Check if StatefulSet exists (GET returns 404 if not)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  --cacert "${CACERT}" \
  "${API}/apis/apps/v1/namespaces/${NS}/statefulsets/${STS_NAME}")

if [ "${HTTP_CODE}" = "200" ]; then
  echo "Deleting StatefulSet ${STS_NAME} (orphan pods/PVCs)..." >&2
  curl -sSf -X DELETE \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    --cacert "${CACERT}" \
    -d '{"propagationPolicy":"Orphan"}' \
    "${API}/apis/apps/v1/namespaces/${NS}/statefulsets/${STS_NAME}"
  echo "StatefulSet deleted. Pods and PVCs preserved." >&2
elif [ "${HTTP_CODE}" = "404" ]; then
  echo "StatefulSet ${STS_NAME} not found -- no cleanup needed." >&2
else
  echo "ERROR: Unexpected HTTP ${HTTP_CODE} checking StatefulSet" >&2
  exit 1
fi
```

### Template changes

```yaml
# values.yaml — change default image
preUpgradeCleanup:
  enabled: false
  activeDeadlineSeconds: 300
  image:
    repository: curlimages/curl
    tag: "8.5.0"
```

```yaml
# pre-upgrade-statefulset-cleanup.yaml — update command
containers:
  - name: cleanup
    image: "{{ .Values.postgresql.preUpgradeCleanup.image.repository }}:{{ .Values.postgresql.preUpgradeCleanup.image.tag }}"
    command:
      - /bin/sh
      - -c
      - |
        <curl-based script above>
```

### RBAC unchanged

The existing Role already grants `get`, `list`, `watch`, `delete` on `statefulsets` in the `apps` API group. The K8s REST API uses the same RBAC — the ServiceAccount token carries the same permissions. No RBAC changes needed.

### Security context unchanged

- `readOnlyRootFilesystem: true` — curl needs no writable filesystem (the tmp volume handles any needed scratch)
- `runAsNonRoot: true`, `runAsUser: 1000` — curl image supports non-root
- `allowPrivilegeEscalation: false`, drop `ALL` capabilities — unchanged

### setup-cluster.sh changes

Remove `bitnami/kubectl:1.32.0` from the pre-load list. `curlimages/curl:8.5.0` is already pre-loaded.

### Helm unit test changes

Update `hook-pre-upgrade_test.yaml`:
- AC-7 test: change `matchRegex` patterns from kubectl commands to curl-based script patterns
- Verify the script references `floe-platform-postgresql` and `propagationPolicy.*Orphan`

### Risk: LOW-MEDIUM

- The K8s REST API for StatefulSet deletion is stable (apps/v1, GA since K8s 1.9)
- `propagationPolicy: Orphan` is the REST API equivalent of `--cascade=orphan`
- The ServiceAccount token is automatically mounted (`automountServiceAccountToken: true`)
- **Risk factor**: The curl image's entrypoint and shell path (`/bin/sh`) — verified in curlimages/curl docs

### Long-term: Eliminate hook entirely

The `immutableLabels` helper already excludes `helm.sh/chart` and `app.kubernetes.io/version` from VCT labels. The hook is only needed when `commonLabels` values change (not on regular chart upgrades). Long-term, document this clearly and consider defaulting `preUpgradeCleanup.enabled: false` with explicit opt-in only when `commonLabels` are modified.

### Cascading Impact

Fixes all 3 Helm failures (#5, #6, #7).

---

## Blast Radius

| Module/File | Change Type | Failure Propagation |
|-------------|-------------|---------------------|
| `.vuln-ignore` | Add entry | LOCAL — only affects pip-audit test |
| `demo/*/profiles.yml` (3 files) | Config change | LOCAL — only affects demo products in-cluster |
| `plugin.py:582` | Caller argument | ADJACENT — affects per-model lineage events; facet builder + extraction unchanged |
| `pre-upgrade-statefulset-cleanup.yaml` | Template rewrite | LOCAL — hook only runs during `helm upgrade` |
| `values.yaml` | Default image change | LOCAL — only affects hook image |
| `setup-cluster.sh` | Remove pre-load | LOCAL — only affects Kind setup |
| `hook-pre-upgrade_test.yaml` | Test update | LOCAL — helm unit tests |

**What this design does NOT change:**
- Dagster plugin architecture, asset creation, or resource management
- OpenLineage facet builders, emission pipeline, or Marquez integration
- Helm chart structure, RBAC model, or PostgreSQL StatefulSet template
- VolumeClaimTemplate labels or `immutableLabels` helper
- E2E test assertions or test infrastructure (test-e2e.sh, conftest.py)
- Any Python package code outside `plugin.py:582`

---

## Implementation Phases

### Phase 1: Quick Wins (~1 day, eliminates 4/7 failures)

| Unit | Fix | Tests Fixed | Effort |
|------|-----|-------------|--------|
| 1 | Fix A (`.vuln-ignore`) + Fix B (`profiles.yml` x3) | #1, #2, #4 | 30 min |
| 2 | Fix C (parentRun wiring in `plugin.py`) | #3 | 30 min |

### Phase 2: Helm Resilience (~1 day, eliminates 3/7 failures)

| Unit | Fix | Tests Fixed | Effort |
|------|-----|-------------|--------|
| 3 | Fix D (curl hook + values + setup-cluster + tests) | #5, #6, #7 | 1 day |

### Phase 3: Long-term (future PRs, tracked via issues)

| Item | Benefit | Tracking |
|------|---------|----------|
| Upstream `datacontract-cli` issue for `requests>=2.33` | Remove CVE ignore | GitHub issue |
| Plugin generator writes K8s-specific `profiles.yml` at build | Profile/compilation alignment | GitHub issue |
| Document hook as opt-in for `commonLabels` changes only | Reduce hook usage | README/chart docs |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| curl image shell path differs from expected | LOW | Verify with `docker run curlimages/curl:8.5.0 sh -c 'echo ok'` |
| K8s REST API auth fails in Kind | LOW | ServiceAccount token + RBAC already proven with kubectl approach |
| DuckDB `:memory:` behaves differently than file mode for demos | LOW | Already validated by compiled artifacts test |
| `context.run.run_id` not a valid UUID in edge cases | LOW | Dagster guarantees UUID format for run IDs |

---

## Architect Review WARNs (addressed)

### WARN-1: Shell `[ ]` vs `[[ ]]` in hook script

The code-quality rules require `[[ ]]` for bash conditionals. However, the hook script runs under `/bin/sh` (busybox on Alpine-based `curlimages/curl`), which does not support `[[`. Resolution: use `[ ]` intentionally and add a comment `# POSIX sh — [[ ]] not available in busybox` to document the deviation.

### WARN-2: Dual-ID pattern in Fix C

The design changes the parent ID for `extract_dbt_model_lineage()` but not for `lineage.emit_start/fail/complete()`. This is semantically correct: the asset-level OL UUID tracks the lifecycle of the overall asset execution, while per-model events reference the Dagster run as their parent (per OpenLineage ParentRunFacet spec). Add a comment at the call site explaining this dual-ID pattern.

### WARN-2b: Dagster run_id format

`context.run.run_id` is a hex-hyphenated UUID string (standard UUID format). If it ever weren't, `UUID()` would raise `ValueError`, caught by the `except Exception` handler at line 587 — lineage extraction would be skipped with a warning log, not crash.

---

## Open Questions

1. Should Phase 3 items be tracked in Linear or GitHub issues? (Depends on team workflow preference)
2. Is `curlimages/curl:8.5.0` the right pin, or should we use a newer tag? (8.5.0 is already in setup-cluster.sh)
