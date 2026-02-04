# Tasks: E2E Platform Testing & Live Demo Mode

**Input**: Design documents from `/specs/13-e2e-demo-platform/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

**Numbering Convention**: T001–T050 and T024a match Linear issue mappings (FLO-2293–FLO-2342). Tasks added after initial planning use the next available sequential ID (T048 fills a gap, T051–T065 are additions). See `.linear-mapping.json` for the full mapping.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Enable Marquez, create demo directory structure, update shared test infrastructure

- [x] T001 Enable Marquez in Helm chart by setting `marquez.enabled: true` in charts/floe-platform/values.yaml
- [x] T002 [P] Create demo directory structure: demo/customer-360/, demo/iot-telemetry/, demo/financial-risk/ each with seeds/ and models/staging/, models/intermediate/, models/marts/ subdirectories
- [x] T003 [P] Update tests/e2e/conftest.py with shared fixtures: `platform_namespace`, `compiled_artifacts`, `dagster_client`, `polaris_client`, `marquez_client`, `jaeger_client`
- [x] T004 [P] Create charts/floe-platform/values-demo.yaml with demo-specific overrides (Marquez enabled, 10-min schedule, resource limits for Kind)
- [x] T005 Add `make demo` and `make demo-stop` targets to Makefile (bootstrap + deploy 3 products + open dashboards)
- [ ] T048 [P] Add namespace teardown fixture to tests/e2e/conftest.py: session-scoped fixture that creates a fresh K8s namespace per test class and tears it down after (kubectl delete namespace). Ensures full isolation between test suites per FR-008 clarification.
- [ ] T065 [P] Ensure Marquez DB backend is configurable via manifest.yaml lineage section (FR-049): Update charts/floe-platform/values.yaml and values-demo.yaml to support `marquez.database` config (default: shared PostgreSQL). Platform engineers MUST be able to override this.

---

## Phase 2: Foundational (Demo Data Products)

**Purpose**: Create the 3 demo data products that ALL user stories depend on for E2E validation

**CRITICAL**: No E2E test can run without demo data products available

### customer-360 (Retail)

- [x] T006 [P] Create demo/customer-360/floe.yaml with FloeSpec config (bronze/silver/gold pipeline, compute=duckdb, storage=iceberg via Polaris S3FileIO + MinIO, 10-min schedule)
- [x] T007 [P] Create seed CSVs in demo/customer-360/seeds/: raw_customers.csv (500 rows), raw_transactions.csv (1000 rows), raw_support_tickets.csv (300 rows) with _loaded_at timestamp column
- [x] T008 [P] Create staging models in demo/customer-360/models/staging/: stg_crm_customers.sql, stg_transactions.sql, stg_support_tickets.sql
- [x] T009 [P] Create intermediate models in demo/customer-360/models/intermediate/: int_customer_orders.sql, int_customer_support.sql
- [x] T010 [P] Create mart model in demo/customer-360/models/marts/mart_customer_360.sql
- [x] T011 [P] Create dbt schema tests in demo/customer-360/models/schema.yml (not_null, unique, accepted_values per layer)

### iot-telemetry (Manufacturing)

- [x] T012 [P] Create demo/iot-telemetry/floe.yaml with FloeSpec config (sensor pipeline, compute=duckdb, storage=iceberg via Polaris S3FileIO + MinIO, 10-min schedule)
- [x] T013 [P] Create seed CSVs in demo/iot-telemetry/seeds/: raw_sensors.csv (200 rows), raw_readings.csv (1000 rows), raw_maintenance_log.csv (100 rows) with _loaded_at timestamp column
- [x] T014 [P] Create staging models in demo/iot-telemetry/models/staging/: stg_sensors.sql, stg_readings.sql, stg_maintenance.sql
- [x] T015 [P] Create intermediate models in demo/iot-telemetry/models/intermediate/: int_sensor_metrics.sql, int_anomaly_detection.sql
- [x] T016 [P] Create mart model in demo/iot-telemetry/models/marts/mart_equipment_health.sql
- [x] T017 [P] Create dbt schema tests in demo/iot-telemetry/models/schema.yml

### financial-risk (Finance)

- [x] T018 [P] Create demo/financial-risk/floe.yaml with FloeSpec config (risk pipeline, compute=duckdb, storage=iceberg via Polaris S3FileIO + MinIO, 10-min schedule)
- [x] T019 [P] Create seed CSVs in demo/financial-risk/seeds/: raw_positions.csv (500 rows), raw_market_data.csv (1000 rows), raw_counterparties.csv (100 rows) with _loaded_at timestamp column
- [x] T020 [P] Create staging models in demo/financial-risk/models/staging/: stg_positions.sql, stg_market_data.sql, stg_counterparties.sql
- [x] T021 [P] Create intermediate models in demo/financial-risk/models/intermediate/: int_portfolio_risk.sql, int_counterparty_exposure.sql
- [x] T022 [P] Create mart model in demo/financial-risk/models/marts/mart_risk_dashboard.sql
- [x] T023 [P] Create dbt schema tests in demo/financial-risk/models/schema.yml

### dbt Project Configuration

- [x] T024a [P] Add dbt_project.yml for each demo product (demo/customer-360/dbt_project.yml, demo/iot-telemetry/dbt_project.yml, demo/financial-risk/dbt_project.yml). Required before compilation (Phase 4).

### Data Retention

- [x] T024 Create dbt macro for retention cleanup in demo/macros/retention_cleanup.sql (DELETE WHERE _loaded_at < now() - interval '1 hour') applied as post-hook to all models
- [x] T025 [P] Create seed data generator script in demo/scripts/generate_seeds.py supporting FLOE_DEMO_SEED_SCALE env var (small=default, medium, large). Run with `uv run python demo/scripts/generate_seeds.py`

**Checkpoint**: All 3 demo data products ready with seeds, models, tests, and retention. Ready for E2E testing.

---

## Phase 3: User Story 1 - Platform Bootstrap & Service Health (Priority: P1)

**Goal**: Verify all platform services deploy and respond correctly in Kind cluster

**Independent Test**: `pytest tests/e2e/test_platform_bootstrap.py -v` validates all services healthy

**Requirements**: FR-001 to FR-008

### Tests

- [x] T026 [US1] Create tests/e2e/test_platform_bootstrap.py with TestPlatformBootstrap class inheriting IntegrationTestBase:
  - test_all_pods_ready (FR-001, FR-002): Deploy floe-platform chart, verify all pods Ready within 120s
  - test_nodeport_services_respond (FR-003): Query each NodePort (Dagster:3000, Polaris:8181, MinIO:9000/9001, Jaeger:16686, Grafana:3001, Prometheus:9090, Marquez:5001)
  - test_postgresql_databases_exist (FR-004): Verify dagster and polaris databases with correct schemas
  - test_minio_buckets_exist (FR-005): Verify warehouse and staging buckets
  - test_otel_collector_forwarding (FR-006): Send test span, verify it appears in Jaeger
  - test_observability_uis_accessible (FR-007): HTTP 200 from Jaeger, Grafana, Prometheus UIs
  - test_marquez_accessible (FR-049): HTTP 200 from Marquez API and UI

### Implementation

- [x] T027 [US1] Update testing/ci/test-e2e.sh to check for Marquez service in addition to existing checks (FR-008)

**Checkpoint**: Platform bootstrap validated. All services healthy including Marquez.

---

## Phase 4: User Story 2 - Compilation & Artifact Generation (Priority: P1)

**Goal**: Verify floe compile produces valid CompiledArtifacts for all 3 demo products

**Independent Test**: `pytest tests/e2e/test_compilation.py -v` validates compilation pipeline

**Requirements**: FR-010 to FR-017

### Tests

- [x] T028 [US2] Create tests/e2e/test_compilation.py with TestCompilation class:
  - test_compile_customer_360 (FR-010): Compile demo/customer-360/floe.yaml, validate CompiledArtifacts v0.5.0
  - test_compile_iot_telemetry (FR-010): Compile demo/iot-telemetry/floe.yaml
  - test_compile_financial_risk (FR-010): Compile demo/financial-risk/floe.yaml
  - test_compilation_stages_execute (FR-011): Verify all 6 compilation stages (LOAD→VALIDATE→RESOLVE→ENFORCE→COMPILE→GENERATE) complete
  - test_manifest_merge (FR-012): Compile with manifest.yaml + floe.yaml, verify merge
  - test_dbt_profiles_generated (FR-013): Verify profiles.yml in artifacts
  - test_dagster_config_generated (FR-014): Verify Dagster resource config in artifacts, validate workspace.yaml has separate code location per data product with `python_file` entries pointing to generated `definitions.py`
  - test_generate_definitions_flag (FR-014): Compile with `--generate-definitions`, verify `definitions.py` is generated per product and is importable by Dagster
  - test_invalid_spec_rejected (FR-015): Compile invalid floe.yaml, expect ValidationError
  - test_deterministic_output (FR-016): Compile same input twice, verify byte-identical output
  - test_json_schema_export (FR-017): Verify JSON Schema exported for floe.yaml

**Checkpoint**: All 3 demo products compile successfully. Artifacts validated.

---

## Phase 5: User Story 3 - Data Pipeline Execution (Priority: P1)

**Goal**: Execute complete pipelines through all medallion layers with data landing in Iceberg tables

**Independent Test**: `pytest tests/e2e/test_data_pipeline.py -v` validates end-to-end data flow

**Requirements**: FR-020 to FR-033

### Tests

- [x] T029 [US3] Create tests/e2e/test_data_pipeline.py with TestDataPipeline class inheriting IntegrationTestBase:
  - test_dbt_seed_loads_data (FR-023): Run dbt seed for customer-360, verify tables populated
  - test_pipeline_execution_order (FR-020): Trigger Dagster run, verify models execute in dependency order
  - test_medallion_layers (FR-021): Verify Bronze→Silver→Gold transforms produce correct output
  - test_iceberg_tables_created (FR-022): Query Polaris catalog, verify Iceberg tables exist with schemas and row counts > 0
  - test_dbt_tests_pass (FR-024): Run dbt test after pipeline, verify schema/data tests pass
  - test_incremental_model_merge (FR-025): Run pipeline twice with overlapping data, verify incremental merge behavior (no duplicates)
  - test_data_quality_checks (FR-026): Run dbt test with dbt-expectations tests, verify quality checks execute and report results
  - test_pipeline_failure_recording (FR-027): Trigger pipeline with bad model, verify Dagster records failure
  - test_pipeline_retry (FR-028): After failure, retry from failure point (not full re-run)
  - NOTE: FR-029 (auto-trigger sensor E2E) is covered by T051 in Phase 13 — full sensor execution test added to this same file

### Implementation

- [x] T030 [US3] Add auto-trigger health sensor to plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py (FR-029, FR-033): SensorDefinition that checks platform service health and triggers first pipeline run
- [x] T031 [US3] Add sensor_definition() method to OrchestratorPlugin ABC in packages/floe-core/src/floe_core/plugins/orchestrator.py
- [x] T032 [US3] Add recurring schedule configuration (10-min default) to DagsterOrchestratorPlugin in plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py (FR-030)
- [x] T033 [US3] Add Iceberg snapshot expiry integration to floe-iceberg for demo retention (FR-032): Configure keep_last=6 snapshots in packages/floe-iceberg/src/floe_iceberg/_snapshot_manager.py
- [x] T034 [US3] Add unit tests for auto-trigger sensor in plugins/floe-orchestrator-dagster/tests/unit/test_health_sensor.py
- [x] T035 [US3] Add unit tests for snapshot expiry retention config in packages/floe-iceberg/tests/unit/test_snapshot_retention.py

**Checkpoint**: Complete data pipeline execution validated. Seeds → Staging → Intermediate → Marts working for all 3 products.

---

## Phase 6: User Story 4 - Observability & Lineage (Priority: P2)

**Goal**: Verify OTel traces, OpenLineage events, and metrics are emitted and queryable

**Independent Test**: `pytest tests/e2e/test_observability.py -v` validates observability stack

**Requirements**: FR-040 to FR-049

### Tests

- [x] T036 [P] [US4] Create tests/e2e/test_observability.py with TestObservability class inheriting IntegrationTestBase:
  - test_otel_traces_in_jaeger (FR-040, FR-047): Run pipeline, query Jaeger for traces with span-per-model
  - test_openlineage_events_in_marquez (FR-041, FR-048): Query Marquez API for START/COMPLETE events at all 4 emission points
  - test_trace_lineage_correlation (FR-042): Verify trace_id matches between OTel spans and OpenLineage events
  - test_prometheus_metrics (FR-043): Query Prometheus for pipeline duration, model count, error rate metrics
  - test_structured_logs_with_trace_id (FR-045): Query logs for structured entries with trace_id correlation
  - test_observability_non_blocking (FR-046): Stop OTel collector, run pipeline, verify it still completes
  - test_marquez_lineage_graph (FR-048): Query Marquez lineage API, verify data flow graph across models

**Checkpoint**: Full observability stack validated. Traces, lineage, and metrics all working.

---

## Phase 7: User Story 5 - Plugin System Validation (Priority: P2)

**Goal**: Verify all plugin types discoverable, ABC-compliant, and swappable

**Independent Test**: `pytest tests/e2e/test_plugin_system.py -v` validates plugin architecture

**Requirements**: FR-050 to FR-056

### Tests

- [x] T037 [P] [US5] Create tests/e2e/test_plugin_system.py with TestPluginSystem class:
  - test_all_plugin_types_discoverable (FR-050): Load PluginRegistry.discover_all(), verify all 15 plugin ABCs defined and at least 12 have implementations (Ingestion, Semantic, Storage are ABC-only)
  - test_abc_compliance (FR-051): For each plugin type, instantiate and verify all abstract methods implemented
  - test_plugin_swap_via_config (FR-052): Compile with compute=duckdb, then compute=spark, verify both succeed
  - test_plugin_health_checks (FR-055): Call health check on each discovered plugin
  - test_plugin_compatibility_at_compile_time (FR-054): Verify incompatible plugin version rejected at compile
  - test_third_party_plugin_discovery (FR-053): Install a test plugin via pip (uv pip install), verify it is discovered by PluginRegistry
  - test_plugin_abc_backwards_compat (FR-056): Load plugin ABCs, verify no breaking changes from baseline signatures within major version

**Checkpoint**: Plugin system fully validated. All 15 ABCs defined, 12 with implementations discoverable and compliant.

---

## Phase 8: User Story 6 - Governance & Security (Priority: P2)

**Goal**: Verify RBAC, NetworkPolicy, secret management, and security scanning

**Independent Test**: `pytest tests/e2e/test_governance.py -v` validates security posture

**Requirements**: FR-060 to FR-067

### Tests

- [x] T038 [P] [US6] Create tests/e2e/test_governance.py with TestGovernance class inheriting IntegrationTestBase:
  - test_network_policies_restrict_traffic (FR-060): Deploy test pod, attempt unauthorized connection, verify denied
  - test_secrets_not_hardcoded (FR-061): Inspect all pod specs, verify secrets via K8s Secret refs only
  - test_polaris_rbac_enforcement (FR-062): Create restricted principal, attempt TABLE_READ, verify 403
  - test_bandit_security_scan (FR-063): Run bandit on codebase, verify zero critical/high findings
  - test_pip_audit_clean (FR-064): Run `uv run pip-audit`, verify zero critical/high vulnerabilities
  - test_secretstr_usage (FR-065): Grep Pydantic models for password/api_key fields, verify SecretStr type
  - test_no_stack_trace_exposure (FR-066): Trigger error via API, verify response contains no stack traces
  - test_security_event_logging (FR-067): Trigger auth failure, verify structured log entry

**Checkpoint**: Security posture validated. RBAC, network isolation, and scanning all pass.

---

## Phase 9: User Story 7 - Artifact Promotion Lifecycle (Priority: P2)

**Goal**: Verify artifact promotion through K8s namespaces with gate enforcement

**Independent Test**: `pytest tests/e2e/test_promotion.py -v` validates promotion lifecycle

**Requirements**: FR-070 to FR-075

### Tests

- [x] T039 [US7] Create tests/e2e/test_promotion.py with TestPromotion class inheriting IntegrationTestBase:
  - test_create_environment_namespaces: Create floe-dev, floe-staging, floe-prod K8s namespaces
  - test_promote_dev_to_staging (FR-070, FR-071): Compile artifact, deploy to floe-dev, promote to floe-staging with gate execution
  - test_promotion_gate_blocks_on_failure (FR-072): Deploy OPA with deny policy, verify promotion blocked by real gate service (no mocks)
  - test_promotion_audit_trail (FR-073): Promote successfully, query audit trail for who/what/when/gates
  - test_rollback_to_previous_version (FR-074): Promote v2, rollback to v1, verify v1 active
  - test_manual_approval_gate (FR-075): Trigger promotion requiring manual approval, verify it waits

**Checkpoint**: Promotion lifecycle validated across K8s namespaces. Gates enforce correctly.

---

## Phase 10: User Story 8 - Live Demo Mode (Priority: P3)

**Goal**: Validate `make demo` runs full platform with 3 data products and dashboards

**Independent Test**: `pytest tests/e2e/test_demo_mode.py -v` validates complete demo experience

**Requirements**: FR-080 to FR-088

### Tests

- [x] T040 [US8] Create tests/e2e/test_demo_mode.py with TestDemoMode class inheriting IntegrationTestBase:
  - test_make_demo_completes (FR-087, FR-088): Run `make demo`, verify completion within 10 minutes
  - test_three_products_visible_in_dagster (FR-080, FR-081, FR-082): Verify 3 data products in Dagster UI
  - test_dagster_asset_lineage (FR-084): Verify Bronze→Silver→Gold lineage graphs per product
  - test_grafana_dashboards_loaded (FR-044): Verify Grafana dashboards show pipeline metrics
  - test_jaeger_traces_for_all_products: Verify traces for all 3 products in Jaeger
  - test_independent_product_deployment (FR-086): Deploy only customer-360, verify it works alone
  - test_configurable_seed_scale (FR-083): Run with FLOE_DEMO_SEED_SCALE=medium, verify larger data

### Implementation

- [x] T041 [P] [US8] Create Grafana dashboard JSON for pipeline metrics in charts/floe-platform/dashboards/pipeline-metrics.json
- [x] T042 [P] [US8] Create Grafana dashboard JSON for data quality in charts/floe-platform/dashboards/data-quality.json
- [x] T043 [P] [US8] Create Grafana dashboard JSON for lineage overview in charts/floe-platform/dashboards/lineage-overview.json
- [x] T044 [US8] Add Grafana dashboard provisioning to Helm chart in charts/floe-platform/templates/grafana-dashboards-configmap.yaml

**Checkpoint**: Live demo mode fully functional. `make demo` runs 3 products with observable dashboards.

---

## Phase 11: User Story 9 - Multi-Product Coexistence & Schema Evolution (Priority: P3)

**Goal**: Validate multiple products coexist and schemas evolve safely

**Independent Test**: `pytest tests/e2e/test_schema_evolution.py -v` validates multi-tenancy and evolution

### Tests

- [x] T045 [US9] Create tests/e2e/test_schema_evolution.py with TestSchemaEvolution class inheriting IntegrationTestBase:
  - test_multi_product_no_conflicts (FR-093): Run all 3 products simultaneously, verify no resource conflicts or namespace collisions
  - test_polaris_namespace_isolation (FR-093): Verify each product has its own Polaris namespace with isolated tables and independent schema evolution
  - test_iceberg_schema_evolution_add_column (FR-090): Add column to existing Iceberg table (v1→v2), verify old queries return null for new column, new queries can use it
  - test_iceberg_partition_evolution (FR-091): Change partition spec, verify new data uses new partitioning, old data still queryable under old spec
  - test_iceberg_time_travel_query (FR-092): Run pipeline, record snapshot ID, run again, query as-of previous snapshot and verify historical data returned
  - test_backward_compat_schema_enforcement (FR-094): Attempt to drop column or change column type, verify rejected at compile time with descriptive error message
  - NOTE: FR-031 (data retention) and FR-032 (snapshot expiry) are tested by T052 and T053 in Phase 13 to ensure behavioral validation, not just existence checks

**Checkpoint**: Multi-product coexistence and schema evolution validated.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup, skeleton removal, documentation

- [x] T046 Remove skeleton test_demo_flow.py (replace pytest.fail placeholders with reference to new test files) in tests/e2e/test_demo_flow.py
- [x] T047 [P] Update demo/README.md with quickstart instructions for running all 3 demo products
- [ ] T049 Run `make test-e2e` and verify all E2E tests pass with 100% requirement traceability
- [ ] T050 Run `uv run python -m testing.traceability --all --threshold 100` to verify traceability coverage

---

## Phase 13: Test Quality Hardening (TQR/GAP Coverage)

**Purpose**: Fill critical test gaps (GAP-001 to GAP-010) and enforce test quality requirements (TQR-001 to TQR-014). This phase ensures tests validate actual behavior, not just existence.

**CRITICAL**: Phases 3-11 create the test files. Phase 13 hardens them against anti-patterns identified during research (test quality score was 20/100 before this epic).

### Triage Protocol (NON-NEGOTIABLE)

When running tests in this phase, every failure MUST be classified and handled according to this protocol. **Do not apply quick fixes. Do not weaken assertions. Be slow and methodical.**

| Category | Symptom | Action | Allowed Changes |
|----------|---------|--------|-----------------|
| **INFRA** | Test config wrong, fixture misconfigured, missing K8s resource, wrong port/URL | Fix the infrastructure or test config | Config files, fixtures, setup code. **NEVER loosen assertions.** |
| **COMPLEX** | Root cause unclear, spans multiple systems, requires architectural investigation | Raise GitHub issue with diagnosis | None. Document findings in the issue. |
| **PROD-BUG** | Production code has a gap, bug, or missing feature that the test correctly exposes | Raise GitHub issue describing the gap | None. The test is RIGHT. The production code needs work. |

**Key principle**: A failing test is a signal, not a problem to silence. If a test fails because the platform doesn't do what the spec says, that's a production issue — not a test issue.

### GAP Coverage Tasks (New Tests)

- [ ] T051 [US3] Add test_auto_trigger_sensor_e2e to tests/e2e/test_data_pipeline.py (GAP-001, FR-029): Deploy pipeline, health sensor detects all services healthy, fires RunRequest, Dagster run completes. Full sensor execution, not mock.
- [ ] T052 [US3] Add test_data_retention_enforcement to tests/e2e/test_data_pipeline.py (GAP-002, FR-031): Run pipeline with retention macro, verify records older than retention period are actually deleted from Iceberg table (query post-cleanup, assert row count decreased).
- [ ] T053 [US3] Add test_snapshot_expiry_enforcement to tests/e2e/test_data_pipeline.py (GAP-003, FR-032): Run pipeline 8+ times, verify Iceberg snapshot count capped at 6 via PyIceberg table.snapshots() API.
- [ ] T054 [US4] Add test_trace_content_validation to tests/e2e/test_observability.py (GAP-004): Query Jaeger for traces, validate span attributes contain model_name, pipeline_name, duration_ms, layer (not just "trace exists").
- [ ] T055 [US4] Add test_openlineage_four_emission_points to tests/e2e/test_observability.py (GAP-005, FR-041): Verify OpenLineage events emitted at: (1) dbt model start, (2) dbt model complete, (3) pipeline start, (4) pipeline complete. Query Marquez for all 4 event types.
- [ ] T056 [US5] Add test_plugin_swap_actual_execution to tests/e2e/test_plugin_system.py (GAP-008, FR-052): Compile with compute=duckdb and execute pipeline, then compile with compute=spark (config-only swap), verify both produce valid CompiledArtifacts with different compute sections.
- NOTE: GAP-009 (FR-072 promotion gate blocking) is already covered by T039's test_promotion_gate_blocks_on_failure which deploys real OPA with deny policy. Phase 13 audits T039 for TQR compliance (T058) rather than duplicating the test.

### TQR Anti-Pattern Audit Tasks (Run, Diagnose, Triage)

Each task below follows the same process: **Run the tests. Observe failures. Classify per triage protocol. Fix only INFRA issues. Raise GitHub issues for COMPLEX and PROD-BUG.**

- [ ] T058 Run all Phase 3-11 test files and audit for TQR-001 compliance (behavioral validation): Grep for bare `assert X is not None` or `assert len(X) > 0` without subsequent value assertions. For each violation: determine if it's INFRA (test assertion can be strengthened without production changes), COMPLEX (needs investigation), or PROD-BUG (the platform doesn't expose the data needed for a proper assertion). Strengthen assertions only where the platform already provides the data. Raise GitHub issues for the rest.
- [ ] T059 Run all Phase 3-11 test files and audit for TQR-002 compliance (data content validation): Identify all Iceberg/pipeline tests that check only table existence without querying actual data values (row counts, column values, schema fields). Classify each gap per triage protocol.
- [ ] T060 Run all Phase 3-11 test files and audit for TQR-010 compliance (no dry_run=True): Grep for `dry_run=True` in E2E tests. For each occurrence: determine if removing it requires only test config changes (INFRA) or reveals a production gap (PROD-BUG). Raise GitHub issues for production gaps.
- [ ] T061 Run all Phase 3-11 test files and audit for TQR-004 compliance (real compilation): Identify all tests that use pre-built CompiledArtifacts fixtures instead of calling `compile_pipeline()` or `floe platform compile`. Determine if switching to real compilation requires only test changes (INFRA) or reveals missing compiler features (PROD-BUG). Raise GitHub issues for production gaps.
- [ ] T062 [P] Add TQR checklist enforcement to tests/e2e/conftest.py: Create a pytest plugin or conftest hook that warns on common anti-patterns (bare existence checks, dry_run=True, pytest.skip usage) during test collection. This is a new tool, not a fix.

### Cross-Cutting Gap Diagnosis (Run, Diagnose, Triage)

- [ ] T063 Run tests that use CompiledArtifacts and diagnose GAP-006 (compilation fixture bypass): Review all E2E tests that use CompiledArtifacts. Determine if switching to `compile_pipeline()` with real floe.yaml requires only test config changes (INFRA) or reveals compiler issues (PROD-BUG). Fix INFRA, raise GitHub issues for PROD-BUG.
- [ ] T064 Run data pipeline tests and diagnose GAP-007 (DuckDB vs Iceberg): Review all data pipeline tests. Determine if switching validation from local DuckDB to Iceberg tables via Polaris catalog (S3FileIO + MinIO) requires only test config changes (INFRA) or reveals missing storage integration (PROD-BUG). Fix INFRA, raise GitHub issues for PROD-BUG.

**Checkpoint**: All tests audited. Anti-patterns classified. INFRA issues fixed (assertions never weakened). COMPLEX and PROD-BUG issues tracked as GitHub issues with clear diagnosis.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on T001 (Marquez enabled) - BLOCKS all E2E tests
- **US1 Bootstrap (Phase 3)**: Depends on Phase 1 setup. Can run before demo data.
- **US2 Compilation (Phase 4)**: Depends on Phase 2 (demo products exist to compile)
- **US3 Pipeline (Phase 5)**: Depends on Phase 3 (services healthy) + Phase 2 (products to run)
- **US4 Observability (Phase 6)**: Depends on Phase 5 (needs pipeline run to produce traces)
- **US5 Plugins (Phase 7)**: Depends on Phase 1 only (tests plugin registry, not demo data)
- **US6 Governance (Phase 8)**: Depends on Phase 3 (needs deployed platform)
- **US7 Promotion (Phase 9)**: Depends on Phase 4 (needs compiled artifacts)
- **US8 Demo Mode (Phase 10)**: Depends on Phases 2-6 (needs everything working)
- **US9 Schema Evolution (Phase 11)**: Depends on Phase 5 (needs pipeline execution working)
- **Polish (Phase 12)**: Depends on all desired stories complete
- **Test Quality Hardening (Phase 13)**: Depends on Phases 3-11 (test files must exist before auditing). Can run in parallel with Phase 12.

### User Story Dependencies

```
US1 (Bootstrap) ─────────────────────────┐
US2 (Compilation) ──► US3 (Pipeline) ──► US4 (Observability)
                                         │
