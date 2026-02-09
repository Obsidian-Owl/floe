# Data Model: Epic 3D Contract Monitoring

**Date**: 2026-02-08
**Branch**: `3d-contract-monitoring`

## Entity Relationship Diagram

```
ContractMonitor
    │ manages
    ├── RegisteredContract (1:N)
    │   │ has
    │   ├── MonitoringSchedule (1:1)
    │   └── SLAStatus (1:N per check type)
    │
    ├── CheckResult (generates 1:N)
    │   └── ContractViolationEvent (0:1 per failed check)
    │
    ├── AlertRouter (delegates to)
    │   └── AlertChannelPlugin (1:N, discovered via entry points)
    │
    └── MonitoringConfig (configured by)

DataContract (from Epic 3C, READ-ONLY)
    │ referenced by
    └── RegisteredContract
```

## Core Pydantic Models

### ContractViolationEvent (SOLE Interface: Monitor -> Alerts)

```python
class ViolationType(str, Enum):
    FRESHNESS = "freshness"
    SCHEMA_DRIFT = "schema_drift"
    QUALITY = "quality"
    AVAILABILITY = "availability"
    DEPRECATION = "deprecation"

class ViolationSeverity(str, Enum):
    INFO = "info"         # 80% of SLA consumed
    WARNING = "warning"   # 90% of SLA consumed
    ERROR = "error"       # SLA breached
    CRITICAL = "critical" # >3 violations same type/contract in 24h

class ContractViolationEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_name: str
    contract_version: str
    violation_type: ViolationType
    severity: ViolationSeverity
    message: str
    element: str | None = None
    expected_value: str | None = None
    actual_value: str | None = None
    timestamp: datetime
    affected_consumers: list[str] = []
    check_duration_seconds: float
    metadata: dict[str, str] = {}
```

### MonitoringConfig (from Platform Manifest)

```python
class CheckIntervalConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    freshness_minutes: int = 15
    schema_drift_minutes: int = 60
    quality_minutes: int = 360
    availability_minutes: int = 5

class SeverityThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    info_pct: float = 80.0       # % of SLA consumed
    warning_pct: float = 90.0    # % of SLA consumed
    critical_count: int = 3       # violations in 24h window
    critical_window_hours: int = 24

class AlertChannelRoutingRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    channel_name: str
    min_severity: ViolationSeverity
    contract_filter: str | None = None  # glob pattern

class AlertConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    routing_rules: list[AlertChannelRoutingRule] = []
    dedup_window_minutes: int = 30
    rate_limit_per_contract: int = 10
    rate_limit_window_minutes: int = 60

class MonitoringConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    mode: str = "scheduled"  # scheduled | continuous | on_demand
    check_intervals: CheckIntervalConfig = CheckIntervalConfig()
    severity_thresholds: SeverityThresholds = SeverityThresholds()
    alerts: AlertConfig = AlertConfig()
    retention_days: int = 90
    clock_skew_tolerance_seconds: int = 60
    check_timeout_seconds: int = 30
```

### RegisteredContract (Runtime State)

```python
class RegisteredContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_name: str
    contract_version: str
    contract: DataContract  # From Epic 3C
    connection_config: dict[str, Any]
    monitoring_overrides: MonitoringConfig | None = None
    registered_at: datetime
    last_check_times: dict[str, datetime] = {}  # check_type -> last_run
    active: bool = True
```

### CheckResult (Persisted to PostgreSQL)

```python
class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"

class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str  # UUID
    contract_name: str
    check_type: ViolationType
    status: CheckStatus
    duration_seconds: float
    timestamp: datetime
    details: dict[str, Any] = {}
    violation: ContractViolationEvent | None = None
```

### SLAStatus (Rolling Compliance Tracking)

```python
class SLAStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_name: str
    check_type: ViolationType
    current_value: float  # current metric value
    threshold: float  # SLA threshold
    compliance_pct: float  # rolling 24h compliance
    last_check_time: datetime | None = None
    consecutive_failures: int = 0
    violation_count_24h: int = 0
    window_start: datetime  # rolling window start
```

## AlertChannelPlugin ABC

```python
class AlertChannelPlugin(PluginMetadata, ABC):
    """Plugin ABC for alert delivery channels.

    Entry point group: floe.alert_channels

    Inherits from PluginMetadata:
    - name, version, floe_api_version (abstract properties — MUST implement)
    - health_check(timeout) -> HealthStatus (default: HEALTHY — override for real checks)
    - startup() / shutdown() lifecycle hooks
    - get_config_schema() -> type[BaseModel] | None
    """

    @abstractmethod
    async def send_alert(
        self,
        event: ContractViolationEvent,
    ) -> bool:
        """Send alert for a contract violation.

        Returns True if delivery succeeded, False otherwise.
        Fire-and-forget: failures are logged, not retried.
        """
        ...

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Validate channel configuration.

        Returns list of validation errors (empty = valid).
        """
        ...
```

