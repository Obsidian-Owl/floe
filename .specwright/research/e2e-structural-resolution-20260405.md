# Research Brief: E2E Structural Resolution — Permanent Fixes for Recurring Failures

**Date:** 2026-04-05
**Confidence:** HIGH (official docs, GitHub issues, codebase analysis, multiple sources per track)
**Tracks:** 4 (+1 config chain analysis)

---

## Executive Summary

The 8 recurring E2E failures stem from 4 structural root causes, not random bugs. Each has a permanent resolution that eliminates the failure class entirely — no patches, no retries, no workarounds.

| Root Cause | Failure Count | Permanent Fix | Effort |
|---|---|---|---|
| DuckDB Iceberg DROP CASCADE | 4 tests | PyIceberg `purge_table` + S3 prefix cleanup | Small |
| Polaris in-memory state loss | 2 tests | Switch to PostgreSQL persistence (already deployed) | Small |
| Host-to-K8s connectivity | 1 test | In-cluster test runner pod (K8s Job) | Medium |
| Template lineage gap | 1 test | Generate `emit_start`/`emit_complete` in template | Small |

Cross-cutting: **Config propagation has 5 divergence points** across an 8-hop chain. Manifest must be the single source of truth — test infrastructure must read from compiled artifacts, not re-extract or hardcode.

---

## Track 1: DuckDB Iceberg DROP TABLE CASCADE

### Problem

DuckDB's Iceberg extension does NOT support `DROP TABLE CASCADE`. dbt emits this for `--full-refresh` and `materialized='table'` re-runs. The current pre-purge via `catalog.drop_table()` clears the Polaris catalog entry but leaves all parquet data and metadata JSON files in MinIO. When dbt re-seeds, DuckDB may encounter stale file references causing HTTP 404 errors.

**Affected tests:** `test_dbt_seed`, `test_dbt_run`, `test_incremental_model_merge`, `test_pipeline_retry`

### Root Cause Chain

