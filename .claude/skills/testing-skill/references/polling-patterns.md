# Polling Patterns Reference

## Overview

**Replace ALL `time.sleep()` calls with polling utilities.**

**Location**: `testing/fixtures/services.py`

**Why**: Polling is faster, more reliable, and deterministic compared to hardcoded sleeps.

---

## wait_for_condition

### Purpose

**Wait for a boolean condition to become True.**

### Signature

```python
def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = DEFAULT_POLL_TIMEOUT,  # 30.0 seconds
    poll_interval: float = DEFAULT_POLL_INTERVAL,  # 0.5 seconds
    description: str = "condition",
) -> bool:
    """Wait for a condition to become True using polling.

    Args:
        condition: Callable that returns bool
        timeout: Maximum wait time in seconds
        poll_interval: Time between checks in seconds
        description: Human-readable description for logging

    Returns:
        True if condition met, False if timeout

    Example:
        >>> wait_for_condition(
        ...     lambda: service.is_ready(),
        ...     timeout=10,
        ...     description="service to become ready"
        ... )
        True
    """
```

### Basic Usage

```python
from testing.fixtures.services import wait_for_condition

def test_service_ready():
    """Test service becomes ready after startup."""
    start_service()

    # ❌ FORBIDDEN
    # import time
    # time.sleep(5)

    # ✅ CORRECT
    result = wait_for_condition(
        condition=lambda: service.is_ready(),
        timeout=10.0,
        poll_interval=0.5,
        description="service to become ready"
    )

    assert result, "Service did not become ready within 10s"
```

### Advanced Usage

```python
# Wait for multiple conditions
def test_pipeline_complete():
    trigger_pipeline()

    # Wait for all steps to complete
    result = wait_for_condition(
        condition=lambda: all([
            step1.is_complete(),
            step2.is_complete(),
            step3.is_complete()
        ]),
        timeout=60.0,
        description="all pipeline steps to complete"
    )

    assert result, "Pipeline did not complete within 60s"

# Wait for count
def test_data_loaded():
    load_data()

    result = wait_for_condition(
        condition=lambda: db.table.count_documents({}) >= 1000,
        timeout=30.0,
        description="1000 rows to be loaded"
    )

    assert result
    assert db.table.count_documents({}) >= 1000

# Wait for file existence
def test_artifact_generated():
    compile_project()

    result = wait_for_condition(
        condition=lambda: Path("target/compiled.json").exists(),
        timeout=5.0,
        description="compiled artifact to be generated"
    )

    assert result
    assert Path("target/compiled.json").exists()
```

### Exception Handling

```python
def test_with_exceptions():
    """Condition may raise exceptions during polling."""
    start_service()

    # Exceptions during polling are caught and ignored
    result = wait_for_condition(
        condition=lambda: service.get_status() == "ready",  # May raise if not ready
        timeout=10.0,
        poll_interval=1.0,
        description="service status to be ready"
    )

    assert result
```

**Note**: Exceptions during polling are caught and retried until timeout. This is intentional - service might not be ready yet.

---

## poll_until

### Purpose

**Two-phase polling: fetch data repeatedly, then check a condition on that data.**

### Signature

```python
def poll_until(
    fetch_func: Callable[[], T],
    check_func: Callable[[T], bool],
    timeout: float = DEFAULT_POLL_TIMEOUT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    description: str = "expected result",
) -> T | None:
    """Poll until a check function returns True on fetched data.

    Args:
        fetch_func: Function to fetch data (called repeatedly)
        check_func: Function to check if data matches condition
        timeout: Maximum wait time in seconds
        poll_interval: Time between checks in seconds
        description: Human-readable description for logging

    Returns:
        Fetched data if condition met, None if timeout

    Example:
        >>> traces = poll_until(
        ...     fetch_func=lambda: jaeger.get_traces(service="test"),
        ...     check_func=lambda traces: len(traces) > 0,
        ...     timeout=10,
        ...     description="traces to be exported"
        ... )
    """
```