US5 (Plugins) ───── independent ─────────┤
US6 (Governance) ── depends on US1 ──────┤
US7 (Promotion) ── depends on US2 ──────┤
                                         ▼
                                    US8 (Demo Mode)
                                         │
US9 (Schema Evolution) ── depends on US3 ┘
```

### Parallel Opportunities

**Phase 2 (T006-T025 + T024a, all parallelizable)**: All 3 data products can be created simultaneously - they're independent directories.

**After Phase 3 (US1)**:
- US5 (Plugins) can run in parallel with US2/US3
- US6 (Governance) can run in parallel with US2/US3

**After Phase 5 (US3)**:
- US4 (Observability) and US9 (Schema Evolution) can run in parallel
- US7 (Promotion) can start after US2

---

## Parallel Example: Phase 2 (Demo Data Products)

```bash
# All 3 products can be created in parallel:
Task: "Create customer-360 floe.yaml" (T006)
Task: "Create iot-telemetry floe.yaml" (T012)
Task: "Create financial-risk floe.yaml" (T018)

# Within each product, seeds + models + tests are parallelizable:
Task: "Create customer-360 seeds" (T007)
Task: "Create customer-360 staging models" (T008)
Task: "Create customer-360 intermediate models" (T009)
Task: "Create customer-360 mart model" (T010)
Task: "Create customer-360 schema tests" (T011)
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 Only)