1. dbt-duckdb emits `DROP TABLE IF EXISTS ... CASCADE` → DuckDB Iceberg extension rejects CASCADE
2. Current purge uses `catalog.drop_table(fqn)` which sends `purgeRequested=false` → metadata/data files persist in MinIO
3. Polaris has open bugs (#1195, #1448) where even `purgeRequested=true` fails to delete metadata files
4. dbt-duckdb incremental materialization for Iceberg external tables is **not implemented** (dbt-duckdb issue #74)

### Permanent Resolution

**Two-layer cleanup:**

1. **Switch from `drop_table` to `purge_table`** in `_purge_iceberg_namespace()`:
   ```python
   catalog.purge_table(fqn)  # sends purgeRequested=true
   ```

2. **Supplement with direct S3 prefix deletion** (because Polaris purge is unreliable per issues #1195, #1448):
   ```python
   import boto3
   s3 = boto3.client('s3', endpoint_url=minio_url)
   prefix = f"{namespace}/{table_name}/"
   objects = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
   if 'Contents' in objects:
       s3.delete_objects(Bucket=bucket, Delete={
           'Objects': [{'Key': obj['Key']} for obj in objects['Contents']]
       })
   ```

3. **Drop namespace after all tables purged** (already implemented in PR #227).

**Confidence:** HIGH — Official PyIceberg API, confirmed Polaris bugs with issue numbers.

### Sources

- [DuckDB Iceberg issue #784: CREATE OR REPLACE TABLE](https://github.com/duckdb/duckdb-iceberg/issues/784)
- [DuckDB Iceberg issue #785: Issues on Dropping Table](https://github.com/duckdb/duckdb-iceberg/issues/785)
- [dbt-duckdb issue #74: Incremental external models](https://github.com/duckdb/dbt-duckdb/issues/74)
- [Polaris issue #289: purge doesn't delete metadata files](https://github.com/apache/polaris/issues/289)
- [Polaris issue #1195: varchar(255) overflow in cleanup tasks](https://github.com/apache/polaris/issues/1195)
- [Polaris issue #1448: purge=true leaves metadata files](https://github.com/apache/polaris/issues/1448)
- [Apache Iceberg issue #3541: No CASCADE for drop_namespace](https://github.com/apache/iceberg/issues/3541)
- [PyIceberg PR #2086: REST purgeRequested parameter](https://www.mail-archive.com/commits@iceberg.apache.org/msg16728.html)

---

## Track 2: Polaris In-Memory State Loss

### Problem

Polaris uses in-memory persistence by default. Pod restart loses ALL catalog state (namespaces, tables, grants). The Helm bootstrap Job only fires on `post-install` / `post-upgrade` hooks — NOT on pod restart. After a crash/restart mid-suite, Polaris is healthy (`/q/health/ready` returns 200) but all catalogs and grants are gone. 73+ minute test suites make restarts likely.

**Affected tests:** `test_trigger_asset_materialization`, `test_iceberg_tables_exist_after_materialization`

### Root Cause

The `values-test.yaml` configures Polaris with the default `in-memory` persistence type. The official Polaris docs explicitly state: *"Data will be lost when pods restart and you cannot run multiple replicas."*

### Permanent Resolution

**Switch to `relational-jdbc` persistence using the existing PostgreSQL instance.**

The `floe-platform-postgresql` StatefulSet is already deployed in the test environment. Required changes:

1. **Create K8s secret** for Polaris JDBC connection:
   ```bash
   kubectl create secret generic polaris-persistence \
     --namespace floe-test \
     --from-literal=username=polaris \
     --from-literal=password=polaris \
     --from-literal=jdbcUrl=jdbc:postgresql://floe-platform-postgresql:5432/polaris
   ```

2. **Update `values-test.yaml`** persistence block:
   ```yaml
   polaris:
     persistence:
       type: relational-jdbc
       relationalJdbc:
         secret:
           name: "polaris-persistence"
           username: "username"
           password: "password"
           jdbcUrl: "jdbcUrl"
   ```

3. **Add Polaris database** to PostgreSQL init (or let Quarkus auto-create on first boot).

**Impact:** State survives pod restarts. No re-bootstrap needed. Startup adds 5-15 seconds for JDBC connection + schema migration. Bootstrap Job remains idempotent — safe to run on upgrades.

**Confidence:** HIGH — Official Polaris documentation, confirmed PostgreSQL already deployed.

### Sources

- [Persistence | Apache Polaris Helm Chart](https://polaris.apache.org/in-dev/unreleased/helm-chart/persistence/)
- [Relational JDBC | Apache Polaris](https://polaris.apache.org/in-dev/unreleased/metastores/relational-jdbc/)
- [Production Configuration | Apache Polaris](https://polaris.apache.org/in-dev/unreleased/helm-chart/production/)
- [Development & Testing | Apache Polaris](https://polaris.apache.org/in-dev/unreleased/helm-chart/dev/)

---

## Track 3: Host-to-K8s Connectivity (E2E Architecture)

### Problem

E2E tests run on the HOST, connecting to K8s services via 8+ port-forwards across 4+ network hops. 71% of failures (27 of 38) are TCP connection timeouts from port-forward deaths. `kubectl port-forward` is officially positioned as a development/debugging tool, not a production connectivity mechanism. It has no auto-reconnect, dies on pod restart, and suffers idle timeouts.

Additionally, PyIceberg's REST catalog `_fetch_config` merge has server-side overrides ALWAYS WIN — Polaris returns K8s-internal S3 hostnames that the host cannot resolve. This is **architectural**, not a configuration bug.

**Affected test:** `test_make_demo_completes` (K8s DNS `floe-platform-polaris` unreachable from host)

### Three Options (Ranked)

#### Option A: In-Cluster Test Runner Pod (Recommended)

Run pytest as a K8s Job inside the cluster. All services reachable via K8s DNS. No port-forwards. No S3 endpoint mismatch.

**Pattern:**
1. Build test Docker image with pytest + test suite
2. Submit as K8s Job: `kubectl apply -f test-job.yaml`
3. Wait: `kubectl wait --for=condition=complete --timeout=30m job/e2e-tests`
4. Extract results: `kubectl logs job/e2e-tests` + JUnit XML via PVC or `kubectl cp`
5. Read exit code from `.status.succeeded`

**Tradeoff:** Requires building/pushing test image per run. Mitigated by Docker layer caching.

**Used by:** Testkube (CNCF), Eficode CI pipeline guide, multiple production K8s projects.

#### Option B: Kind extraPortMappings (Partial Fix)

Define port mappings at cluster creation time. Stable Docker-level binding, not a kubectl process. Does NOT fix the PyIceberg S3 endpoint override problem.

```yaml
kind: Cluster
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 8181
        hostPort: 8181  # Polaris
      - containerPort: 9000
        hostPort: 9000  # MinIO
```

**Limitation:** Ports must be known at cluster creation. Does not solve K8s DNS or PyIceberg config merge.

#### Option C: mirrord Process Injection (Alternative)

`mirrord exec -- pytest` wraps the pytest process, intercepting syscalls and routing them through a temporary agent pod. No root required. Resolves K8s DNS from host. Supports env var injection.

**Tradeoff:** Alpha-to-production maturity. Requires `LD_PRELOAD`/`DYLD_INSERT_LIBRARIES`. May not work in all CI environments.

### Recommendation

**Option A (in-cluster test runner)** permanently eliminates the entire connectivity failure class. It also resolves the PyIceberg S3 endpoint override problem (ARC-003 in AUDIT) because the test process sees the same network as Polaris.

**Confidence:** HIGH — Official Kubernetes docs, CNCF patterns, confirmed by Testkube and polaris-local-forge projects.

### Sources

- [Kubernetes: Port Forward Access](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/)
- [Kubernetes Blog: Comparing Telepresence, Gefyra, mirrord (Sept 2023)](https://kubernetes.io/blog/2023/09/12/local-k8s-development-tools/)
- [Eficode/CNCF: Testing K8s Deployments in CI](https://www.cncf.io/blog/2020/06/17/testing-kubernetes-deployments-within-ci-pipelines/)
- [Testkube: In-Cluster Test Execution](https://testkube.io/glossary/in-cluster-test-execution)
- [inlets.dev: Fixing kubectl port-forward](https://inlets.dev/blog/2022/06/24/fixing-kubectl-port-forward.html)
- [kubectl issue #78446: port-forward doesn't recover](https://github.com/kubernetes/kubernetes/issues/78446)
- [Snowflake polaris-local-forge: split endpoint problem](https://github.com/Snowflake-Labs/polaris-local-forge)

---

## Track 4: OpenLineage Template Generation Gap

### Problem

Template-generated `definitions.py` files (used by all 3 demo products) do NOT emit OpenLineage events. The `lineage` resource is wired as a Dagster resource but the asset function never calls it. `emit_start()`/`emit_complete()` only exist in the dynamic asset creation path (`plugin.py:557-616`).

Additionally, the codebase uses `"parentRun"` as the facet key (`lineage_extraction.py:240`) but the OpenLineage spec renamed this to `"parent"`. Marquez stores whatever key arrives, so the E2E test querying for `"parent"` finds nothing.

**Affected test:** `test_openlineage_four_emission_points`

### Permanent Resolution

**Two fixes:**

1. **Fix facet key**: Change `"parentRun"` to `"parent"` in `lineage_extraction.py:240` to match the OpenLineage spec.

2. **Add lineage emission to generated template**: The template at `plugin.py:1344-1351` must:
   - Declare `lineage` as a resource parameter in the asset function
   - Call `lineage.emit_start(model_name, run_facets={"traceCorrelation": ...})` before `dbt.cli()`
   - Call `lineage.emit_complete(run_id, model_name)` after successful build
   - Call `extract_dbt_model_lineage()` to emit per-model events with parent context

   This mirrors the existing dynamic path in `plugin.py:556-618`.

**Confidence:** HIGH — OpenLineage spec confirmed key rename, codebase analysis confirmed template gap.

### Sources

- [OpenLineage ParentRunFacet spec](https://openlineage.io/docs/spec/facets/run-facets/parent_run/)
- [OpenLineage dbt integration](https://openlineage.io/docs/integrations/dbt/)
- [Marquez API: run facets](https://marquezproject.ai/docs/api/get-facets/)

---

## Track 5: Config Propagation Chain (Cross-Cutting)

### Problem

Config values pass through an 8-hop chain with 5 divergence points:

| Hop | Location | Model | Risk |
|---|---|---|---|
| 1 | `demo/manifest.yaml` | Plain YAML | Source of truth |
| 1B | `test-e2e.sh:460-476` | Shell env vars | **DIVERGES**: Hardcodes K8s hostnames |
| 2 | `floe_spec.py` | FloeSpec | Intentionally env-agnostic (no config) |
| 3 | `compiled_artifacts.py` | PluginRef.config dict | First Pydantic validation |
| 4 | `config.py` | PolarisCatalogConfig | S3 endpoint NOT in this schema |
| 5 | `plugin.py:270-299` | catalog_config dict | Additional config merged from connect() |
| 6 | PyIceberg REST | Server response | **DIVERGES**: Server overrides ALWAYS WIN |
| 7 | `manager.py:206-213` | IcebergTableManagerConfig | S3 comes from Polaris, not manifest |
| 8 | `conftest.py:54-60` | dict[str, str] | **DIVERGES**: Hardcodes `warehouse: "floe-e2e"` vs manifest `"floe-demo"` |

### Key Divergences

1. **test-e2e.sh line 476**: `'table-default.s3.endpoint': MINIO_ENDPOINT` hardcodes K8s-internal hostname. This server-side override is what makes client S3 config invisible.

2. **conftest.py line 59**: Fallback `warehouse: "floe-e2e"` differs from manifest's `warehouse: floe-demo`.

3. **Polaris server config always wins**: PyIceberg `_fetch_config` merge order is `server_defaults < client_props < server_overrides`. The `table-default.*` properties set by `test-e2e.sh` override any client-side S3 config.

### Permanent Resolution

**Manifest as single source of truth:**

1. Test infrastructure must read compiled artifacts (Hop 3), never re-extract from manifest or hardcode values.
2. Polaris bootstrap script (`test-e2e.sh`) must read S3 endpoint from manifest config, not hardcode K8s hostnames.
3. Remove hardcoded fallbacks in `conftest.py` — if manifest is missing, fail early with a clear error.
4. For in-cluster test runner (Track 3 Option A), the S3 endpoint divergence becomes moot — test process and Polaris see the same network.

**Confidence:** HIGH — Codebase analysis with exact file:line references.

---

## Synthesis: Resolution Priority

### Phase 1: Quick Wins (Small effort, eliminates 5 of 8 failures)

1. **Switch `drop_table` to `purge_table` + S3 prefix cleanup** → Fixes 4 DuckDB/Iceberg failures
2. **Fix `"parentRun"` → `"parent"` facet key** → Partially fixes lineage test
3. **Add lineage emission to generated template** → Fully fixes lineage test

### Phase 2: Infrastructure (Medium effort, eliminates remaining 3 failures + prevents recurrence)

4. **Switch Polaris to PostgreSQL persistence** → Fixes 2 Polaris state-loss failures
5. **Config single-source-of-truth** → Remove hardcoded values in test-e2e.sh and conftest.py

### Phase 3: Architecture (Larger effort, eliminates the entire connectivity failure class)

6. **In-cluster test runner pod** → Eliminates port-forward failures (71% of all E2E failures), resolves PyIceberg S3 endpoint override, removes K8s DNS unreachability from host

---

## Open Questions

1. **PyIceberg version**: Does the installed PyIceberg version (0.11.0rc2) support `purge_table`? The method was added in PR #2086 (June 2025). Need to verify.
2. **Polaris PostgreSQL schema**: Does the existing `floe-platform-postgresql` have capacity for an additional database? Need to check StatefulSet resource limits.
3. **Test Docker image**: What base image and dependencies are needed for the in-cluster test runner? The `testing/` framework (21K lines) would need to be included.
4. **CI pipeline changes**: In-cluster test runner requires `kubectl apply` + `kubectl wait` instead of `pytest` directly. The Makefile and CI workflows need updating.