### Basic Usage

```python
from testing.fixtures.services import poll_until

def test_lineage_emission():
    """Test lineage events are emitted to Marquez."""
    trigger_pipeline()

    # ❌ FORBIDDEN
    # import time
    # time.sleep(10)
    # events = marquez.get_events()

    # ✅ CORRECT
    events = poll_until(
        fetch_func=lambda: marquez.get_events(namespace="default"),
        check_func=lambda events: len(events) > 0,
        timeout=15.0,
        poll_interval=1.0,
        description="lineage events to be emitted"
    )

    assert events is not None, "No lineage events within 15s"
    assert len(events) > 0
```

### Advanced Usage

```python
# Wait for specific data
def test_trace_with_attributes():
    """Test trace has specific attributes."""
    execute_operation()

    trace = poll_until(
        fetch_func=lambda: jaeger.get_traces(service="test"),
        check_func=lambda traces: any(
            t.operation_name == "transform" and
            t.attributes.get("model") == "customers"
            for t in traces
        ),
        timeout=10.0,
        description="trace with transform operation"
    )

    assert trace is not None
    transform_span = next(
        t for t in trace if t.operation_name == "transform"
    )
    assert transform_span.attributes["model"] == "customers"

# Wait for data with specific count
def test_expected_row_count():
    """Test table has expected row count."""
    load_data()

    result = poll_until(
        fetch_func=lambda: db.table.find().to_list(),
        check_func=lambda rows: len(rows) == 1000,
        timeout=30.0,
        description="1000 rows to be loaded"
    )

    assert result is not None
    assert len(result) == 1000

# Wait for API response
def test_api_returns_data():
    """Test API endpoint returns data."""
    trigger_job()

    response_data = poll_until(
        fetch_func=lambda: requests.get("http://api/status").json(),
        check_func=lambda data: data.get("status") == "complete",
        timeout=20.0,
        description="job to complete"
    )

    assert response_data is not None
    assert response_data["status"] == "complete"
```

### Exception Handling

```python
def test_with_exceptions():
    """Fetch function may raise exceptions during polling."""
    start_service()

    # Exceptions during fetch are caught and retried
    data = poll_until(
        fetch_func=lambda: service.fetch_data(),  # May raise if not ready
        check_func=lambda data: data is not None,
        timeout=10.0,
        poll_interval=1.0,
        description="data to be available"
    )

    assert data is not None
```

**Note**: Exceptions during fetch/check are caught and retried. This is intentional - service might not be ready yet.

---

## Comparison: wait_for_condition vs poll_until

| Aspect | wait_for_condition | poll_until |
|--------|-------------------|------------|
| **Use When** | Checking a simple boolean condition | Need to fetch data and check it |
| **Returns** | `bool` (True/False) | Fetched data or None |
| **Example** | "Is service ready?" | "Get me the trace with X attribute" |
| **Pattern** | Single callable returns bool | Two callables: fetch + check |

### When to Use Each

```python
# Use wait_for_condition when:
# - Simple boolean check
# - Don't need the data, just confirmation
wait_for_condition(
    lambda: service.is_ready(),  # Just checks, doesn't fetch
    timeout=10
)

# Use poll_until when:
# - Need to fetch data repeatedly
# - Want to use the data after polling
# - Complex condition on fetched data
data = poll_until(
    fetch_func=lambda: fetch_data(),  # Fetches data
    check_func=lambda d: len(d) > 0,  # Checks data
    timeout=10
)
# Can use 'data' variable here
```

---

## Common Patterns

### Wait for Database Record

```python
def test_record_created():
    create_record(id=123)

    record = poll_until(
        fetch_func=lambda: db.table.find_one({"id": 123}),
        check_func=lambda rec: rec is not None,
        timeout=5.0,
        description="record to be created"
    )

    assert record is not None
    assert record["id"] == 123
```

