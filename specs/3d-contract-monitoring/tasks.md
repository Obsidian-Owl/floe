# Tasks: Contract Monitoring

**Input**: Design documents from `/specs/3d-contract-monitoring/`
**Prerequisites**: plan.md, spec.md, data-model.md, research.md, contracts/

**Tests**: Tests are included (TDD approach) per project testing standards.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **floe-core package**: `packages/floe-core/src/floe_core/`
- **floe-core tests**: `packages/floe-core/tests/`
- **Alert channel plugins**: `plugins/floe-alert-{name}/`
- **Root contract tests**: `tests/contract/`
- **Helm charts**: `charts/floe-platform/templates/contract-monitor/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, module structure, and dependency configuration

- [ ] T001 Create monitoring module package structure: `packages/floe-core/src/floe_core/contracts/monitoring/__init__.py`, `checks/__init__.py`, `db/__init__.py`
- [ ] T002 [P] Add monitoring dependencies to `packages/floe-core/pyproject.toml`: sqlalchemy[asyncio]>=2.0, asyncpg>=0.29.0, httpx>=0.25.0
- [ ] T003 [P] Create alert channel plugin package scaffolds: `plugins/floe-alert-webhook/`, `plugins/floe-alert-slack/`, `plugins/floe-alert-email/`, `plugins/floe-alert-alertmanager/` with pyproject.toml, src/, tests/ structure
- [ ] T004 [P] Create test directory structure: `packages/floe-core/tests/unit/contracts/monitoring/`, `packages/floe-core/tests/integration/contracts/monitoring/`, `tests/contract/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models, plugin ABC, and plugin type extension that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Implement ViolationType and ViolationSeverity enums in `packages/floe-core/src/floe_core/contracts/monitoring/violations.py`
- [ ] T006 Implement ContractViolationEvent frozen Pydantic model in `packages/floe-core/src/floe_core/contracts/monitoring/violations.py`
- [ ] T007 [P] Implement CheckStatus enum and CheckResult frozen Pydantic model in `packages/floe-core/src/floe_core/contracts/monitoring/violations.py`
- [ ] T008 [P] Implement MonitoringConfig model hierarchy (CheckIntervalConfig, SeverityThresholds, AlertChannelRoutingRule, AlertConfig, MonitoringConfig) in `packages/floe-core/src/floe_core/contracts/monitoring/config.py`
- [ ] T009 [P] Implement SLAStatus and SLAComplianceReport models in `packages/floe-core/src/floe_core/contracts/monitoring/sla.py`
- [ ] T010 [P] Implement RegisteredContract model in `packages/floe-core/src/floe_core/contracts/monitoring/config.py`
- [ ] T011 Add ALERT_CHANNEL to PluginType enum in `packages/floe-core/src/floe_core/plugin_types.py`
- [ ] T012 Implement AlertChannelPlugin ABC extending PluginMetadata in `packages/floe-core/src/floe_core/plugins/alert_channel.py` with send_alert(), validate_config() abstract methods
- [ ] T013 Register `floe.alert_channels` entry point group in plugin registry discovery in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T014 Implement BaseCheck ABC in `packages/floe-core/src/floe_core/contracts/monitoring/checks/base.py` with execute() method, common check interface

### Foundational Tests

- [ ] T015 [P] Unit tests for ViolationType, ViolationSeverity, ContractViolationEvent, CheckResult in `packages/floe-core/tests/unit/contracts/monitoring/test_violations.py` — validation, serialization, frozen immutability, extra=forbid
- [ ] T016 [P] Unit tests for MonitoringConfig hierarchy in `packages/floe-core/tests/unit/contracts/monitoring/test_config.py` — defaults, validation, frozen immutability
- [ ] T017 [P] Unit tests for SLAStatus, SLAComplianceReport in `packages/floe-core/tests/unit/contracts/monitoring/test_sla.py`
- [ ] T018 [P] Contract test for AlertChannelPlugin ABC compliance in `tests/contract/test_alert_channel_plugin_contract.py` — verify interface contract, entry point discovery pattern
- [ ] T019 [P] Contract test for ContractViolationEvent schema stability in `tests/contract/test_violation_event_contract.py` — schema snapshot, backward compatibility

