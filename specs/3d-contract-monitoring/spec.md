# Feature Specification: Contract Monitoring

**Epic**: 3D (Contract Monitoring)
**Feature Branch**: `3d-contract-monitoring`
**Created**: 2026-02-08
**Status**: Draft
**Input**: User description: "Epic-03d contract monitoring"

## Scope

### What's Included
- ContractMonitor service (K8s Deployment, Layer 3) with scheduled monitoring
- Four monitoring check types: Freshness, Schema Drift, Quality, Availability
- Contract violation detection and event emission
- AlertChannelPlugin ABC and AlertRouter for pluggable alert routing
- Default alert channels: CloudEvents webhook, Slack, Email, Alertmanager
- OpenTelemetry metrics export (Prometheus-compatible)
- OpenLineage FAIL events with `contractViolation` facet
- SLA compliance tracking and reporting
- Historical trend analysis and violation aggregation
- Incident management integration (REQ-265)
- Consumer impact analysis
- Custom metric definitions
- Monitoring configuration via platform manifest

### What's Excluded (Deferred)
- **Anomaly detection** (REQ-263) — deferred to future enhancement; requires ML capabilities beyond initial scope
- Enterprise-specific alert channel implementations (ServiceNow, PagerDuty, Opsgenie) — provided as separate plugin packages, not in core
- Grafana dashboard provisioning — documentation only; dashboards are operator-owned

### Integration Points

**Entry Points**:
- ContractMonitor K8s Deployment (Layer 3 service), registered via Helm chart
- `floe sla report` CLI command (floe-cli package) for SLA compliance reporting

**Dependencies**:
- floe-core: DataContract models (Epic 3C, complete), CompiledArtifacts
- Epic 6A (OpenTelemetry): TelemetryPlugin ABC, OTel SDK for metrics/traces
- Epic 6B (OpenLineage): LineagePlugin ABC, OpenLineage event emission
- QualityPlugin: run_checks(), calculate_quality_score() (Epic 5B)
- ComputePlugin: validate_connection() for availability pings (Epic 4A)
- CatalogPlugin: load_table().schema() for schema drift queries, list_namespaces()/list_tables() for cold start discovery (Epic 4C)

**Produces**:
- AlertChannelPlugin ABC (new plugin type, registered via `floe.alert_channels` entry point)
- ContractViolationEvent schema (frozen Pydantic model)
- AlertRouter (severity-based routing with deduplication and rate limiting)
- OpenTelemetry metrics: `floe_contract_violations_total`, `floe_contract_freshness_seconds`, `floe_contract_availability_ratio`, `floe_contract_quality_score`, `floe_contract_check_duration_seconds`
- OpenLineage FAIL events with `contractViolation` custom facet
- SLA compliance reports (programmatic and exportable)
- PostgreSQL schema for monitoring state persistence

## Assumptions

- Epic 3C (Data Contracts) is complete, providing DataContract, ContractVersion, SLAProperties, and lifecycle models
- Epic 6A (OpenTelemetry) provides a working TelemetryPlugin with metric export capabilities
- Epic 6B (OpenLineage) provides a working LineagePlugin with event emission capabilities
- PostgreSQL is available as a persistent backend (provided by platform infrastructure, Epic 9A/9B)
- Monitoring is alert-only by default (violations do NOT block pipeline execution, per ADR-0028)
- ODCS v3 standard is used for contract definitions (established in Epic 3C)
- Alert channel plugins follow the same entry point pattern as other floe plugin types

## User Scenarios & Testing *(mandatory)*

### User Story 1 - SLA Violation Detection and Alerting (Priority: P1)

A data consumer depends on a data product with a defined freshness SLA of "data must be no older than 2 hours." The ContractMonitor continuously checks freshness at 15-minute intervals. When the data exceeds the SLA threshold, the system detects the violation, emits an OpenLineage FAIL event, exports OTel metrics, and routes alerts through configured channels (e.g., Slack, webhook) so the responsible team can investigate.

**Why this priority**: This is the core value proposition of contract monitoring — detecting violations in real-time and ensuring the right people are notified. Without this, contracts are documentation-only with no runtime enforcement.

**Independent Test**: Can be fully tested with a single monitored contract, a mock data source with controllable timestamps, and a test alert channel. Delivers immediate value by proving the monitor-detect-alert loop works end-to-end.

**Acceptance Scenarios**:

