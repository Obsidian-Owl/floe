# Acceptance Criteria Standards

**Purpose**: Define quantifiable patterns for acceptance criteria to ensure testability and clarity.

**Principle**: Every acceptance criterion MUST be measurable, testable, and unambiguous.

---

## Quantification Patterns

### Error Messages

**Vague**: "Provide clear error messages"

**Quantified**: Error messages MUST include:
- `error_code`: Unique identifier (e.g., `FLOE-E001`)
- `message`: Human-readable description
- `field_name`: Field that caused the error (if applicable)
- `expected`: Expected format or value
- `actual`: Actual value received
- `suggestion`: Actionable fix (when determinable)

**Example**:
```json
{
  "error_code": "FLOE-E042",
  "message": "Invalid model name format",
  "field_name": "model_name",
  "expected": "^(bronze|silver|gold)_[a-z_]+$",
  "actual": "stg_payments",
  "suggestion": "Rename to bronze_payments, silver_payments, or gold_payments"
}
```

---

### Timeouts

**Vague**: "Configurable timeouts"

**Quantified**: Timeout configuration MUST support:

| Timeout Type | Default | Min | Max | Config Key |
|--------------|---------|-----|-----|------------|
| Connection | 30s | 5s | 120s | `timeouts.connection` |
| Read | 60s | 10s | 300s | `timeouts.read` |
| Write | 60s | 10s | 300s | `timeouts.write` |
| Total | 120s | 30s | 600s | `timeouts.total` |
| Idle | 300s | 60s | 3600s | `timeouts.idle` |

**Test Coverage**:
- [ ] Timeout triggers after configured duration
- [ ] Timeout < min value → validation error
- [ ] Timeout > max value → validation error

---

### Graceful Degradation

**Vague**: "Graceful degradation when backend unavailable"

**Quantified**: Degradation behavior MUST specify:

| Condition | Buffer Size | Drop Policy | Log Level | Recovery |
|-----------|-------------|-------------|-----------|----------|
| Backend slow (P99 > 500ms) | 1000 events | oldest-first | WARN | auto-retry |
| Backend unavailable | 10000 events | oldest-first | ERROR | exponential backoff |
| Buffer full | N/A | drop incoming | ERROR | continue processing |

**Configuration**:
```yaml
degradation:
  buffer_size: 10000
  drop_policy: oldest_first  # oldest_first | newest_first | random
  log_level: ERROR
  retry:
    initial_delay: 1s
    max_delay: 60s
    backoff_multiplier: 2.0
    max_retries: 10
```

---

### Performance Requirements

**Vague**: "Fast response times"

**Quantified**: Performance targets MUST specify:

| Metric | Target | Warning | Critical | Measurement |
|--------|--------|---------|----------|-------------|
| P50 latency | < 100ms | > 200ms | > 500ms | Rolling 5min |
| P99 latency | < 500ms | > 1s | > 2s | Rolling 5min |
| Throughput | > 1000 req/s | < 500 req/s | < 100 req/s | Peak load |
| Error rate | < 0.1% | > 1% | > 5% | Rolling 1min |

**Resource Bounds**:
- Memory: Peak usage < 2GB per pod
- CPU: Sustained usage < 2 cores per pod
- Network: < 100MB/s egress per pod

---

### Test Coverage

**Vague**: "Adequate test coverage"

**Quantified**: Test coverage MUST meet:

| Test Type | Minimum | Target | Measurement |
|-----------|---------|--------|-------------|
| Unit tests | 80% | 90% | Line coverage |
| Integration tests | 70% | 80% | Branch coverage |
| Contract tests | 100% | 100% | All public interfaces |
| E2E tests | 50% | 70% | Critical paths |

**Enforcement**:
- CI fails if unit test coverage < 80%
- PR blocked if contract tests not 100%

---

### Validation Rules

**Vague**: "Validate input"

**Quantified**: Validation MUST specify for each field:

| Field | Type | Required | Min | Max | Pattern | Example |
|-------|------|----------|-----|-----|---------|---------|
| `name` | string | Yes | 1 | 100 | `^[a-z][a-z0-9_]*$` | `customer_360` |
| `version` | string | Yes | - | - | `^\d+\.\d+\.\d+$` | `1.2.3` |
| `port` | integer | No | 1 | 65535 | - | `8080` |
| `timeout_ms` | integer | No | 100 | 600000 | - | `30000` |

