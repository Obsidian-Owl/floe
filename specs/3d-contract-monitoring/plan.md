# Implementation Plan: Contract Monitoring

**Branch**: `3d-contract-monitoring` | **Date**: 2026-02-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/3d-contract-monitoring/spec.md`

## Summary

Implement runtime contract monitoring for the floe platform (Epic 3D, Wave 7). The ContractMonitor is a long-lived K8s Deployment (Layer 3) that continuously checks data contracts for freshness, schema drift, quality, and availability violations. Violations are emitted as OpenLineage FAIL events with `contractViolation` facet, exported as OTel metrics, and routed through pluggable alert channels (AlertChannelPlugin ABC). The system is alert-only by default — violations do not block pipeline execution. Four default alert channels are provided: CloudEvents webhook, Slack, Email, and Alertmanager.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: pydantic>=2.0, opentelemetry-api>=1.39.0, opentelemetry-sdk>=1.20.0, structlog>=24.0, httpx>=0.25.0, sqlalchemy[asyncio]>=2.0, asyncpg>=0.29.0, click>=8.0
**Storage**: PostgreSQL (asyncpg + SQLAlchemy async) for monitoring state, 90-day raw retention + indefinite aggregates
**Testing**: pytest with Kind cluster (K8s-native), >80% coverage, @pytest.mark.requirement() on all tests
**Target Platform**: Kubernetes (Layer 3 Deployment)
**Project Type**: Monorepo package (floe-core + plugins)
**Performance Goals**: 100+ contracts monitored concurrently, <5s alert delivery latency, <10% schedule drift
**Constraints**: Alert-only enforcement (no pipeline blocking), fire-and-forget alert delivery, 90-day retention
**Scale/Scope**: 47 functional requirements, 7 user stories, ~60-70 tasks estimated

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package: monitoring core in floe-core, alert channel plugins as separate packages
- [x] No SQL parsing/validation in Python — schema comparison uses structured models, not SQL
- [x] No orchestration logic — post-materialize hook is in orchestrator plugin, not monitoring code

**Principle II: Plugin-First Architecture**
- [x] AlertChannelPlugin is a new ABC extending PluginMetadata
- [x] Alert channels registered via `floe.plugins.alert_channel` entry point
- [x] PluginMetadata declares name, version, floe_api_version for all channel plugins

**Principle III: Enforced vs Pluggable**
- [x] OpenTelemetry enforced: all metrics via MetricRecorder (OTel API)
- [x] OpenLineage enforced: FAIL events via LineageBackendPlugin transport
- [x] K8s-native: ContractMonitor deployed as K8s Deployment
- [x] Alert channels are pluggable: platform team selects and configures

**Principle IV: Contract-Driven Integration**
- [x] ContractViolationEvent (frozen Pydantic v2 model) is sole interface between monitor and channels
- [x] All schemas use Pydantic v2 with ConfigDict(frozen=True, extra="forbid")
- [x] No direct coupling between monitoring and alert implementation

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster with PostgreSQL, OTel Collector
- [x] No pytest.skip() usage
- [x] @pytest.mark.requirement() on all tests

**Principle VI: Security First**
- [x] All input validation via Pydantic models
- [x] Alert channel credentials (Slack webhooks, SMTP passwords) via SecretStr
- [x] No shell=True, no dynamic code execution
- [x] No PII in violation events or alert payloads

**Principle VII: Four-Layer Architecture**
- [x] ContractMonitor is Layer 3 (Services) — long-lived deployment
- [x] Configuration flows from manifest.yaml (Layer 2) to monitor (Layer 3)
- [x] Data engineers cannot override platform monitoring config

**Principle VIII: Observability By Default**
- [x] OTel metrics: 5 metric types via MetricRecorder
- [x] OTel spans: trace context on all check executions
- [x] OpenLineage: FAIL events with contractViolation facet

**Result**: ALL GATES PASS. No violations.

## Integration Design

### Entry Point Integration
- [x] ContractMonitor reachable as K8s Deployment (Layer 3 service)
- [x] `floe sla report` CLI command added to `packages/floe-core/src/floe_core/cli/sla/`
- [x] AlertChannelPlugin discoverable via plugin registry
- [x] Wiring tasks needed: CLI registration, plugin type enum, Helm chart

### Dependency Integration
| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| DataContract, SLAProperties | floe-core (schemas) | Import from `floe_core.schemas.data_contract` |
| ContractValidator, SchemaComparisonResult | floe-core (enforcement) | Import from `floe_core.enforcement.validators` |
| PluginMetadata, PluginRegistry, PluginType | floe-core (plugins) | Extend PluginType enum, inherit PluginMetadata |
| MetricRecorder | floe-core (telemetry) | Import from `floe_core.telemetry.metrics` |
| LineageBackendPlugin | floe-core (plugins) | Use transport config for OpenLineage events |
| ComputePlugin | floe-core (plugins) | Availability pings via validate_connection() |
| QualityPlugin | floe-core (plugins) | run_checks(), calculate_quality_score() |
| CatalogPlugin | floe-core (plugins) | Schema queries via load_table().schema(), contract discovery on cold start via list_namespaces()/list_tables() |

### Produces for Others
| Output | Consumers | Contract |
|--------|-----------|----------|
| AlertChannelPlugin ABC | Alert channel plugin packages | `floe.alert_channels` entry point group |
| ContractViolationEvent | AlertChannelPlugins, CLI | Frozen Pydantic model |
| OTel metrics (`floe_contract_*`) | Prometheus/Grafana dashboards | OTel metric names and labels |
| OpenLineage FAIL events | Marquez/lineage tools | contractViolation facet schema |
| SLA compliance data | `floe sla report` CLI | SLAComplianceReport model |
| PostgreSQL schema | DB migrations | Alembic migrations |

### Cleanup Required
- None — this is a new feature, no existing code is being replaced

## Project Structure

### Documentation (this feature)

```text
specs/3d-contract-monitoring/
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Entity models and DB schema
├── quickstart.md        # Developer setup guide
├── contracts/           # API contracts
│   └── contract-violation-facet.json  # OpenLineage facet schema
└── tasks.md             # Generated by /speckit.tasks
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── contracts/
│   └── monitoring/                    # NEW: Core monitoring module
│       ├── __init__.py
│       ├── monitor.py                 # ContractMonitor class
│       ├── scheduler.py               # Async check scheduler
│       ├── checks/                    # Check type implementations
│       │   ├── __init__.py
│       │   ├── base.py                # BaseCheck ABC
│       │   ├── freshness.py           # FreshnessCheck
│       │   ├── schema_drift.py        # SchemaDriftCheck
│       │   ├── quality.py             # QualityCheck
│       │   └── availability.py        # AvailabilityCheck
│       ├── violations.py              # ContractViolationEvent model
│       ├── config.py                  # MonitoringConfig model
│       ├── sla.py                     # SLAStatus, SLAComplianceReport
│       ├── db/                        # PostgreSQL persistence
│       │   ├── __init__.py
│       │   ├── models.py              # SQLAlchemy models
│       │   ├── repository.py          # Data access layer
│       │   └── migrations/            # Alembic migrations
│       └── events.py                  # OpenLineage event emission
├── plugins/
│   └── alert_channel.py               # NEW: AlertChannelPlugin ABC
├── plugin_types.py                    # MODIFY: Add ALERT_CHANNEL
├── cli/
│   └── sla/                           # NEW: SLA CLI commands
│       ├── __init__.py
│       └── report.py                  # floe sla report
└── telemetry/
    └── metrics.py                     # EXISTING: MetricRecorder (no changes)