**Checkpoint**: Foundation ready — all models, enums, plugin ABC, and plugin type registered. User story implementation can now begin.

---

## Phase 3: User Story 1 — SLA Violation Detection and Alerting (Priority: P1)

**Goal**: Detect freshness SLA violations, emit OpenLineage FAIL events, export OTel metrics, and route alerts through configured channels. This is the core monitor-detect-alert loop.

**Independent Test**: Single monitored contract with mock data source and test alert channel proves end-to-end violation detection and alerting.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T020 [P] [US1] Unit tests for FreshnessCheck in `packages/floe-core/tests/unit/contracts/monitoring/test_freshness.py` — positive (data fresh), negative (stale data), clock skew tolerance, missing timestamp column
- [ ] T021 [P] [US1] Unit tests for ContractMonitor lifecycle in `packages/floe-core/tests/unit/contracts/monitoring/test_monitor.py` — register/unregister contract, start/stop, health endpoint
- [ ] T022 [P] [US1] Unit tests for async scheduler in `packages/floe-core/tests/unit/contracts/monitoring/test_scheduler.py` — interval scheduling, no overlap, skip on overrun
- [ ] T023 [P] [US1] Unit tests for severity assignment logic in `packages/floe-core/tests/unit/contracts/monitoring/test_violations.py` (append) — 80% INFO, 90% WARNING, breach ERROR, >3 in 24h CRITICAL
- [ ] T024 [P] [US1] Unit tests for OpenLineage event emission in `packages/floe-core/tests/unit/contracts/monitoring/test_events.py` — FAIL event with contractViolation facet, W3C trace context

### Implementation for User Story 1

- [ ] T025 [US1] Implement FreshnessCheck in `packages/floe-core/src/floe_core/contracts/monitoring/checks/freshness.py` — timestamp comparison, clock skew tolerance, SLA threshold evaluation
- [ ] T026 [US1] Implement severity assignment logic in `packages/floe-core/src/floe_core/contracts/monitoring/violations.py` — calculate_severity() function using SeverityThresholds config
- [ ] T027 [US1] Implement async scheduler in `packages/floe-core/src/floe_core/contracts/monitoring/scheduler.py` — interval-based scheduling, no-overlap guard, skip-on-overrun
- [ ] T028 [US1] Implement OpenLineage event emission utility in `packages/floe-core/src/floe_core/contracts/monitoring/events.py` — emit_violation_event() creating FAIL RunEvent with contractViolation facet, retrieve HTTP transport config from LineageBackendPlugin.get_transport_config() for event delivery
- [ ] T029 [US1] Implement OTel metric instrumentation via MetricRecorder in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py` — floe_contract_violations_total, floe_contract_freshness_seconds, floe_contract_check_duration_seconds. Include W3C trace context propagation via opentelemetry.context in span creation (FR-035).
- [ ] T030 [US1] Implement ContractMonitor class in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py` — register_contract(), unregister_contract(), start(), stop(), health_check(), run_check()
- [ ] T031 [US1] Wire FreshnessCheck into ContractMonitor.run_check() dispatch in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py`

**Checkpoint**: Freshness violation detection works end-to-end: schedule check → detect violation → assign severity → emit OTel metrics → emit OpenLineage FAIL event. Alert routing deferred to US3.

---

## Phase 4: User Story 2 — Schema Drift Detection (Priority: P1)

**Goal**: Detect schema drift between contract definition and actual table schema via ComputePlugin queries.

**Independent Test**: Mock compute engine returning controllable schemas proves drift detection for added, removed, and type-changed columns.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T032 [P] [US2] Unit tests for SchemaDriftCheck in `packages/floe-core/tests/unit/contracts/monitoring/test_schema_drift.py` — column added, column removed, type changed, nullability changed, exact match (no drift), multiple drifts

### Implementation for User Story 2

- [ ] T033 [US2] Implement SchemaDriftCheck in `packages/floe-core/src/floe_core/contracts/monitoring/checks/schema_drift.py` — query actual schema via CatalogPlugin.connect().load_table().schema(), map Iceberg types to contract schema types, compare using SchemaComparisonResult, emit violations per drift. Supports any CatalogPlugin implementation (FR-014).
- [ ] T034 [US2] Wire SchemaDriftCheck into ContractMonitor.run_check() dispatch in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py`

