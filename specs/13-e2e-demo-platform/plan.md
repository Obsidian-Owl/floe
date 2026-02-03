# Implementation Plan: E2E Platform Testing & Live Demo Mode

**Branch**: `13-e2e-demo-platform` | **Date**: 2026-02-02 | **Spec**: `specs/13-e2e-demo-platform/spec.md`
**Input**: Feature specification from `/specs/13-e2e-demo-platform/spec.md`

## Summary

Implement comprehensive E2E tests validating ALL platform features (bootstrap, compilation, pipelines, observability, plugins, security, promotion) and a live demo mode with 3 industry data products (customer-360, iot-telemetry, financial-risk). Builds on existing Helm workflow tests, Marquez integration, and promotion system. Key new work: seed data creation, demo pipeline models, auto-trigger sensor, data retention, and E2E test implementations.

## Technical Context

**Language/Version**: Python 3.11 (CLI/tests), Go templating (Helm), SQL (dbt models)
**Primary Dependencies**: pytest, Dagster, dbt-core, PyIceberg, Polaris, Marquez, OTel SDK
**Storage**: Iceberg tables via Polaris 1.1.0+ (Quarkus) catalog with S3FileIO, MinIO (S3-compatible), PostgreSQL
**Testing**: pytest in Kind cluster, IntegrationTestBase, `make test-e2e`
**Target Platform**: Kubernetes (Kind cluster for local, managed K8s for CI)
**Project Type**: Monorepo (multi-package)
**Performance Goals**: `make demo` completes in <10 min; `make e2e` completes in <15 min
**Constraints**: All tests K8s-native, no pytest.skip(), 100% requirement traceability
**Scale/Scope**: 3 data products, ~18 dbt models, ~93 functional requirements (including FR-090–094 schema evolution, 14 TQRs, 10 GAPs), ~50+ E2E tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (E2E tests at root `tests/e2e/`, demo data at `demo/`)
- [x] No SQL parsing/validation in Python (dbt owns SQL via models)
- [x] No orchestration logic outside floe-dagster (sensors/schedules in Dagster plugin)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (sensor via OrchestratorPlugin ABC)
- [x] Plugin registered via entry point (Dagster orchestrator already registered)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
- [x] Pluggable choices documented in manifest.yaml

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (demo products compiled via standard pipeline)
- [x] Pydantic v2 models for all schemas (existing schemas reused)
- [x] Contract changes follow versioning rules (no schema changes needed)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (demo configs validated by FloeSpec)
- [x] Credentials use SecretStr (K8s Secrets for DB passwords)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → floe.yaml → CompiledArtifacts)
- [x] Layer ownership respected (demo floe.yaml = Data Team, platform config = Platform Team)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (validated by E2E tests)
- [x] OpenLineage events for data transformations (validated by E2E tests)

## Integration Design

### Entry Point Integration
- [x] Feature reachable from: CLI (`floe compile`, `floe platform promote`) + `make demo` + `make e2e`
- [x] Integration point: `tests/e2e/` (tests), `demo/` (data products), `Makefile` (targets)
- [x] Wiring task needed: Yes - `make demo` target, `make e2e` updates

### Dependency Integration
| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| CompiledArtifacts | floe-core | `compile_floe_spec()` in compiler.py |
| PromotionController | floe-core | `floe platform promote` CLI |
| DagsterOrchestratorPlugin | floe-orchestrator-dagster | Entry point `floe.orchestrators` |
| IcebergTableManager | floe-iceberg | `expire_snapshots()` |
| MarquezPlugin | floe-lineage-marquez | Entry point `floe.lineage_backends` |
| PluginRegistry | floe-core | `discover_all()`, `get()` |

### Key Architecture Decisions

**Polaris 1.1.0+ (Quarkus)**: The demo requires Polaris 1.1.0+ which is Quarkus-based (not Dropwizard 0.9.x). This version has native S3FileIO support for MinIO. The Helm chart must use the `apache/polaris:1.1.0` image with Quarkus configuration format (application.properties, not server.yml). This is a breaking change from the 0.9.0 image currently in the chart.

**Dagster workspace.yaml Multi-Location**: Each data product is a separate Dagster code location. The `--generate-definitions` flag on `floe platform compile` produces a `definitions.py` per product. These are registered in `workspace.yaml` as separate `python_file` entries, enabling independent deployment per FR-086 and FR-014. No monolithic single `Definitions` object.