plugins/
├── floe-alert-webhook/               # NEW: CloudEvents webhook channel
│   ├── pyproject.toml
│   ├── src/floe_alert_webhook/
│   │   ├── __init__.py
│   │   └── plugin.py
│   └── tests/
│       └── unit/
├── floe-alert-slack/                  # NEW: Slack channel
│   ├── pyproject.toml
│   ├── src/floe_alert_slack/
│   │   ├── __init__.py
│   │   └── plugin.py
│   └── tests/
│       └── unit/
├── floe-alert-email/                  # NEW: Email (SMTP) channel
│   └── ...
└── floe-alert-alertmanager/           # NEW: Alertmanager channel
    └── ...

packages/floe-core/src/floe_core/contracts/monitoring/
└── alert_router.py                    # AlertRouter (severity routing, dedup, rate limiting)

charts/floe-platform/templates/
└── contract-monitor/                  # NEW: Helm templates
    ├── deployment.yaml
    ├── service.yaml
    ├── configmap.yaml
    └── serviceaccount.yaml

packages/floe-core/tests/
├── unit/
│   └── contracts/
│       └── monitoring/                # Unit tests for monitoring
│           ├── test_monitor.py
│           ├── test_scheduler.py
│           ├── test_freshness.py
│           ├── test_schema_drift.py
│           ├── test_quality.py
│           ├── test_availability.py
│           ├── test_violations.py
│           ├── test_config.py
│           ├── test_sla.py
│           ├── test_alert_router.py
│           └── test_events.py
├── integration/
│   └── contracts/
│       └── monitoring/                # Integration tests (K8s)
│           ├── test_monitor_integration.py
│           ├── test_db_persistence.py
│           ├── test_otel_metrics.py
│           └── test_openlineage_events.py
└── contract/                          # (Root-level already exists)
    └── test_violation_event_contract.py