1. **Given** a registered data contract with freshness SLA of 2 hours, **When** the ContractMonitor runs a freshness check and the data is 2.5 hours old, **Then** a contract violation is detected with severity ERROR, an OpenLineage FAIL event is emitted with `contractViolation` facet, OTel metric `floe_contract_violations_total` is incremented, and alerts are routed to configured channels.

2. **Given** a registered data contract with freshness SLA of 2 hours, **When** the ContractMonitor runs a freshness check and the data is 1.5 hours old (approaching threshold), **Then** the check passes with no violation, the metric `floe_contract_freshness_seconds` records the current age, and no alert is triggered.

3. **Given** a contract violation has already been alerted within the last 30 minutes, **When** the same violation is detected again on the next check cycle, **Then** the violation is recorded but the alert is deduplicated (not sent again) to prevent alert fatigue.

4. **Given** a registered contract with no alert channels configured, **When** a violation is detected, **Then** the violation is still recorded, metrics are emitted, and OpenLineage events are sent, but no alert channel delivery is attempted.

---

### User Story 2 - Schema Drift Detection (Priority: P1)

A platform operator needs assurance that data products conform to their declared schema contracts. The ContractMonitor periodically queries the actual table schema from the compute engine and compares it against the contract's schema definition. When columns are added, removed, or their types change unexpectedly, the system detects the drift and alerts the operator with a detailed diff of expected vs actual schema.

**Why this priority**: Schema drift is one of the most common causes of downstream pipeline failures. Early detection prevents cascading breakage across consuming data products.

**Independent Test**: Can be tested with a mock compute engine that returns controllable schemas. Delivers value by detecting drift between any contract and its underlying table.

**Acceptance Scenarios**:

1. **Given** a contract specifying columns [id: INT, name: STRING, amount: DECIMAL], **When** the actual table has an additional column [status: STRING], **Then** a schema drift violation is detected with type "column_added", including the unexpected column details.

2. **Given** a contract specifying column [amount: DECIMAL], **When** the actual column type is [amount: FLOAT], **Then** a schema drift violation is detected with type "type_changed", reporting expected DECIMAL vs actual FLOAT.

3. **Given** a contract specifying columns [id, name, amount], **When** the actual table is missing column [amount], **Then** a schema drift violation is detected with type "column_removed" and severity CRITICAL.

4. **Given** the schema matches the contract exactly, **When** the drift check runs, **Then** the check passes successfully, `floe_contract_check_duration_seconds` records the execution time, and no violation is emitted.

---

### User Story 3 - Alert Channel Configuration and Routing (Priority: P2)

A platform operator configures multiple alert channels (Slack for warnings, Alertmanager for critical, CloudEvents webhook for enterprise integration) in the platform manifest. When violations occur, the AlertRouter evaluates the violation severity, applies rate limiting and deduplication rules, and dispatches alerts to the appropriate channels based on configured routing rules.

**Why this priority**: Pluggable alert routing is what makes contract monitoring actionable in diverse environments. Without it, violations are only visible in metrics and logs.

**Independent Test**: Can be tested with mock alert channels and synthetic violations. Delivers value by proving that different severity levels route to different channels.

**Acceptance Scenarios**:

1. **Given** Slack configured for WARNING+ and Alertmanager for ERROR+, **When** a WARNING-severity freshness violation occurs, **Then** an alert is sent to Slack but NOT to Alertmanager.

2. **Given** a CloudEvents webhook channel configured, **When** any violation occurs, **Then** the violation is formatted as a CloudEvents v1.0 envelope and POSTed to the webhook URL with proper content-type headers.

3. **Given** rate limiting configured at 1 alert per contract per 30 minutes, **When** 5 violations for the same contract occur within 10 minutes, **Then** only the first violation triggers an alert delivery; subsequent violations within the window are suppressed with a log entry noting suppression.

4. **Given** an alert channel is unreachable (network error), **When** a violation alert delivery fails, **Then** the failure is logged with structured error details, the metric `floe_alert_delivery_failures_total` is incremented, and the alert is NOT retried (fire-and-forget with logging).

---

### User Story 4 - Quality Monitoring via DataQualityPlugin (Priority: P2)

A data engineer has defined quality expectations in their data contract (e.g., null rate < 5%, uniqueness on ID column). The ContractMonitor periodically invokes the DataQualityPlugin to execute these checks against live data. Results are scored, recorded, and violations are emitted when quality drops below thresholds.