**Compute vs Storage Separation**: DuckDB is the pluggable *compute* engine (runs SQL transforms). Data MUST land in Iceberg tables via Polaris catalog with S3FileIO pointing to MinIO. This is the enforced storage path — DuckDB does not own data persistence. Tests MUST validate data exists in Iceberg (via PyIceberg/Polaris API), not in local DuckDB files.

**Marquez DB Backend**: Configurable via `manifest.yaml` lineage section. Default: shared PostgreSQL instance. Platform engineers can override with dedicated DB. Not hardcoded in tests or demo config.

### Produces for Others
| Output | Consumers | Contract |
|--------|-----------|----------|
| 3 demo floe.yaml configs | Anyone running `make demo` | FloeSpec schema |
| Seed CSVs | dbt seed command | dbt seed convention |
| E2E test suite | CI pipeline | pytest + requirement markers |
| Grafana dashboards | Demo viewers | Grafana JSON model |

### Cleanup Required
- [x] Old code to remove: None (additive feature)
- [x] Old tests to update: `tests/e2e/test_demo_flow.py` (replace pytest.fail placeholders)
- [x] Old docs to update: None

## Project Structure

### Documentation (this feature)

```text
specs/13-e2e-demo-platform/
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart guide
├── contracts/           # Phase 1 contracts
└── tasks.md             # Phase 2 tasks (generated by /speckit.tasks)
```

### Source Code (repository root)

```text
demo/
├── floe.yaml                     # Existing customer-360 config (UPDATE)
├── datacontract.yaml             # Existing data contract
├── customer-360/
│   ├── floe.yaml                 # Product-specific config
│   ├── seeds/
│   │   ├── raw_customers.csv
│   │   ├── raw_transactions.csv
│   │   └── raw_support_tickets.csv
│   └── models/
│       ├── staging/
│       │   ├── stg_crm_customers.sql
│       │   ├── stg_transactions.sql
│       │   └── stg_support_tickets.sql
│       ├── intermediate/
│       │   ├── int_customer_orders.sql
│       │   └── int_customer_support.sql
│       └── marts/
│           └── mart_customer_360.sql
├── iot-telemetry/
│   ├── floe.yaml
│   ├── seeds/
│   │   ├── raw_sensors.csv
│   │   ├── raw_readings.csv
│   │   └── raw_maintenance_log.csv
│   └── models/
│       ├── staging/
│       │   ├── stg_sensors.sql
│       │   ├── stg_readings.sql
│       │   └── stg_maintenance.sql
│       ├── intermediate/
│       │   ├── int_sensor_metrics.sql
│       │   └── int_anomaly_detection.sql
│       └── marts/
│           └── mart_equipment_health.sql
├── financial-risk/
│   ├── floe.yaml
│   ├── seeds/
│   │   ├── raw_positions.csv
│   │   ├── raw_market_data.csv
│   │   └── raw_counterparties.csv
│   └── models/
│       ├── staging/
│       │   ├── stg_positions.sql
│       │   ├── stg_market_data.sql
│       │   └── stg_counterparties.sql
│       ├── intermediate/
│       │   ├── int_portfolio_risk.sql
│       │   └── int_counterparty_exposure.sql
│       └── marts/
│           └── mart_risk_dashboard.sql

tests/e2e/
├── conftest.py                   # Existing (UPDATE with new fixtures)
├── test_helm_workflow.py         # Existing (no changes)
├── test_demo_flow.py             # Existing skeleton (REPLACE)
├── test_platform_bootstrap.py    # NEW: US1 - service health
├── test_compilation.py           # NEW: US2 - compile & artifacts
├── test_data_pipeline.py         # NEW: US3 - pipeline execution
├── test_observability.py         # NEW: US4 - traces, lineage, metrics
├── test_plugin_system.py         # NEW: US5 - plugin discovery & ABC
├── test_governance.py            # NEW: US6 - RBAC, NetworkPolicy, secrets
├── test_promotion.py             # NEW: US7 - promotion lifecycle
├── test_demo_mode.py             # NEW: US8 - live demo
└── test_schema_evolution.py      # NEW: US9 - multi-product, schema evolution

charts/floe-platform/
├── values.yaml                   # UPDATE: enable Marquez
└── values-demo.yaml              # NEW: demo-specific overrides

Makefile                          # UPDATE: add `make demo` target
```