tests/contract/
└── test_alert_channel_plugin_contract.py  # Root: cross-package plugin contract
```

**Structure Decision**: Monorepo package layout. Monitoring core is in `floe-core` under `contracts/monitoring/` (per epic file ownership). Alert channel plugins are separate plugin packages under `plugins/` following the established pattern. CLI commands extend the existing Click group structure. Helm charts extend the existing `charts/floe-platform/` chart.

## Implementation Phases

### Phase 1: Core Models & Plugin Infrastructure (Foundation)

**Goal**: Establish the data models, plugin ABC, and plugin type extension.

1. ContractViolationEvent frozen Pydantic model (violations.py)
2. MonitoringConfig Pydantic model from manifest schema (config.py)
3. CheckResult and CheckStatus models
4. SLAStatus and SLAComplianceReport models (sla.py)
5. AlertChannelPlugin ABC extending PluginMetadata (alert_channel.py)
6. Add ALERT_CHANNEL to PluginType enum (plugin_types.py)
7. Register `floe.alert_channels` in plugin registry discovery
8. Unit tests for all models (validation, serialization, edge cases)
9. Contract test: AlertChannelPlugin ABC compliance (root tests/contract/)

### Phase 2: Check Implementations (Monitoring Logic)

**Goal**: Implement the four check types with consistent patterns.

1. BaseCheck ABC (checks/base.py) — common interface for all check types
2. FreshnessCheck — timestamp comparison, clock skew tolerance (checks/freshness.py)
3. SchemaDriftCheck — query actual schema via CatalogPlugin.load_table().schema(), compare via SchemaComparisonResult (checks/schema_drift.py)
4. QualityCheck — DataQualityPlugin invocation, score calculation (checks/quality.py)
5. AvailabilityCheck — ComputePlugin.validate_connection() for ping, timeout handling, uptime tracking (checks/availability.py)
6. Severity assignment logic (80%/90%/ERROR/CRITICAL thresholds)
7. Unit tests for each check type (positive + negative + edge cases)

### Phase 3: Monitoring Engine (Scheduler & Orchestration)

**Goal**: Build the ContractMonitor service with scheduling and lifecycle.

1. Async scheduler (scheduler.py) — interval-based check scheduling, no overlap
2. ContractMonitor class (monitor.py) — register/unregister, start/stop, health endpoint
3. Contract discovery: DB primary; catalog fallback via CatalogPlugin.list_namespaces()/list_tables() to discover tables, matched against contract definitions in manifest (FR-004)
4. PostgreSQL persistence layer — SQLAlchemy async models, repository (db/)
5. Alembic migration scripts for monitoring schema
6. OpenLineage event emission utility (events.py) — uses LineageBackendPlugin.get_transport_config() for HTTP transport
7. OTel metric instrumentation via MetricRecorder (5 metrics)
8. Unit tests for scheduler, monitor lifecycle, DB persistence
9. Integration tests: PostgreSQL persistence, OTel metric emission

### Phase 4: Alert System (Router & Default Channels)

**Goal**: Implement alert routing and default channel plugins.

1. AlertRouter — severity routing, deduplication, rate limiting (alert_router.py)
2. CloudEvents webhook channel plugin (plugins/floe-alert-webhook/)
3. Slack incoming webhook channel plugin (plugins/floe-alert-slack/)
4. Email SMTP channel plugin (plugins/floe-alert-email/)
5. Alertmanager HTTP API channel plugin (plugins/floe-alert-alertmanager/)
6. Plugin entry point registration in each pyproject.toml
7. Unit tests for AlertRouter (routing rules, dedup, rate limiting)
8. Unit tests for each channel plugin (payload formatting, config validation)

### Phase 5: Reporting, CLI & Consumer Impact

**Goal**: Implement SLA reporting, CLI commands, and consumer analysis.

1. SLA compliance calculation engine (rolling 24h, daily/weekly/monthly)
2. Historical trend analysis (from daily aggregates)
3. Root cause analysis context (FR-047)
4. Consumer impact analysis via contract dependency metadata (FR-040, FR-041)
5. `floe sla report` CLI command (cli/sla/report.py)
6. Data retention cleanup job (90-day raw, keep aggregates)
7. Unit tests for compliance calculations, CLI output
8. Integration test: CLI end-to-end with populated data

### Phase 6: Helm Chart & K8s Deployment

**Goal**: Deploy ContractMonitor as K8s service.

1. Helm chart templates (deployment, service, configmap, serviceaccount)
2. Health probe endpoints (liveness + readiness)
3. Resource requests/limits, replica configuration
4. Integration with platform PostgreSQL
5. Helm chart validation tests
6. K8s deployment integration test (Kind cluster)

### Phase 7: Incident Management & Final Integration

**Goal**: Incident management channel and end-to-end validation.

1. Incident management alert channel pattern (FR-042, FR-043)
2. Violation correlation logic for open incidents
3. Per-contract monitoring overrides (FR-045)
4. Custom metric definitions (FR-046)
5. End-to-end integration test: violation -> alert -> metrics -> lineage
6. Documentation updates

## Complexity Tracking

No constitution violations. All design decisions align with established principles.

## Key Design Decisions

| Decision | Choice | Rationale | ADR |
|----------|--------|-----------|-----|
| Metrics API | MetricRecorder (OTel) | Established pattern, exports to any backend | ADR-0035 |
| Async engine | asyncio | I/O-heavy operations, ADR-0028 specifies async | ADR-0028 |
| State persistence | PostgreSQL + SQLAlchemy async | Already in platform stack, no new dependency | ADR-0028 |
| Alert interface | ContractViolationEvent | Frozen Pydantic model, sole contract | Constitution IV |
| Alert architecture | Plugin + AlertRouter | Plugin-first, severity routing, dedup, rate limiting | Constitution II |
| Enforcement mode | Alert-only (default) | No pipeline blocking per ADR-0028 | ADR-0028 |
| Contract discovery | DB primary + catalog fallback | Resilient cold start, fast recovery | Clarification |
| Availability window | Rolling 24h | Industry standard SLA calculation | Clarification |
| Severity thresholds | 80% INFO, 90% WARNING | Configurable, provides early warning buffer | Clarification |
| Data retention | 90 days raw + indefinite aggregates | Balances storage with trend analysis | Clarification |
| Reporting access | Library API + CLI | Both programmatic and operator-facing | Clarification |
