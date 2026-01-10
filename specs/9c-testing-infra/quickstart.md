# Quickstart: K8s-Native Testing Infrastructure

**Feature**: 9c-testing-infra
**Date**: 2026-01-09

## Prerequisites

- Docker installed and running
- `kind` CLI installed: `brew install kind`
- `kubectl` CLI installed: `brew install kubectl`
- Python 3.10+ with `uv` installed

## Quick Start (3 Commands)

```bash
# 1. Create Kind cluster with test services
make kind-up

# 2. Run all tests (unit + integration)
make test

# 3. Tear down cluster when done
make kind-down
```

## Running Specific Test Types

```bash
# Unit tests only (fast, no K8s required)
make test-unit

# Integration tests only (requires Kind cluster)
make test-integration

# E2E tests (full stack validation)
make test-e2e

# Full CI check (lint + typecheck + tests)
make check
```

## Writing Integration Tests

### Basic Integration Test

```python
from testing.base_classes.integration_test_base import IntegrationTestBase
import pytest


class TestMyCatalog(IntegrationTestBase):
    """Integration tests for catalog operations."""

    required_services = [("polaris", 8181), ("minio", 9000)]

    @pytest.mark.requirement("9c-FR-012")
    def test_create_catalog(self) -> None:
        """Test catalog creation with real Polaris."""
        namespace = self.generate_unique_namespace("test_catalog")

        # Your test code here
        catalog = create_catalog(name=f"{namespace}_catalog")

        assert catalog is not None
        assert catalog.name == f"{namespace}_catalog"
```

### Using Service Fixtures

```python
import pytest
from testing.fixtures.postgres import postgres_connection
from testing.fixtures.minio import minio_client


@pytest.mark.requirement("9c-FR-010")
def test_with_postgres(postgres_connection) -> None:
    """Test using PostgreSQL fixture."""
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    assert result[0] == 1


@pytest.mark.requirement("9c-FR-013")
def test_with_minio(minio_client) -> None:
    """Test using MinIO S3 fixture."""
    bucket_name = "test-bucket"
    minio_client.make_bucket(bucket_name)
    assert minio_client.bucket_exists(bucket_name)
```

### Using Polling Utilities

```python
from testing.fixtures.polling import wait_for_condition, wait_for_service


def test_async_operation() -> None:
    """Test with polling instead of sleep."""
    # Start async operation
    job_id = start_background_job()

    # Poll for completion (NOT time.sleep!)
    assert wait_for_condition(
        lambda: job_status(job_id) == "complete",
        timeout=30.0,
        description="job completion"
    )
```

## Requirement Traceability

Every integration test MUST have a requirement marker:

```python
@pytest.mark.requirement("9c-FR-001")  # Single requirement
def test_something() -> None:
    ...

@pytest.mark.requirement("9c-FR-001")
@pytest.mark.requirement("9c-FR-009")  # Multiple requirements
def test_covers_multiple() -> None:
    ...
```

### Verify Traceability

```bash
# Check all tests have markers
python -m testing.traceability --all --threshold 100

# Generate traceability report
python -m testing.traceability --report
```

## Local Development Workflow

```bash
# 1. Start cluster (once)
make kind-up

# 2. Develop and run tests iteratively
make test-unit                    # Fast feedback
pytest tests/integration/test_my_feature.py -v  # Specific test

# 3. Full validation before PR
make check

# 4. Clean up
make kind-down
```

## CI Integration

The CI workflow automatically:

1. Runs security scans (Bandit, pip-audit)
2. Creates Kind cluster
3. Deploys test services
4. Runs integration tests as K8s Jobs
5. Collects results and artifacts
6. Fails if coverage < 100%

## Troubleshooting

### Cluster Won't Start

```bash
# Check Docker is running
docker info

# Check Kind logs
kind get clusters
kind export logs floe-test

# Delete and recreate
make kind-down && make kind-up
```

### Service Not Ready

```bash
# Check pod status
kubectl get pods -n floe-test

# Check service logs
kubectl logs -n floe-test deployment/postgres --tail=50

# Check events
kubectl get events -n floe-test --sort-by='.lastTimestamp'
```

### Test Timeouts

```python
# Increase timeout for slow services
from testing.fixtures.polling import PollingConfig

config = PollingConfig(timeout=60.0, interval=1.0)
wait_for_service("polaris", 8181, config=config)
```

## Key Files

| File | Purpose |
|------|---------|
| `testing/base_classes/integration_test_base.py` | Base class for integration tests |
| `testing/fixtures/polling.py` | Polling utilities (no sleep!) |
| `testing/fixtures/*.py` | Service-specific fixtures |
| `testing/k8s/kind-config.yaml` | Kind cluster configuration |
| `testing/k8s/services/*.yaml` | Test service manifests |
| `testing/traceability/checker.py` | Requirement coverage checker |
| `Makefile` | Test and cluster commands |