**Why this priority**: Quality monitoring extends beyond schema and freshness to validate data correctness. It builds on the DataQualityPlugin infrastructure from Epic 5B.

**Independent Test**: Can be tested with a mock DataQualityPlugin implementation returning controllable results. Delivers value by proving the ContractMonitor correctly invokes, scores, and reports quality results.

**Acceptance Scenarios**:

1. **Given** a contract with quality expectation "null_rate < 0.05 on column email", **When** the quality check executes and finds null_rate = 0.12, **Then** a quality violation is emitted with the expected and actual values, and the quality score is calculated.

2. **Given** multiple quality expectations on a single contract, **When** the quality check runs, **Then** all expectations are evaluated, a weighted quality score is calculated, and individual failures are reported separately.

3. **Given** the DataQualityPlugin is unavailable (not installed), **When** the ContractMonitor attempts a quality check, **Then** the check is skipped with a WARNING log, the metric indicates the check was not executed, and no false violations are emitted.

---

### User Story 5 - Availability Monitoring (Priority: P2)

A data consumer's contract specifies 99.9% availability SLA. The ContractMonitor checks the data source availability every 5 minutes by issuing a lightweight ping query through the compute engine. It tracks uptime percentage, consecutive failures, and alerts when availability drops below the SLA threshold.

**Why this priority**: Availability monitoring is the simplest check type but critical for SLA compliance tracking. It provides the baseline health signal.

**Independent Test**: Can be tested with a mock compute engine that simulates intermittent failures. Delivers value by proving uptime tracking and SLA threshold alerting work.

**Acceptance Scenarios**:

1. **Given** an availability SLA of 99.9%, **When** the data source has been unreachable for 15 minutes (3 consecutive failures at 5-minute intervals), **Then** the current availability percentage drops below threshold, a violation is emitted, and the metric `floe_contract_availability_ratio` reflects the degradation.

2. **Given** the data source recovers after a failure, **When** the next availability check succeeds, **Then** the consecutive failure count resets, the availability percentage is recalculated, and a recovery event is logged (but not alerted unless configured).

3. **Given** an availability check times out, **When** the timeout exceeds the configured threshold (default 30 seconds), **Then** the check is recorded as a failure with reason "timeout".

---

### User Story 6 - SLA Compliance Reporting (Priority: P3)

A product owner wants periodic reports on data product SLA compliance. The system calculates uptime percentages, violation summaries, and trend analysis over configurable time windows (daily, weekly, monthly). Reports can be queried programmatically or exported.

**Why this priority**: Reporting enables governance accountability and trend visibility. It builds on all other monitoring data and is primarily a read-side concern.

**Independent Test**: Can be tested with pre-populated monitoring history data. Delivers value by proving compliance calculations and report generation work independently of live monitoring.

**Acceptance Scenarios**:

1. **Given** monitoring data for the past 30 days, **When** an SLA compliance report is generated for a data product, **Then** the report includes: overall uptime %, freshness SLA compliance %, quality score trend, total violations by type and severity.

2. **Given** no violations in the reporting period, **When** a report is generated, **Then** the report shows 100% compliance with zero violations and includes the monitoring coverage (how many checks were executed).

3. **Given** a request for weekly trend data, **When** the report is generated for the past 4 weeks, **Then** each week's metrics are independently calculated and trends (improving/degrading/stable) are indicated.

---

### User Story 7 - Incident Management Integration (Priority: P3)

A platform operator configures an incident management integration so that CRITICAL-severity violations automatically create incidents in the organization's incident management system. The integration uses the AlertChannelPlugin interface with a dedicated incident management channel that maps violation severity to incident priority.

**Why this priority**: Incident management integration bridges the gap between monitoring alerts and organizational response processes. It leverages the AlertChannelPlugin infrastructure.

**Independent Test**: Can be tested with a mock incident management channel. Delivers value by proving that critical violations trigger incident creation with correct severity mapping.

**Acceptance Scenarios**:

1. **Given** an incident management alert channel configured for CRITICAL violations, **When** a CRITICAL violation occurs (e.g., >3 repeated SLA breaches in 24h), **Then** an incident is created via the configured channel with mapped priority, violation details, and affected data product information.

2. **Given** an existing open incident for the same contract, **When** another CRITICAL violation occurs, **Then** the new violation is correlated with the existing incident (via contract identifier) and a comment/update is added rather than creating a duplicate incident.

---

### Edge Cases