**Checkpoint**: Schema drift detection works. Monitor detects added/removed/changed columns and emits violations with expected vs actual details.

---

## Phase 5: User Story 3 — Alert Channel Configuration and Routing (Priority: P2)

**Goal**: Route violations to appropriate alert channels based on severity, with deduplication and rate limiting. Implement all 4 default channel plugins.

**Independent Test**: Mock alert channels with synthetic violations prove severity-based routing, deduplication, and rate limiting.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T035 [P] [US3] Unit tests for AlertRouter in `packages/floe-core/tests/unit/contracts/monitoring/test_alert_router.py` — severity routing rules, deduplication (30min window), rate limiting (N per contract per window), multiple channels, no channels configured
- [ ] T036 [P] [US3] Unit tests for CloudEvents webhook channel in `plugins/floe-alert-webhook/tests/unit/test_plugin.py` — CloudEvents v1.0 envelope format, content-type headers, HTTP POST, error handling
- [ ] T037 [P] [US3] Unit tests for Slack channel in `plugins/floe-alert-slack/tests/unit/test_plugin.py` — Slack Block Kit formatting, webhook POST, error handling
- [ ] T038 [P] [US3] Unit tests for Email channel in `plugins/floe-alert-email/tests/unit/test_plugin.py` — SMTP sending, HTML formatting, SecretStr for credentials
- [ ] T039 [P] [US3] Unit tests for Alertmanager channel in `plugins/floe-alert-alertmanager/tests/unit/test_plugin.py` — Alertmanager HTTP API format, label mapping, error handling

### Implementation for User Story 3

- [ ] T040 [US3] Implement AlertRouter in `packages/floe-core/src/floe_core/contracts/monitoring/alert_router.py` — evaluate routing rules, deduplication via alert_dedup_state, rate limiting per contract
- [ ] T041 [P] [US3] Implement CloudEvents webhook channel plugin in `plugins/floe-alert-webhook/src/floe_alert_webhook/plugin.py` — CloudEvents v1.0 envelope, httpx POST, entry point registration
- [ ] T042 [P] [US3] Implement Slack channel plugin in `plugins/floe-alert-slack/src/floe_alert_slack/plugin.py` — Slack Block Kit message, httpx POST to webhook URL, entry point registration
- [ ] T043 [P] [US3] Implement Email channel plugin in `plugins/floe-alert-email/src/floe_alert_email/plugin.py` — SMTP sending, HTML template, SecretStr for credentials, entry point registration
- [ ] T044 [P] [US3] Implement Alertmanager channel plugin in `plugins/floe-alert-alertmanager/src/floe_alert_alertmanager/plugin.py` — Alertmanager HTTP API, label mapping from violation, entry point registration
- [ ] T045 [US3] Wire AlertRouter into ContractMonitor — on violation, pass to AlertRouter.route() for dispatch in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py`

**Checkpoint**: Full alert pipeline works: violation → severity evaluation → routing rules → dedup/rate limit → channel dispatch. All 4 default channels implemented and registered.

---

## Phase 6: User Story 4 — Quality Monitoring via DataQualityPlugin (Priority: P2)

**Goal**: Invoke DataQualityPlugin to validate data quality expectations, score results, and emit violations when quality drops below thresholds.

**Independent Test**: Mock DataQualityPlugin returning controllable results proves quality scoring and violation emission.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T046 [P] [US4] Unit tests for QualityCheck in `packages/floe-core/tests/unit/contracts/monitoring/test_quality.py` — quality below threshold, quality above threshold, multiple expectations, plugin unavailable (graceful skip), weighted score calculation

### Implementation for User Story 4

- [ ] T047 [US4] Implement QualityCheck in `packages/floe-core/src/floe_core/contracts/monitoring/checks/quality.py` — invoke QualityPlugin.run_checks() (or run_suite() with explicit config), QualityPlugin.calculate_quality_score() for scoring, handle plugin unavailability gracefully (skip with WARNING)
- [ ] T048 [US4] Wire QualityCheck into ContractMonitor.run_check() dispatch and add floe_contract_quality_score gauge in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py`