## PostgreSQL Schema (Monitoring State)

```sql
-- Check results history (90-day retention)
CREATE TABLE contract_check_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_name VARCHAR(255) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    duration_seconds FLOAT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details JSONB DEFAULT '{}',
    violation JSONB DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_check_results_contract ON contract_check_results(contract_name, checked_at);
CREATE INDEX idx_check_results_type ON contract_check_results(check_type, checked_at);

-- Violation history (90-day retention)
CREATE TABLE contract_violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_name VARCHAR(255) NOT NULL,
    contract_version VARCHAR(50) NOT NULL,
    violation_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    element VARCHAR(255),
    expected_value TEXT,
    actual_value TEXT,
    affected_consumers JSONB DEFAULT '[]',
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_result_id UUID REFERENCES contract_check_results(id)
);
CREATE INDEX idx_violations_contract ON contract_violations(contract_name, detected_at);
CREATE INDEX idx_violations_severity ON contract_violations(severity, detected_at);

-- SLA status tracking (current state, not time-series)
CREATE TABLE contract_sla_status (
    contract_name VARCHAR(255) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    current_value FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    compliance_pct FLOAT NOT NULL,
    last_check_time TIMESTAMPTZ,
    consecutive_failures INT DEFAULT 0,
    violation_count_24h INT DEFAULT 0,
    window_start TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (contract_name, check_type)
);

-- Daily aggregates (retained indefinitely)
CREATE TABLE contract_daily_aggregates (
    contract_name VARCHAR(255) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    total_checks INT NOT NULL DEFAULT 0,
    passed_checks INT NOT NULL DEFAULT 0,
    failed_checks INT NOT NULL DEFAULT 0,
    error_checks INT NOT NULL DEFAULT 0,
    avg_duration_seconds FLOAT,
    min_quality_score FLOAT,
    max_quality_score FLOAT,
    avg_quality_score FLOAT,
    uptime_pct FLOAT,
    violation_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (contract_name, check_type, date)
);

-- Registered contracts (active monitoring set)
CREATE TABLE registered_contracts (
    contract_name VARCHAR(255) PRIMARY KEY,
    contract_version VARCHAR(50) NOT NULL,
    contract_data JSONB NOT NULL,
    connection_config JSONB NOT NULL,
    monitoring_overrides JSONB,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_check_times JSONB DEFAULT '{}',
    active BOOLEAN DEFAULT TRUE
);

-- Alert deduplication tracking
CREATE TABLE alert_dedup_state (
    contract_name VARCHAR(255) NOT NULL,
    violation_type VARCHAR(50) NOT NULL,
    last_alerted_at TIMESTAMPTZ NOT NULL,
    alert_count_window INT DEFAULT 1,
    window_start TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (contract_name, violation_type)
);
```

## OpenLineage contractViolation Facet

```json
{
  "_producer": "floe",
  "_schemaURL": "https://floe.dev/schemas/contract-violation-facet.json",
  "contractName": "string",
  "contractVersion": "string (semver)",
  "violationType": "freshness | schema_drift | quality | availability | deprecation",
  "severity": "info | warning | error | critical",
  "message": "string (human-readable, no PII)",
  "element": "string | null (column/field name)",
  "expectedValue": "string | null",
  "actualValue": "string | null",
  "timestamp": "ISO 8601 datetime"
}
```

## OTel Semantic Conventions

| Attribute | Type | Description |
|-----------|------|-------------|
| `floe.contract.name` | string | Contract being monitored |
| `floe.contract.version` | string | Contract version |
| `floe.check.type` | string | freshness/schema_drift/quality/availability |
| `floe.check.status` | string | pass/fail/error/skipped |
| `floe.check.duration_ms` | int | Check duration in milliseconds |
| `floe.violation.severity` | string | info/warning/error/critical |
| `floe.violation.type` | string | Violation type enum value |

## CloudEvents Envelope (for Webhook Channel)

```json
{
  "specversion": "1.0",
  "type": "floe.contract.violation",
  "source": "floe-contract-monitor",
  "id": "uuid",
  "time": "ISO 8601",
  "datacontenttype": "application/json",
  "data": {
    "contractName": "...",
    "contractVersion": "...",
    "violationType": "...",
    "severity": "...",
    "message": "...",
    "element": "...",
    "expectedValue": "...",
    "actualValue": "..."
  }
}
```