- What happens when the ContractMonitor starts and no contracts are registered? The monitor enters an idle state, logs an INFO message, and checks for newly registered contracts at each scheduler tick.
- What happens when a contract is deleted while monitoring is active? The monitor detects the missing contract on the next check cycle, removes it from the active monitoring set, and logs a WARNING.
- What happens when the PostgreSQL backend is unavailable? The monitor continues running checks and emitting OTel/OpenLineage events but cannot persist history. A health probe failure is reported and the monitor enters a degraded state.
- What happens when clock skew exists between the monitor and data sources? Freshness calculations account for configurable clock skew tolerance (default 60 seconds). Violations within the tolerance window are not emitted.
- What happens when a check takes longer than the check interval? The next scheduled run is skipped (no overlapping runs), a WARNING is logged, and the metric `floe_contract_check_duration_seconds` records the overrun.
- What happens when multiple violations of different types occur simultaneously for the same contract? Each violation type is evaluated and reported independently. The AlertRouter groups them into a single alert batch per delivery cycle to avoid alert storms.

## Requirements *(mandatory)*

### Functional Requirements

#### Core Monitoring Engine

- **FR-001**: System MUST deploy ContractMonitor as a long-lived K8s Deployment (Layer 3) with configurable replicas, resource requests/limits, and liveness/readiness probes. *(REQ-245)*
- **FR-002**: System MUST persist monitoring state (check results, violation history, metrics) in a PostgreSQL backend with defined schema. Raw monitoring data MUST be retained for 90 days by default; daily/weekly aggregates MUST be retained indefinitely for trend analysis. *(REQ-245)*
- **FR-003**: System MUST schedule monitoring checks at configurable intervals per check type: freshness (default 15 min), schema drift (default 1 hour), quality (default 6 hours), availability (default 5 min). *(REQ-245, REQ-246, REQ-247, REQ-248, REQ-249)*
- **FR-004**: System MUST register contracts for monitoring when they are deployed (via post-materialize hook or API) and deregister them when contracts are retired. On startup, the monitor MUST restore its contract set from the PostgreSQL backend (primary) and fall back to scanning the CatalogPlugin for all deployed contracts with monitoring enabled if the database is empty or unavailable. *(REQ-256)*
- **FR-005**: System MUST provide a health endpoint that reports the monitor's operational status, including backend connectivity, last successful check times, and registered contract count. *(REQ-245)*
- **FR-006**: System MUST prevent overlapping check executions for the same contract and check type (skip if previous run still in progress). *(REQ-270)*

#### Freshness Monitoring

- **FR-007**: System MUST check data freshness by comparing the table's latest update timestamp against the current time and the contract's SLA freshness threshold. *(REQ-246, REQ-257)*
- **FR-008**: System MUST support configurable timestamp column detection (explicit column name in contract or auto-detect from table metadata). *(REQ-246)*
- **FR-009**: System MUST emit an OpenLineage FAIL event with `contractViolation` facet when freshness exceeds the SLA threshold. *(REQ-246, REQ-250)*
- **FR-010**: System MUST support clock skew tolerance (default 60 seconds, configurable) to prevent false freshness violations. *(REQ-257)*

#### Schema Drift Monitoring

- **FR-011**: System MUST query the actual table schema from the Iceberg catalog (via CatalogPlugin) and compare it against the contract's schema definition. *(REQ-247)*
- **FR-012**: System MUST detect schema changes including: added columns, removed columns, type changes, nullability changes, and constraint changes. *(REQ-247)*
- **FR-013**: System MUST emit an OpenLineage FAIL event with `contractViolation` facet for each detected drift, including expected and actual schema details. *(REQ-247, REQ-250)*
- **FR-014**: System MUST support schema queries across different catalog implementations (via CatalogPlugin interface). *(REQ-247)*

#### Quality Monitoring

- **FR-015**: System MUST invoke QualityPlugin.run_checks() to validate data quality expectations defined in the contract. *(REQ-248, REQ-258)*
- **FR-016**: System MUST calculate a weighted quality score via QualityPlugin.calculate_quality_score() combining dbt test results, DQ plugin checks, and custom checks. *(REQ-248)*
- **FR-017**: System MUST emit OpenLineage FAIL events for quality checks that fall below configured thresholds. *(REQ-248, REQ-250)*
- **FR-018**: System MUST gracefully handle unavailable QualityPlugin (skip check with WARNING, no false violations). *(REQ-248)*

#### Availability Monitoring