**Checkpoint**: Quality monitoring works. DataQualityPlugin integration validates quality expectations and emits scored violations.

---

## Phase 7: User Story 5 — Availability Monitoring (Priority: P2)

**Goal**: Check data source availability via ping queries, track uptime over rolling 24h window, and alert when availability drops below SLA threshold.

**Independent Test**: Mock compute engine simulating intermittent failures proves uptime tracking, consecutive failure counting, and SLA threshold alerting.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T049 [P] [US5] Unit tests for AvailabilityCheck in `packages/floe-core/tests/unit/contracts/monitoring/test_availability.py` — ping success, ping failure, timeout handling, consecutive failures, rolling 24h window, recovery reset, availability ratio calculation

### Implementation for User Story 5

- [ ] T050 [US5] Implement AvailabilityCheck in `packages/floe-core/src/floe_core/contracts/monitoring/checks/availability.py` — use ComputePlugin.validate_connection() for health ping (returns ConnectionResult with status + latency_ms), timeout handling, rolling 24h window tracking, consecutive failure count, uptime percentage
- [ ] T051 [US5] Wire AvailabilityCheck into ContractMonitor.run_check() dispatch and add floe_contract_availability_ratio gauge in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py`

**Checkpoint**: All 4 check types operational. Monitor executes freshness, schema drift, quality, and availability checks at configured intervals.

---

## Phase 8: User Story 1+2+3 Integration — PostgreSQL Persistence & OTel (Priority: P1/P2)

**Goal**: Persist check results, violations, and SLA status to PostgreSQL. Emit all OTel metrics and OpenLineage events from live monitoring. This phase integrates the persistence and observability layers across US1-US3.

**Independent Test**: Integration tests with real PostgreSQL validate data persistence, retention, and OTel metric emission.

### Tests for Phase 8

- [ ] T052 [P] Unit tests for SQLAlchemy models and repository in `packages/floe-core/tests/unit/contracts/monitoring/test_db_models.py` — model field mapping, query builders
- [ ] T053 [P] Integration test for PostgreSQL persistence in `packages/floe-core/tests/integration/contracts/monitoring/test_db_persistence.py` — write/read check results, write/read violations, SLA status upsert, retention cleanup
- [ ] T054 [P] Integration test for OTel metric emission in `packages/floe-core/tests/integration/contracts/monitoring/test_otel_metrics.py` — verify all 5 metrics emitted with correct labels
- [ ] T055 [P] Integration test for OpenLineage event emission in `packages/floe-core/tests/integration/contracts/monitoring/test_openlineage_events.py` — verify FAIL events with contractViolation facet

### Implementation for Phase 8

- [ ] T056 Implement SQLAlchemy async models for monitoring tables in `packages/floe-core/src/floe_core/contracts/monitoring/db/models.py` — ContractCheckResultModel, ContractViolationModel, ContractSLAStatusModel, ContractDailyAggregateModel, RegisteredContractModel, AlertDedupStateModel
- [ ] T057 Implement data access repository in `packages/floe-core/src/floe_core/contracts/monitoring/db/repository.py` — MonitoringRepository with save_check_result(), save_violation(), upsert_sla_status(), get_violations(), get_daily_aggregates(), cleanup_expired()
- [ ] T058 Create Alembic migration scripts for monitoring schema in `packages/floe-core/src/floe_core/contracts/monitoring/db/migrations/`
- [ ] T059 Wire PostgreSQL persistence into ContractMonitor — persist check results and violations after each check run in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py`
- [ ] T060 Implement contract discovery on cold start — restore from DB primary; if DB empty/unavailable, fall back to CatalogPlugin.list_namespaces()/list_tables() to discover tables, then match against contract definitions from platform manifest to build registered contract set in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py`

**Checkpoint**: Full persistence layer operational. Check results, violations, and SLA status persisted to PostgreSQL. OTel metrics and OpenLineage events emitted correctly.

---

## Phase 9: User Story 6 — SLA Compliance Reporting (Priority: P3)

**Goal**: Calculate SLA compliance over configurable windows, provide trend analysis, and expose via library API and CLI command.

**Independent Test**: Pre-populated monitoring history data proves compliance calculations, trend analysis, and CLI output formatting.

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T061 [P] [US6] Unit tests for SLA compliance calculation in `packages/floe-core/tests/unit/contracts/monitoring/test_sla.py` (append) — daily/weekly/monthly windows, 100% compliance, partial compliance, trend detection (improving/degrading/stable)
- [ ] T062 [P] [US6] Unit tests for `floe sla report` CLI command in `packages/floe-core/tests/unit/cli/test_sla_report.py` — table output, JSON output, contract filter, time window filter

### Implementation for User Story 6

- [ ] T063 [US6] Implement SLA compliance calculation engine in `packages/floe-core/src/floe_core/contracts/monitoring/sla.py` — calculate_compliance() for rolling windows, aggregate_daily(), compute_trend()
- [ ] T064 [US6] Implement historical trend analysis from daily aggregates in `packages/floe-core/src/floe_core/contracts/monitoring/sla.py`
- [ ] T065 [US6] Create CLI command group `sla` in `packages/floe-core/src/floe_core/cli/sla/__init__.py`
- [ ] T066 [US6] Implement `floe sla report` CLI command in `packages/floe-core/src/floe_core/cli/sla/report.py` — Click command with --contract, --window, --format options
- [ ] T067 [US6] Register `sla` command group in main CLI entry point in `packages/floe-core/src/floe_core/cli/__init__.py`
- [ ] T068 [US6] Implement data retention cleanup job (90-day raw, keep aggregates) in `packages/floe-core/src/floe_core/contracts/monitoring/db/repository.py`

**Checkpoint**: SLA reporting works. Compliance percentages calculated over configurable windows, trends identified, accessible via library API and CLI.

---

## Phase 10: User Story 7 — Incident Management Integration (Priority: P3)

**Goal**: Map critical violations to incidents, correlate repeated violations to open incidents, prevent duplicate incident creation.

**Independent Test**: Mock incident management channel proves severity-to-priority mapping and violation correlation.

### Tests for User Story 7

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T069 [P] [US7] Unit tests for incident management alert channel pattern in `packages/floe-core/tests/unit/contracts/monitoring/test_incident.py` — severity-to-priority mapping, incident creation, duplicate correlation by contract identifier

### Implementation for User Story 7

- [ ] T070 [US7] Implement incident management alert channel pattern in `packages/floe-core/src/floe_core/contracts/monitoring/alert_router.py` — severity-to-priority mapping, incident correlation logic (by contract_name + violation_type)
- [ ] T071 [US7] Implement violation correlation for open incidents in `packages/floe-core/src/floe_core/contracts/monitoring/alert_router.py` — check for existing open incident, add comment vs create new

**Checkpoint**: Incident management integration works. Critical violations create incidents, repeated violations correlate to existing open incidents.

---

## Phase 11: Consumer Impact & Root Cause Analysis

**Purpose**: Cross-cutting enhancements that enrich violation context

- [ ] T072 [P] Unit tests for consumer impact analysis in `packages/floe-core/tests/unit/contracts/monitoring/test_consumer_impact.py` — identify downstream consumers, include in alert payloads
- [ ] T073 Implement consumer impact analysis via contract dependency metadata in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py` — resolve affected_consumers from contract metadata, populate ContractViolationEvent.affected_consumers
- [ ] T074 [P] Unit tests for root cause analysis context in `packages/floe-core/tests/unit/contracts/monitoring/test_root_cause.py` — recent pipeline runs, upstream status, historical pattern
- [ ] T075 Implement root cause analysis context enrichment in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py` — attach recent runs, upstream check status, historical violations to violation metadata

---

## Phase 12: Per-Contract Overrides & Custom Metrics

**Purpose**: Advanced configuration capabilities

- [ ] T076 [P] Unit tests for per-contract monitoring overrides in `packages/floe-core/tests/unit/contracts/monitoring/test_config.py` (append) — custom intervals, custom alert channels, custom severity rules override global config
- [ ] T077 Implement per-contract monitoring overrides in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py` — merge RegisteredContract.monitoring_overrides with global MonitoringConfig
- [ ] T078 [P] Unit tests for custom metric definitions in `packages/floe-core/tests/unit/contracts/monitoring/test_custom_metrics.py` — register custom metric, emit custom metric
- [ ] T079 Implement custom metric definitions in `packages/floe-core/src/floe_core/contracts/monitoring/monitor.py` — load custom metrics from config, register via MetricRecorder