1. Complete Phase 1: Setup (T001-T005, T048, T065)
2. Complete Phase 2: Demo Data Products (T006-T025, T024a)
3. Complete Phase 3: US1 Bootstrap (T026-T027)
4. Complete Phase 4: US2 Compilation (T028)
5. Complete Phase 5: US3 Pipeline (T029-T035)
6. **STOP and VALIDATE**: Platform bootstraps, compiles, and executes all 3 pipelines

### Incremental Delivery

1. Setup + Data Products → Foundation ready
2. US1 (Bootstrap) → Platform deploys and responds (MVP!)
3. US2 (Compilation) → All products compile correctly
4. US3 (Pipeline) → Data flows end-to-end through medallion layers
5. US4 (Observability) → Traces and lineage visible
6. US5-US7 (Plugins, Security, Promotion) → Platform features validated
7. US8 (Demo Mode) → `make demo` works end-to-end
8. US9 (Schema Evolution) → Advanced capabilities proven
9. Phase 13 (Test Quality Hardening, T051-T065) → All tests audit-proof, zero anti-patterns

---

## Notes

- All test files use `@pytest.mark.requirement("13-FR-XXX")` markers for traceability
- All test classes inherit from IntegrationTestBase for service health checking
- All tests use unique namespaces via `self.generate_unique_namespace()`
- Seed CSVs include `_loaded_at` column for retention cleanup
- dbt models use `{{ current_timestamp() }}` macro to populate `_loaded_at`
- Iceberg snapshot expiry: keep_last=6 (covers 1 hour at 10-min intervals)
