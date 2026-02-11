# Context: Test Hardening Audit + E2E Brutalization

## Epic Context

This is a continuation of Epic 14: Quality Hardening Audit. Since that epic started,
the platform has gained: all remaining plugins (governance, OTel, reverse ETL, etc.),
governance uplift, and OTel code instrumentation.

The goal is NOT to fix issues. It is to ensure tests are brutal — especially integration
and E2E tests — and to catalog every gap.

**User directive**: No custom test infra going forward. Tests must use the actual platform
deployment capabilities. Real manifests and floe YAMLs feed the charts. No leaky
abstractions or hardcoded config between user and running services.

Custom test infra removal is deferred to a separate future Epic but must be tracked.

## Architecture Summary

### Real Deployment Path (The Right Way)
```
floe.yaml + manifest.yaml
    → floe compile (6-stage pipeline)
    → CompiledArtifacts
    → Helm charts (floe-platform, floe-jobs)
    → K8s (Kind cluster for testing, real cluster for prod)
    → Services: Dagster, Polaris, MinIO, PostgreSQL, Jaeger, Marquez, OTel, Cube
```

### Key Files

| File | Purpose |
|------|---------|
| `charts/floe-platform/values-test.yaml` | K8s test config (single source of truth for test services) |
| `charts/floe-platform/values-demo.yaml` | Demo mode config |
| `demo/manifest.yaml` | Platform manifest (plugin config, observability, governance) |
| `demo/*/floe.yaml` | Data product specs (customer-360, iot-telemetry, financial-risk) |
| `testing/k8s/setup-cluster.sh` | Kind cluster creation + Helm install |
| `testing/k8s/kind-config.yaml` | Kind config with port mappings |
| `testing/k8s/jobs/test-runner.yaml` | K8s Job definitions for in-cluster tests |
| `testing/Dockerfile` | Test runner image |

### Service Matrix

| Service | In-Cluster | Port-Forward | Values Key |
|---------|-----------|--------------|------------|
| Polaris | polaris:8181 | localhost:8181 | `polaris.service.port: 8181` |
| Dagster | dagster:3000 | localhost:3000 | `dagster.dagsterWebserver` |
| MinIO | minio:9000 | localhost:9000 | `minio.auth.*` |
| PostgreSQL | postgresql:5432 | (internal) | `postgresql.auth.*` |
| Marquez | marquez:5000 | localhost:5000 | `marquez.*` |
| Jaeger | jaeger:16686 | localhost:16686 | `jaeger.allInOne` |
| OTel Collector | otel:4317 | (internal) | `otel.*` |
| Cube | cube:4000 | localhost:4000 | `cube.*` |

### Credentials (from values-test.yaml)
- Polaris: `demo-admin:demo-secret`, warehouse: `floe-e2e`
- MinIO: `minioadmin:minioadmin123`, bucket: `floe-iceberg`
- PostgreSQL: `floe:floe-test-password-1234`, database: `floe`
- Cube API: `test-cube-api-secret-32chars000`

## Current Test Landscape

### Test Counts
- **Root contract tests**: 47 files
- **Root E2E tests**: 11 files
- **Root integration tests**: 14 files (12 Helm-specific)
- **floe-core tests**: ~270 (236 unit, 5 contract, 29 integration)
- **Plugin tests**: ~21 plugins, varying coverage
- **devtools/agent-memory**: 24 tests

### Custom Test Infrastructure (Tech Debt)
Located in `testing/` package:
- `base_classes/` — 12 modules, 3,565 lines (IntegrationTestBase, plugin bases, golden utils)
- `fixtures/` — 16 modules, ~130K total (service fixtures, mock catalogs, data generators)
- `tests/` — Meta-tests for the test infrastructure itself
- `traceability/` — Requirement marker enforcement

### Key Anti-Patterns Found

1. **Two sources of truth**: Service config in both `values-test.yaml` AND Python fixtures
2. **Dual-mode networking**: `_get_effective_host()` auto-detects K8s vs localhost
3. **MockCatalog** (665 lines): Full in-memory PyIceberg mock in `fixtures/catalog.py`
4. **TCP socket health checks**: Raw sockets instead of K8s readiness probes
5. **Plugin test base classes**: 3,565 lines of custom test framework

## E2E Test Analysis

### What's Actually Tested
- `test_compilation.py` — Compilation pipeline (NO K8s required, misclassified as E2E)
- `test_data_pipeline.py` — dbt seed/run/test across 3 products with Iceberg validation
- `test_helm_workflow.py` — Helm chart rendering and installation
- `test_observability.py` — OTel and OpenLineage validation
- `test_platform_bootstrap.py` — Platform initialization
- `test_plugin_system.py` — Plugin discovery and lifecycle
- `test_governance.py` — Governance enforcement
- `test_promotion.py` — Artifact promotion workflow
- `test_schema_evolution.py` — Iceberg schema evolution

### What's Missing
1. **No full user workflow E2E**: `floe compile → helm deploy → dagster materialize → iceberg validate`
2. **No observability round-trip**: Compile with OTel → run → verify traces in Jaeger
3. **No lineage round-trip**: Run pipeline → verify events in Marquez
4. **No governance enforcement under load**: Run pipeline that violates policy → verify rejection
5. **No multi-product isolation**: Run all 3 products simultaneously, verify no namespace bleed
6. **No failure cascade**: Kill a service mid-pipeline, verify graceful degradation
7. **No Cube semantic query**: Deploy → query Cube API → verify metrics resolve
8. **No security boundary**: Verify NetworkPolicy isolation between products

## Demo Product Structure

Each demo product has:
```
demo/{product}/
├── floe.yaml          # Product spec
├── dbt_project.yml    # dbt config
├── profiles.yml       # dbt connection profiles
├── models/
│   ├── staging/       # Bronze (stg_*)
│   ├── intermediate/  # Silver (int_*)
│   └── marts/         # Gold (mart_*)
├── seeds/             # CSV test data
├── macros/            # dbt macros
└── tests/             # dbt data tests
```

Products:
- **customer-360**: CRM data → customer insights (staging, intermediate, marts)
- **iot-telemetry**: IoT sensor data → anomaly detection
- **financial-risk**: Transaction data → risk scoring

## Critic Findings (Adversarial Review)

The following blockers were identified and resolved:

### Resolved: Cube E2E (AC-2.8) — DEFERRED
No Cube Helm templates exist in `charts/floe-platform/templates/`. The config key
`cube.enabled: true` has no corresponding K8s resource templates. AC-2.8 is deferred.

### Resolved: Ephemeral Storage
`values-test.yaml` has `persistence.enabled: false` for MinIO and PostgreSQL.
- AC-2.7 (service failure): Tests error handling ONLY, not retry-after-restore
- AC-2.9 (helm upgrade): Tests rollout mechanism ONLY, not data survival

### Resolved: Dagster Code Location Loading
For AC-2.2, the `floe-jobs` chart manages code location loading via ConfigMaps.
Test must verify the full chain from compilation to Dagster workspace loading.

### Resolved: Overlap with Existing Tests
- `test_observability.py` tests OTel SDK config; new AC-2.3 tests full trace round-trip through Collector to Jaeger
- `test_governance.py` tests policy rules; new AC-2.5 tests compilation ENFORCE stage integration

### Acknowledged: Two Test Patterns
8/11 existing E2E tests use IntegrationTestBase. New tests use port-forward + env vars.
Two patterns coexist until Epic 15 migrates old tests.