---

## Phase 13: Helm Chart & K8s Deployment

**Purpose**: Deploy ContractMonitor as K8s service

- [ ] T080 [P] Create Helm Deployment template in `charts/floe-platform/templates/contract-monitor/deployment.yaml` — container spec, resource requests/limits, env vars, probe paths
- [ ] T081 [P] Create Helm Service template in `charts/floe-platform/templates/contract-monitor/service.yaml`
- [ ] T082 [P] Create Helm ConfigMap template in `charts/floe-platform/templates/contract-monitor/configmap.yaml` — monitoring config from values.yaml
- [ ] T083 [P] Create Helm ServiceAccount template in `charts/floe-platform/templates/contract-monitor/serviceaccount.yaml`
- [ ] T084 Add contract-monitor values to `charts/floe-platform/values.yaml` — image, replicas, resources, monitoring config, PostgreSQL connection
- [ ] T085 Helm chart validation tests via `helm template` and `helm lint` in CI

**Checkpoint**: ContractMonitor deployable as K8s service via Helm chart.

---

## Phase 14: End-to-End Integration & Polish

**Purpose**: Full integration validation and cross-cutting concerns

- [ ] T086 Integration test: ContractMonitor full lifecycle in `packages/floe-core/tests/integration/contracts/monitoring/test_monitor_integration.py` — start monitor, register contract, run checks, detect violation, persist result, emit metrics, emit lineage, route alert, stop monitor
- [ ] T087 [P] Integration test: CLI end-to-end with populated data in `packages/floe-core/tests/integration/cli/test_sla_cli.py` — `floe sla report` with real DB data
- [ ] T088 [P] Validate OpenLineage contractViolation facet against JSON schema in `tests/contract/test_violation_event_contract.py` (append) — validate emitted events match `contracts/contract-violation-facet.json`
- [ ] T089 Export module public API in `packages/floe-core/src/floe_core/contracts/monitoring/__init__.py` — export ContractMonitor, ContractViolationEvent, MonitoringConfig, AlertRouter, CheckResult, SLAStatus, all check types
- [ ] T090 Run quickstart.md validation — verify setup instructions work on clean checkout

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — core detection loop
- **US2 (Phase 4)**: Depends on Foundational — can run in parallel with US1
- **US3 (Phase 5)**: Depends on Foundational + ContractViolationEvent (T006) — can run in parallel with US1/US2
- **US4 (Phase 6)**: Depends on Foundational + BaseCheck (T014) — can run in parallel with US1/US2/US3
- **US5 (Phase 7)**: Depends on Foundational + BaseCheck (T014) — can run in parallel with US1/US2/US3/US4
- **Persistence (Phase 8)**: Depends on US1 (ContractMonitor exists) — integrates persistence
- **US6 (Phase 9)**: Depends on Persistence (Phase 8) — needs DB data
- **US7 (Phase 10)**: Depends on US3 (AlertRouter exists)
- **Consumer Impact (Phase 11)**: Depends on US1 (ContractMonitor exists)
- **Overrides (Phase 12)**: Depends on US1 (ContractMonitor exists) + Config models
- **Helm (Phase 13)**: Depends on US1 (ContractMonitor runnable) — can start after Phase 3
- **E2E (Phase 14)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **US2 (P1)**: Can start after Foundational (Phase 2) — Independent of US1
- **US3 (P2)**: Can start after Foundational (Phase 2) — Independent, but AlertRouter wiring (T045) needs ContractMonitor (US1)
- **US4 (P2)**: Can start after Foundational (Phase 2) — Independent, but wiring (T048) needs ContractMonitor (US1)
- **US5 (P2)**: Can start after Foundational (Phase 2) — Independent, but wiring (T051) needs ContractMonitor (US1)
- **US6 (P3)**: Depends on Persistence (Phase 8) for DB queries
- **US7 (P3)**: Depends on US3 (AlertRouter) for incident channel routing

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before wiring
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks (T001-T004) can run in parallel
- All Foundational model tasks (T005-T014) can run in parallel after T001
- All Foundational test tasks (T015-T019) can run in parallel
- US1 and US2 can proceed in parallel (both P1)
- US3, US4, US5 can proceed in parallel (all P2, different files)
- All 4 alert channel implementations (T041-T044) can run in parallel
- Helm chart templates (T080-T084) can run in parallel
- Phase 11 and Phase 12 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (write first, ensure they FAIL):
Task: "Unit tests for FreshnessCheck" (test_freshness.py)
Task: "Unit tests for ContractMonitor lifecycle" (test_monitor.py)
Task: "Unit tests for async scheduler" (test_scheduler.py)
Task: "Unit tests for severity assignment" (test_violations.py)
Task: "Unit tests for OpenLineage events" (test_events.py)