### Wait for File with Content

```python
def test_file_generated():
    generate_report()

    content = poll_until(
        fetch_func=lambda: Path("report.txt").read_text() if Path("report.txt").exists() else None,
        check_func=lambda content: content is not None and len(content) > 100,
        timeout=10.0,
        description="report to be generated with content"
    )

    assert content is not None
    assert "Total: " in content
```

### Wait for Queue to Empty

```python
def test_queue_processed():
    submit_jobs(count=10)

    result = wait_for_condition(
        condition=lambda: queue.size() == 0,
        timeout=30.0,
        description="queue to be processed"
    )

    assert result
    assert queue.size() == 0
```

### Wait for HTTP Endpoint

```python
def test_api_healthy():
    start_api_server()

    result = wait_for_condition(
        condition=lambda: requests.get("http://localhost:8000/health").status_code == 200,
        timeout=15.0,
        poll_interval=1.0,
        description="API to become healthy"
    )

    assert result
```

---

## Timeout Selection Guidelines

| Operation | Suggested Timeout | Reasoning |
|-----------|------------------|-----------|
| **Service startup** | 10-30s | Depends on service complexity |
| **Database query** | 5-10s | Should be fast |
| **File I/O** | 5-10s | Usually fast |
| **HTTP request** | 5-15s | Network latency |
| **Pipeline execution** | 30-120s | Depends on pipeline complexity |
| **Data loading** | 30-60s | Depends on data size |
| **Container startup** | 20-60s | Pulling images takes time |

**Principle**: Set timeout to 2-3x expected time. Better to wait a bit longer than have flaky failures.

---

## Poll Interval Selection

| Condition Check | Suggested Interval | Reasoning |
|----------------|-------------------|-----------|
| **Expensive operation** | 2-5s | Avoid overloading system |
| **Database query** | 0.5-1s | Balance responsiveness vs load |
| **File existence** | 0.1-0.5s | Cheap check, can poll fast |
| **HTTP endpoint** | 1-2s | Avoid overwhelming server |
| **In-memory check** | 0.1-0.5s | Very cheap, can poll fast |

**Principle**: Cheaper checks → faster polling. Expensive checks → slower polling.

---

## Anti-Patterns to Avoid

### ❌ FORBIDDEN: Polling Without Timeout

```python
# Never do infinite polling
while not service.is_ready():
    time.sleep(1)  # Infinite loop if service never ready
```

**Why**: Test hangs forever if condition never met.

### ❌ FORBIDDEN: Nested time.sleep()

```python
# Don't mix sleep with polling
time.sleep(5)  # Wait arbitrary time first
wait_for_condition(lambda: service.is_ready(), timeout=5)
```

**Why**: Wastes time with unnecessary sleep before polling.

### ❌ FORBIDDEN: Checking After Sleep

```python
# Don't sleep then check once
time.sleep(10)
assert service.is_ready()  # Flaky if takes 11 seconds
```

**Why**: If operation takes longer than sleep, test fails. Polling handles variable timing.

---

## Best Practices

1. **Always use polling** - Never `time.sleep()` in tests
2. **Set reasonable timeouts** - 2-3x expected duration
3. **Use descriptive messages** - Helps debugging when timeout occurs
4. **Test timeout path** - Verify timeout works correctly
5. **Log poll attempts** - Utilities already log for debugging

---

## Source Code Reference

**Location**: `testing/fixtures/services.py`

```python
# View full implementation
cat testing/fixtures/services.py

# Search for usage examples
rg "wait_for_condition|poll_until" --type py packages/*/tests/
```

---

## External Resources

- **pytest-timeout**: https://pypi.org/project/pytest-timeout/ (test-level timeouts)
- **tenacity**: https://tenacity.readthedocs.io/ (advanced retry logic)
- **TESTING.md** - "Polling Utilities (Replaces time.sleep)" section