**Structure Decision**: Additive to existing monorepo structure. Demo data products organized under `demo/{product-name}/` with standard dbt project layout. E2E tests split by user story for clarity and independent execution. No new packages needed.

## Implementation Stages

*Note: These are high-level stages grouping related work. See `tasks.md` for the detailed 13-phase breakdown with task IDs.*

### Stage 1: Foundation (P1 User Stories)

**Goal**: Platform bootstrap validation, compilation testing, basic pipeline execution.

1. **Enable Marquez in Helm values** - Set `marquez.enabled: true` in values.yaml
2. **Create demo data products** - 3 product directories with floe.yaml, seeds/, models/
3. **Implement test_platform_bootstrap.py** - Service health checks (FR-001 to FR-008)
4. **Implement test_compilation.py** - Compile all 3 products, validate artifacts (FR-010 to FR-017)
5. **Implement test_data_pipeline.py** - Execute pipelines, verify Iceberg tables (FR-020 to FR-033)
6. **Update conftest.py** - Shared fixtures for compilation, deployment, pipeline execution
7. **Add `make demo` target** - Bootstrap + deploy + execute + open dashboards

### Stage 2: Platform Features (P2 User Stories)

**Goal**: Observability, plugins, security, promotion validation.

8. **Implement test_observability.py** - OTel traces in Jaeger, OpenLineage in Marquez, Prometheus metrics (FR-040 to FR-049)
9. **Implement test_plugin_system.py** - Entry point discovery, ABC compliance, plugin swapping (FR-050 to FR-056)
10. **Implement test_governance.py** - NetworkPolicy, secrets audit, Polaris RBAC, security scanning (FR-060 to FR-067)
11. **Implement test_promotion.py** - Multi-namespace promotion with gates (FR-070 to FR-075)
12. **Add auto-trigger sensor** - Dagster sensor that triggers first run on platform health
13. **Add data retention** - Iceberg snapshot expiry + time-based cleanup model

### Stage 3: Demo & Advanced (P3 User Stories)

**Goal**: Live demo mode, multi-product coexistence, schema evolution.

14. **Implement test_demo_mode.py** - Full `make demo` workflow validation (FR-080 to FR-088)
15. **Create Grafana dashboards** - Pipeline metrics, data quality, lineage visualization
16. **Implement test_schema_evolution.py** - Schema evolution (FR-090 to FR-094), partition evolution, namespace isolation
17. **Add values-demo.yaml** - Demo-specific Helm overrides (Marquez enabled, schedules configured)
18. **Remove test_demo_flow.py skeleton** - Replace with implemented tests above

### Stage 4: Test Quality Hardening (Post-Implementation)

**Goal**: Fill GAP-001 to GAP-010 test gaps and enforce TQR-001 to TQR-014 anti-pattern rules across all test files.

19. **Fill GAP tests** - Auto-trigger sensor E2E (GAP-001), data retention enforcement (GAP-002), snapshot expiry (GAP-003), trace content validation (GAP-004), OpenLineage 4-point emission (GAP-005), plugin swap execution (GAP-008), promotion gate real blocking (GAP-009)
20. **TQR anti-pattern audit** - Grep all test files for bare existence checks (TQR-001), missing data validation (TQR-002), dry_run=True (TQR-010), fixture bypasses (TQR-004). Fix all violations.
21. **Cross-cutting fixes** - Ensure compilation uses real pipeline not fixtures (GAP-006), pipeline tests validate Iceberg via S3FileIO not DuckDB (GAP-007)

## Complexity Tracking

No constitution violations. All work is additive and follows existing patterns.

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Marquez startup adds time to bootstrap | Medium | Already in Helm chart, just disabled. Monitor SC-001 (120s target) |
| 3 data products + seeds exceed 10-min demo target | High | Configurable seed scale (default small). Parallel pipeline execution |
| Sensor auto-trigger timing in CI | Medium | Use deterministic health check, not time-based polling |
| Kind cluster resource limits with 3 products | Medium | Use resource limits in Helm values, test on CI runner specs |