- **FR-019**: System MUST check data source availability via ComputePlugin.validate_connection(), which returns a ConnectionResult with health status and latency. *(REQ-249)*
- **FR-020**: System MUST track availability metrics over a rolling 24-hour window: uptime percentage, consecutive failure count, last failure time, and failure reasons. *(REQ-249)*
- **FR-021**: System MUST emit violations when availability drops below the contract's SLA threshold. *(REQ-249, REQ-250)*
- **FR-022**: System MUST handle check timeouts gracefully (default 30 seconds, configurable) and record them as failures. *(REQ-249)*

#### Violation Detection and Events

- **FR-023**: System MUST emit all contract violations as OpenLineage FAIL events with the `contractViolation` custom facet containing: contractName, contractVersion, violationType, severity, message, element, expectedValue, actualValue, timestamp. *(REQ-250, REQ-259)*
- **FR-024**: System MUST assign violation severity based on configurable rules: INFO (80% of SLA threshold consumed), WARNING (90% of SLA threshold consumed), ERROR (active violation — SLA breached), CRITICAL (>3 violations of the same type for the same contract within 24h). Severity escalation MUST be automatic based on these thresholds. *(REQ-259)*
- **FR-025**: System MUST NOT include PII or sensitive data in violation event messages or alert payloads. *(REQ-250)*

#### Alert Channel Plugin System

- **FR-026**: System MUST define an AlertChannelPlugin ABC with methods: send_alert(violation_event), validate_config(), health_check(). *(REQ-260)*
- **FR-027**: System MUST discover alert channel plugins via `floe.alert_channels` entry point group, following the standard plugin registration pattern. *(REQ-260)*
- **FR-028**: System MUST provide an AlertRouter that evaluates violation severity against channel routing rules (e.g., Slack for WARNING+, Alertmanager for ERROR+). *(REQ-260)*
- **FR-029**: System MUST implement alert deduplication: suppress repeated alerts for the same contract and violation type within a configurable window (default 30 minutes). *(REQ-260)*
- **FR-030**: System MUST implement alert rate limiting: maximum N alerts per contract per time window (configurable). *(REQ-260)*
- **FR-031**: System MUST provide default alert channel implementations: CloudEvents v1.0 webhook, Slack (incoming webhook), Email (SMTP), Alertmanager (HTTP API). *(REQ-260)*
- **FR-032**: System MUST format CloudEvents webhook payloads according to CloudEvents v1.0 specification with `ce-type: floe.contract.violation` and `ce-source: floe-contract-monitor`. *(REQ-260)*

#### OpenTelemetry Integration

- **FR-033**: System MUST export OTel metrics: `floe_contract_violations_total` (counter, labels: contract, type, severity), `floe_contract_freshness_seconds` (gauge), `floe_contract_availability_ratio` (gauge), `floe_contract_quality_score` (gauge), `floe_contract_check_duration_seconds` (histogram). *(REQ-268)*
- **FR-034**: System MUST create OTel spans for each monitoring check execution with attributes: contract name, check type, result (pass/fail), duration. *(REQ-268)*
- **FR-035**: System MUST propagate W3C trace context through monitoring operations. *(REQ-268)*
- **FR-036**: System MUST export metrics via the OTLP exporter configured in the platform (compatible with Prometheus, Grafana, Datadog backends). *(REQ-261, REQ-268)*

#### SLA Reporting and Analysis

- **FR-037**: System MUST calculate SLA compliance percentages over configurable time windows (daily, weekly, monthly). *(REQ-266)*
- **FR-038**: System MUST track historical trends: violation counts, quality score progression, availability uptime, freshness compliance. *(REQ-262)*
- **FR-039**: System MUST provide both a Python library API and a `floe sla report` CLI command for accessing compliance data. The CLI command MUST support filtering by contract, time window, and output format (table, JSON). *(REQ-266)*

#### Consumer Impact Analysis

- **FR-040**: System MUST identify downstream consumers affected by a contract violation using contract dependency metadata. *(REQ-267)*
- **FR-041**: System MUST include consumer impact information in alert payloads when available. *(REQ-267)*

#### Incident Management

- **FR-042**: System MUST support incident management integration via the AlertChannelPlugin interface, mapping violation severity to incident priority. *(REQ-265)*
- **FR-043**: System MUST correlate repeated violations to existing open incidents (by contract identifier) to prevent duplicate incident creation. *(REQ-265)*

#### Configuration