---

### Retry Behavior

**Vague**: "Retry on failure"

**Quantified**: Retry configuration MUST include:

```yaml
retry:
  max_attempts: 3           # Total attempts (1 initial + 2 retries)
  initial_delay_ms: 1000    # First retry delay
  max_delay_ms: 30000       # Maximum delay cap
  backoff_multiplier: 2.0   # Exponential backoff
  retryable_errors:         # Which errors trigger retry
    - connection_timeout
    - service_unavailable
    - rate_limited
  non_retryable_errors:     # Fail immediately
    - invalid_credentials
    - not_found
    - validation_error
```

---

### Circuit Breaker

**Vague**: "Circuit breaker pattern"

**Quantified**: Circuit breaker MUST specify:

| State | Trigger | Behavior | Duration |
|-------|---------|----------|----------|
| Closed | Normal operation | All requests pass | - |
| Open | 5 failures in 60s | All requests fail fast | 30s |
| Half-Open | After cooldown | 1 probe request | Until success/failure |

**Configuration**:
```yaml
circuit_breaker:
  failure_threshold: 5        # Failures to open
  failure_window_ms: 60000    # Window for counting failures
  cooldown_ms: 30000          # Time before half-open
  success_threshold: 2        # Successes to close from half-open
```

---

### Rate Limiting

**Vague**: "Rate limiting support"

**Quantified**: Rate limiting MUST specify:

| Limit Type | Default | Burst | Window | Config Key |
|------------|---------|-------|--------|------------|
| Requests | 1000/min | 100 | 1 minute | `rate_limit.requests` |
| Connections | 100 | 20 | - | `rate_limit.connections` |
| Bandwidth | 10MB/s | 50MB | 1 second | `rate_limit.bandwidth` |

**Response on limit exceeded**:
- HTTP 429 (Too Many Requests)
- `Retry-After` header with seconds until reset
- Log: `rate_limit_exceeded` with client ID

---

### Log Format

**Vague**: "Structured logging"

**Quantified**: Log entries MUST include:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | ISO8601 | Yes | Event time (UTC) |
| `level` | enum | Yes | DEBUG, INFO, WARN, ERROR |
| `message` | string | Yes | Human-readable message |
| `service` | string | Yes | Service name |
| `trace_id` | string | If available | Distributed trace ID |
| `span_id` | string | If available | Current span ID |
| `error` | object | On error | Error details |
| `duration_ms` | number | On completion | Operation duration |

**Example**:
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "ERROR",
  "message": "Database connection failed",
  "service": "floe-dagster",
  "trace_id": "abc123",
  "span_id": "def456",
  "error": {
    "type": "ConnectionError",
    "message": "Connection refused",
    "stack": "..."
  },
  "duration_ms": 30042
}
```

---

### Health Check Response

**Vague**: "Health endpoint"

**Quantified**: Health check MUST return:

**Healthy (HTTP 200)**:
```json
{
  "status": "healthy",
  "version": "1.2.3",
  "uptime_seconds": 3600,
  "checks": {
    "database": {"status": "healthy", "latency_ms": 5},
    "cache": {"status": "healthy", "latency_ms": 2},
    "storage": {"status": "healthy", "latency_ms": 15}
  }
}
```

**Unhealthy (HTTP 503)**:
```json
{
  "status": "unhealthy",
  "version": "1.2.3",
  "uptime_seconds": 3600,
  "checks": {
    "database": {"status": "unhealthy", "error": "Connection refused"},
    "cache": {"status": "healthy", "latency_ms": 2},
    "storage": {"status": "healthy", "latency_ms": 15}
  }
}
```

---

## Applying These Standards

When writing acceptance criteria:

1. **Identify the pattern** from this document
2. **Copy the quantified template**
3. **Adjust values** for your specific requirement
4. **Add test coverage** that verifies each quantified value

### Checklist for Reviewers

- [ ] All numbers have explicit values (not "reasonable", "appropriate", "fast")
- [ ] All errors have specified format and fields
- [ ] All timeouts have min/max/default
- [ ] All degradation has buffer/drop/recovery behavior
- [ ] All validation has type/min/max/pattern
- [ ] All retries have max/delay/backoff
- [ ] Test coverage specifies how to verify each criterion

---

## References

- TESTING.md - Test organization and coverage requirements
- ADR-0017 - Kubernetes-native architecture
- ADR-0035 - Observability plugin interface
