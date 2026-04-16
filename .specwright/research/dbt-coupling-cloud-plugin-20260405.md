# Research Brief: dbt Coupling & Cloud Plugin Feasibility

**Date**: 2026-04-05
**Tracks**: Architecture coupling audit, dbt Cloud API, plugin abstraction patterns
**Confidence**: HIGH (codebase audit + official docs)

## Track 1: Current dbt Coupling in floe

### Finding: dbt is PROPERLY ABSTRACTED, not tightly coupled

**Evidence:**

1. **Zero dbt imports in floe-core** — no `from dbt` or `import dbt` in `packages/floe-core/src/`
2. **Clean ABC** — `DBTPlugin` in `floe_core/plugins/dbt.py` (574 lines) defines abstract methods
   (`compile_project()`, `run_models()`, `test_models()`, etc.) with **generic return types**
   (Path, dict, dataclasses) — no dbt-core types leak into the interface
3. **Two plugin implementations** already exist:
   - `plugins/floe-dbt-core/` — wraps `dbtRunner` (lazy import)
   - `plugins/floe-dbt-fusion/` — alternative runtime
4. **floe-core has no dbt-core dependency** in its pyproject.toml
5. **CompiledArtifacts** uses `dbt_profiles: dict[str, Any] | None` — generic dict, not dbt types
6. **No `packages/floe-dbt/` exists** — dbt is plugin-only, not bundled

### Minor Boundary Issues (non-blocking)

| File | Issue | Severity |
|------|-------|----------|
| `compilation/dbt_test_mapper.py` | dbt-specific test type mappings in floe-core | LOW — compilation-time only |
| `compilation/dbt_profiles.py` | Generates profiles.yml in floe-core | ACCEPTABLE — uses ComputePlugin abstraction |
| `enforcement/validators/*.py` | Understands dbt manifest structure (dict parsing) | ACCEPTABLE — by design |

### Verdict

The `DBTPlugin` ABC is the correct abstraction point. A `floe-dbt-cloud` plugin
can implement it without touching floe-core.

---

## Track 2: dbt Cloud Administrative API

### Authentication
- **Service account tokens**: `Authorization: Token <service_token>` — preferred for programmatic access
- **PATs**: `Authorization: Bearer <pat>` — tied to user
- Both accepted interchangeably

### Core Job/Run Endpoints (v2)

| Operation | Method | URL |
|-----------|--------|-----|
| Trigger job | POST | `/api/v2/accounts/{id}/jobs/{id}/run/` |
| Get run status | GET | `/api/v2/accounts/{id}/runs/{id}/` |
| Get artifact | GET | `/api/v2/accounts/{id}/runs/{id}/artifacts/{path}` |

Run status codes: 1=Queued, 2=Scheduled, 3=Executing, 10=Success, 20=Failed, 30=Canceled

### Webhooks (event-driven alternative)
Events: `job.run.started`, `job.run.completed`, `job.run.errored`
Requires Starter or Enterprise plan.

### Discovery API (GraphQL)
Separate from Administrative API. Metadata queries (model health, lineage, test results).
Requires Starter or Enterprise plan.

**Source**: [dbt Cloud APIs](https://docs.getdbt.com/docs/dbt-cloud-apis/overview),
[OpenAPI spec](https://github.com/dbt-labs/dbt-cloud-openapi-spec)

---

## Track 3: dbt Cloud CLI vs dbt-core

| Capability | dbt-core | dbt Cloud CLI |
|---|---|---|
| `profiles.yml` required | Yes | No — server-side credentials |
| Parallel invocations | Not safe | Supported |
| Artifact deferral | Manual `--defer` | Automatic |
| Cross-project `ref()` | No | Yes |
| Offline execution | Yes | No — requires cloud connectivity |
| Local `manifest.json` | Generated locally | Must fetch via API |

**Critical for plugin design**: Cloud CLI offloads execution to cloud infrastructure.
Artifacts must be fetched via API (`/runs/{id}/artifacts/manifest.json`), not read
from local filesystem.

**Source**: [Cloud CLI docs](https://docs.getdbt.com/docs/cloud/cloud-cli-installation)

---

## Track 4: How Other Orchestrators Abstract dbt

### Common Pattern: Separate Implementations, No Shared ABC

| Platform | dbt-core path | dbt Cloud path | Shared interface? |
|----------|---------------|----------------|-------------------|
| **Dagster** | `DbtCliResource` | `DbtCloudWorkspace` + polling sensor | **No** |
| **Airflow** | `BashOperator`/`PythonOperator` | `DbtCloudRunJobOperator` + `DbtCloudJobRunSensor` | **No** |
| **Prefect** | `DbtCoreOperation` block | `DbtCloudJob` block | **No** |

All three converge on: **trigger job via v2 API → poll for completion → fetch artifacts**.
None define a shared ABC that both implementations satisfy.

**floe is ahead here**: The `DBTPlugin` ABC already provides a shared interface that
both `floe-dbt-core` and a future `floe-dbt-cloud` can implement.

**Source**: [Dagster dbt Cloud](https://docs.dagster.io/integrations/libraries/dbt/dbt-cloud),
[Airflow dbt Cloud](https://airflow.apache.org/docs/apache-airflow-providers-dbt-cloud/stable/operators.html)

---

## Track 5: dbt Cloud Semantic Layer

### API Surface
- GraphQL, JDBC (ArrowFlightSQL), Python SDK
- Region-dependent endpoints (NA, EMEA, APAC)
- Requires Starter or Enterprise plan

### Self-hosted MetricFlow vs Cloud Semantic Layer
- MetricFlow (dbt-core): CLI-only (`mf query`), no network API
- Cloud Semantic Layer: Full GraphQL/JDBC APIs, downstream tool integrations

**Implication**: `SemanticLayerPlugin` implementations for dbt Cloud would use the
GraphQL API; self-hosted would use MetricFlow library calls.

---

## Synthesis: What's Needed for floe-dbt-cloud Plugin

### Plugin would implement existing `DBTPlugin` ABC:

```
plugins/floe-dbt-cloud/
  src/floe_dbt_cloud/
    plugin.py        # DBTPlugin implementation
    api_client.py    # dbt Cloud v2 API wrapper
    config.py        # Pydantic config (account_id, job_id, token)
  tests/
    unit/
    integration/
```

### Method mapping:

| DBTPlugin method | dbt Cloud implementation |
|-----------------|------------------------|
| `compile_project()` | Trigger job → poll → fetch `manifest.json` artifact |
| `run_models()` | Trigger job → poll → fetch `run_results.json` |
| `test_models()` | Trigger job with test step → poll → fetch results |
| `get_manifest()` | Fetch `/runs/{id}/artifacts/manifest.json` |
| `get_run_results()` | Fetch `/runs/{id}/artifacts/run_results.json` |

### No floe-core changes needed — the ABC is already dbt-agnostic.

---

## Open Questions

1. Should `floe-dbt-cloud` also implement `SemanticLayerPlugin` for the Cloud Semantic Layer API?
2. Webhook-driven run monitoring vs polling — which pattern for the plugin?
3. Plan tier requirements: Starter/Enterprise for Discovery API and Semantic Layer — document in manifest.yaml?
