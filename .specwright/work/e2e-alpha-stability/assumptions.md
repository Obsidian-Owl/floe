# Assumptions: E2E Alpha Stability

## Resolved (Type 1 — structural, auto-accepted)

### A1: DuckDB `:memory:` mode is functionally equivalent for demo workloads
- **Classification**: Technical, auto-accepted
- **Evidence**: Compiled artifacts already produce `:memory:` (test validates this). DuckDB docs confirm full SQL support in memory mode. Demo products write to Iceberg (not DuckDB files).
- **Status**: ACCEPTED

### A2: `context.run.run_id` is always a valid UUID
- **Classification**: Technical, auto-accepted
- **Evidence**: Dagster source code generates UUIDs for all run IDs. Dagster docs confirm `run_id` is a UUID string. `UUID()` constructor will raise `ValueError` if invalid, caught by existing exception handler at line 587.
- **Status**: ACCEPTED

### A3: K8s REST API for StatefulSet deletion is stable
- **Classification**: Technical, auto-accepted
- **Evidence**: `apps/v1` API group is GA since K8s 1.9 (2017). The DELETE verb with `propagationPolicy` is part of the stable API. No deprecation signals.
- **Status**: ACCEPTED

### A4: `curlimages/curl:8.5.0` supports `/bin/sh` and runs as non-root
- **Classification**: Technical, auto-accepted
- **Evidence**: curlimages/curl is based on Alpine, includes `/bin/sh`. Image supports `--user` flag. Already pre-loaded in Kind cluster.
- **Status**: ACCEPTED (verify empirically during implementation)

### A5: ServiceAccount token is automatically available when `automountServiceAccountToken: true`
- **Classification**: Technical, auto-accepted
- **Evidence**: K8s docs confirm token mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`. Already used implicitly by kubectl in current hook.
- **Status**: ACCEPTED

## Deferred (Type 2 — external/future, backlogged)

### A6: `datacontract-cli` will relax `requests<2.33` pin
- **Classification**: External dependency, deferred
- **Tracking**: GitHub issue to be created
- **Impact**: Until resolved, `GHSA-gc5v-m9x4-r6x2` stays in `.vuln-ignore`
- **Status**: DEFERRED to backlog

### A7: Hook can be fully eliminated via VCT label documentation
- **Classification**: Process/docs, deferred
- **Evidence**: `immutableLabels` already excludes chart version from VCT. Hook only needed for `commonLabels` changes. Could be documented as opt-in only.
- **Tracking**: Phase 3 item
- **Status**: DEFERRED to backlog

### A8: Plugin generator should write K8s-specific profiles.yml
- **Classification**: Enhancement, deferred
- **Evidence**: Current gap between source `profiles.yml` and compiled output is a one-time sync issue for demos. For custom products, the same gap could recur.
- **Tracking**: Phase 3 item
- **Status**: DEFERRED to backlog