# Then launch parallel implementations:
Task: "Implement FreshnessCheck" (checks/freshness.py)
Task: "Implement severity assignment" (violations.py)
Task: "Implement async scheduler" (scheduler.py)
Task: "Implement OpenLineage emission" (events.py)
```

## Parallel Example: User Story 3 (Alert Channels)

```bash
# All 4 channel plugin tests in parallel:
Task: "Unit tests for webhook channel" (floe-alert-webhook)
Task: "Unit tests for Slack channel" (floe-alert-slack)
Task: "Unit tests for Email channel" (floe-alert-email)
Task: "Unit tests for Alertmanager channel" (floe-alert-alertmanager)

# All 4 channel implementations in parallel:
Task: "Implement webhook channel plugin" (floe-alert-webhook)
Task: "Implement Slack channel plugin" (floe-alert-slack)
Task: "Implement Email channel plugin" (floe-alert-email)
Task: "Implement Alertmanager channel plugin" (floe-alert-alertmanager)
```

---

## Implementation Strategy

### MVP First (User Stories 1+2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (freshness detection)
4. Complete Phase 4: User Story 2 (schema drift detection)
5. **STOP and VALIDATE**: Two core check types working, violations emitted
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 → Core detection (MVP!)
3. US3 → Alert routing (actionable alerts!)
4. US4 + US5 → All 4 check types operational
5. Phase 8 → Persistence + observability
6. US6 → SLA reporting
7. US7 → Incident management
8. Phases 11-14 → Advanced features + deployment

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (freshness + monitor core)
   - Developer B: US2 (schema drift)
   - Developer C: US3 (alert channels — 4 plugins)
3. Next wave:
   - Developer A: US4 + US5 (quality + availability)
   - Developer B: Phase 8 (persistence)
   - Developer C: US6 + US7 (reporting + incidents)
4. Final wave: Helm, E2E, polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All Pydantic models use ConfigDict(frozen=True, extra="forbid") per constitution
- All async methods use async/await per ADR-0028
- MetricRecorder (OTel API) for all metrics — NOT prometheus_client
- @pytest.mark.requirement() on ALL tests
- Type hints on ALL functions (mypy --strict)