- **FR-044**: System MUST load monitoring configuration from the platform manifest (check intervals, alert channels, severity thresholds, rate limits). *(REQ-270)*
- **FR-045**: System MUST support per-contract monitoring overrides (custom intervals, custom alert channels, custom severity rules). *(REQ-270)*
- **FR-046**: System MUST allow custom metric definitions beyond the built-in set, registered via configuration. *(REQ-269)*

#### Root Cause Analysis

- **FR-047**: System MUST provide violation context that aids root cause analysis: recent pipeline runs, upstream status, historical pattern for the same check. *(REQ-264)*

### Key Entities

- **ContractMonitor**: The core monitoring service. Orchestrates scheduled checks across registered contracts. Deployed as K8s Deployment. Manages check scheduling, violation detection, and metric emission. Interacts with PostgreSQL for state persistence.

- **ContractViolationEvent**: A frozen Pydantic model representing a detected violation. Contains: contract_name, contract_version, violation_type (freshness/schema_drift/quality/availability), severity (INFO/WARNING/ERROR/CRITICAL), message, element, expected_value, actual_value, timestamp, affected_consumers. This is the SOLE interface between the monitor and alert channels.

- **AlertChannelPlugin**: Plugin ABC for alert delivery. Extends PluginMetadata (inheriting health_check(), startup(), shutdown()). Each implementation handles one delivery mechanism (Slack, webhook, email, Alertmanager, incident management). Discovered via `floe.alert_channels` entry point. Abstract methods: send_alert(), validate_config().

- **AlertRouter**: Orchestrator that receives ContractViolationEvents and dispatches them to appropriate AlertChannelPlugins based on severity routing rules, deduplication windows, and rate limits.

- **MonitoringConfig**: Configuration model (from platform manifest) specifying check intervals, alert channel configurations, severity routing rules, rate limiting parameters, and per-contract overrides.

- **SLAStatus**: Tracks ongoing SLA compliance for a contract. Contains: contract_name, check_type, current_value, threshold, compliance_percentage, last_check_time, consecutive_failures, violation_count_24h.

- **CheckResult**: Records the outcome of a single monitoring check. Contains: contract_name, check_type, status (pass/fail/error/skipped), duration, timestamp, details, violation (if any).

## Clarifications

- Q: How should the ContractMonitor discover contracts on startup (cold start)? A: Both — PostgreSQL as primary, catalog scan as fallback if DB is empty or unavailable. Catalog fallback uses CatalogPlugin.list_namespaces()/list_tables() to discover tables, then matches against contract definitions in the platform manifest to build the registered contract set.
- Q: How does SchemaDriftCheck access actual table schemas? A: Via CatalogPlugin — connect to catalog, load_table() to get the Iceberg table, then read its schema(). Iceberg types are mapped to contract schema types for comparison. This works across all CatalogPlugin implementations (Polaris, Glue, etc.).
- Q: Over what time window should availability SLA percentage be calculated? A: Rolling 24-hour window.
- Q: At what percentage of SLA consumption should the INFO-severity alert trigger? A: 80% of SLA consumed (WARNING at 90%, ERROR on breach, CRITICAL on >3 in 24h).
- Q: What should the default data retention policy be for monitoring history? A: 90 days for raw data; daily/weekly aggregates retained indefinitely.
- Q: Should SLA compliance reporting be a library API, CLI command, or both? A: Both — Python library API and `floe sla report` CLI command.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four monitoring check types (freshness, schema drift, quality, availability) execute at their configured intervals with less than 10% schedule drift under normal load.
- **SC-002**: Contract violations are detected within one check interval of occurrence (e.g., freshness violation detected within 15 minutes of SLA breach).
- **SC-003**: Alert delivery latency from violation detection to channel dispatch is less than 5 seconds for all configured channels.
- **SC-004**: Alert deduplication reduces repeated alerts by at least 80% compared to raw violation count during sustained violation periods.
- **SC-005**: SLA compliance reports accurately reflect monitoring data with calculation error less than 0.1%.
- **SC-006**: System handles monitoring of 100+ contracts concurrently without check schedule degradation.
- **SC-007**: Monitoring metrics are queryable in the configured observability backend within 60 seconds of emission.
- **SC-008**: All violation events contain valid OpenLineage `contractViolation` facet data and are queryable in lineage tools.
- **SC-009**: ContractMonitor maintains 99.9% uptime with automated recovery from failures.
- **SC-010**: Alert channels are independently deployable and configurable without modifying the core monitor.
