# Data Model: K8s-Native Testing Infrastructure

**Feature**: 001-testing-infra
**Date**: 2026-01-09
**Status**: Complete

## Overview

This document defines the data models, entities, and relationships for the testing infrastructure. Unlike feature epics that define API contracts, this infrastructure epic defines internal Python classes and configuration schemas.

---

## Core Entities

### 1. IntegrationTestBase

Base class for all integration tests that require K8s services.

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar
from pydantic import BaseModel, Field

class ServiceRequirement(BaseModel):
    """Service dependency for integration tests."""
    name: str = Field(..., description="Service name (e.g., 'postgres')")
    port: int = Field(..., ge=1, le=65535, description="Service port")
    namespace: str = Field(default="floe-test", description="K8s namespace")

class IntegrationTestBase(ABC):
    """Base class for K8s-native integration tests.

    Provides:
    - Service availability checks
    - Unique namespace generation
    - Automatic resource cleanup

    Usage:
        class TestPolarisCatalog(IntegrationTestBase):
            required_services: ClassVar[list[ServiceRequirement]] = [
                ServiceRequirement(name="polaris", port=8181),
                ServiceRequirement(name="minio", port=9000),
            ]
    """

    # Subclasses MUST declare required services
    required_services: ClassVar[list[ServiceRequirement]] = []

    # Generated per-test instance
    _namespace: str | None = None

    @classmethod
    def generate_unique_namespace(cls, prefix: str = "test") -> str:
        """Generate unique namespace for test isolation.

        Args:
            prefix: Namespace prefix (default: "test")

        Returns:
            Unique namespace string: "{prefix}_{uuid[:8]}"
        """
        ...

    def check_infrastructure(self, service: str, port: int) -> None:
        """Verify service is accessible. FAILS if not available.

        Args:
            service: Service name
            port: Service port

        Raises:
            pytest.fail: If service is not available
        """
        ...

    def setup_method(self) -> None:
        """Verify all required services before each test."""
        ...

    def teardown_method(self) -> None:
        """Clean up test resources after each test."""
        ...
```

### 2. PluginTestBase

Base class for testing plugin compliance with ABCs.

```python
class PluginTestBase(IntegrationTestBase):
    """Base class for plugin compliance testing.

    Verifies:
    - Plugin implements required ABC methods
    - Plugin registers via entry point
    - PluginMetadata is correctly declared

    Usage:
        class TestDuckDBPlugin(PluginTestBase):
            plugin_type = "compute"
            plugin_name = "duckdb"
    """

    plugin_type: ClassVar[str]  # e.g., "compute", "orchestrator"
    plugin_name: ClassVar[str]  # e.g., "duckdb", "dagster"

    def test_entry_point_discovery(self) -> None:
        """Verify plugin is discoverable via entry points."""
        ...

    def test_plugin_metadata(self) -> None:
        """Verify PluginMetadata is correctly declared."""
        ...

    def test_abc_compliance(self) -> None:
        """Verify plugin implements all required ABC methods."""
        ...
```

### 3. AdapterTestBase

Base class for testing adapters between components.

```python
class AdapterTestBase(IntegrationTestBase):
    """Base class for adapter testing.

    Tests integration between two components via their adapter.

    Usage:
        class TestDbtDuckDBAdapter(AdapterTestBase):
            source_component = "dbt"
            target_component = "duckdb"
    """

    source_component: ClassVar[str]
    target_component: ClassVar[str]

    def test_adapter_initialization(self) -> None:
        """Verify adapter can be initialized with valid config."""
        ...

    def test_data_flow(self) -> None:
        """Verify data flows correctly through adapter."""
        ...
```

---

## Service Fixtures

### 4. ServiceFixture Protocol

Protocol defining the interface for service fixtures.

```python
from typing import Protocol, Generator, Any

class ServiceFixture(Protocol):
    """Protocol for service fixtures.

    All service fixtures must:
    - Verify service availability
    - Provide connection/client
    - Clean up resources on teardown
    """

    service_name: str
    service_port: int

    def __call__(self) -> Generator[Any, None, None]:
        """Yield service connection, clean up on exit."""
        ...
```

### 5. PostgresFixture

```python
class PostgresConfig(BaseModel):
    """PostgreSQL fixture configuration."""
    host: str = Field(default="postgres.floe-test.svc.cluster.local")
    port: int = Field(default=5432)
    database: str = Field(default="test")
    user: str = Field(default="test")
    password: SecretStr

@pytest.fixture
def postgres_connection(postgres_config: PostgresConfig) -> Generator[Connection, None, None]:
    """PostgreSQL connection fixture.

    Yields:
        psycopg2.Connection to test database

    Cleanup:
        Closes connection, drops test database
    """
    ...
```

### 6. MinIOFixture

```python
class MinIOConfig(BaseModel):
    """MinIO S3 fixture configuration."""
    endpoint: str = Field(default="http://minio.floe-test.svc.cluster.local:9000")
    access_key: str = Field(default="minioadmin")
    secret_key: SecretStr
    secure: bool = Field(default=False)

@pytest.fixture
def minio_client(minio_config: MinIOConfig) -> Generator[Minio, None, None]:
    """MinIO S3 client fixture.

    Yields:
        minio.Minio client

    Cleanup:
        Deletes test buckets
    """
    ...
```

### 7. PolarisFixture

```python
class PolarisConfig(BaseModel):
    """Polaris catalog fixture configuration."""
    uri: str = Field(default="http://polaris.floe-test.svc.cluster.local:8181/api/catalog")
    warehouse: str = Field(default="test_warehouse")

@pytest.fixture
def polaris_catalog(polaris_config: PolarisConfig) -> Generator[RestCatalog, None, None]:
    """Polaris REST catalog fixture.

    Yields:
        pyiceberg.catalog.rest.RestCatalog

    Cleanup:
        Drops test namespace
    """
    ...
```

### 8. DuckDBFixture

```python
class DuckDBConfig(BaseModel):
    """DuckDB fixture configuration."""
    database: str = Field(default=":memory:")
    read_only: bool = Field(default=False)

@pytest.fixture
def duckdb_connection(duckdb_config: DuckDBConfig) -> Generator[DuckDBPyConnection, None, None]:
    """DuckDB connection fixture.

    Yields:
        duckdb.DuckDBPyConnection

    Cleanup:
        Closes connection
    """
    ...
```

### 9. DagsterFixture

```python
class DagsterConfig(BaseModel):
    """Dagster fixture configuration."""
    host: str = Field(default="dagster-webserver.floe-test.svc.cluster.local")
    port: int = Field(default=3000)

@pytest.fixture
def dagster_client(dagster_config: DagsterConfig) -> Generator[DagsterGraphQLClient, None, None]:
    """Dagster GraphQL client fixture.

    Yields:
        dagster_graphql.DagsterGraphQLClient
    """
    ...
```

---

## Polling Utilities

### 10. PollingConfig

```python
class PollingConfig(BaseModel):
    """Configuration for polling utilities."""
    timeout: float = Field(default=30.0, ge=1.0, description="Max wait time in seconds")
    interval: float = Field(default=0.5, ge=0.1, description="Poll interval in seconds")
    description: str = Field(default="condition", description="Description for error messages")

def wait_for_condition(
    condition: Callable[[], bool],
    config: PollingConfig | None = None,
) -> bool:
    """Wait for condition to become true.

    Args:
        condition: Callable returning True when ready
        config: Polling configuration

    Returns:
        True if condition met within timeout

    Raises:
        TimeoutError: If condition not met within timeout
    """
    ...

def wait_for_service(
    service: str,
    port: int,
    namespace: str = "floe-test",
    config: PollingConfig | None = None,
) -> None:
    """Wait for K8s service to be accessible.

    Args:
        service: Service name
        port: Service port
        namespace: K8s namespace
        config: Polling configuration

    Raises:
        TimeoutError: If service not accessible within timeout
    """
    ...
```

---

## Traceability

### 11. RequirementMarker

```python
class RequirementCoverage(BaseModel):
    """Requirement coverage tracking."""
    requirement_id: str = Field(..., pattern=r"^\d{3}-FR-\d{3}[a-z]?$")
    test_ids: list[str] = Field(default_factory=list)

class TraceabilityReport(BaseModel):
    """Full traceability report."""
    spec_id: str
    total_requirements: int
    covered_requirements: int
    coverage_percentage: float
    uncovered: list[str]
    coverage_map: dict[str, list[str]]  # requirement_id -> [test_ids]
```

---

## State Transitions

### Test Lifecycle

```
                    ┌─────────────┐
                    │   PENDING   │
                    └──────┬──────┘
                           │
                    setup_method()
                           │
                    ┌──────▼──────┐
                    │   RUNNING   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
        │  PASSED   │ │ FAILED  │ │  ERROR    │
        └─────┬─────┘ └────┬────┘ └─────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    teardown_method()
                           │
                    ┌──────▼──────┐
                    │  CLEANUP    │
                    └─────────────┘
```

### Kind Cluster Lifecycle

```
                    ┌─────────────┐
                    │    NONE     │
                    └──────┬──────┘
                           │
                    make kind-up
                           │
                    ┌──────▼──────┐
                    │  CREATING   │
                    └──────┬──────┘
                           │
                    kubectl apply -f services/
                           │
                    ┌──────▼──────┐
                    │  DEPLOYING  │
                    └──────┬──────┘
                           │
                    kubectl wait --for=condition=ready
                           │
                    ┌──────▼──────┐
                    │    READY    │
                    └──────┬──────┘
                           │
                    make kind-down
                           │
                    ┌──────▼──────┐
                    │  DESTROYED  │
                    └─────────────┘
```

---

## Validation Rules

| Entity | Field | Validation |
|--------|-------|------------|
| ServiceRequirement | port | 1 ≤ port ≤ 65535 |
| ServiceRequirement | namespace | DNS-1123 label format |
| PollingConfig | timeout | ≥ 1.0 seconds |
| PollingConfig | interval | ≥ 0.1 seconds |
| RequirementCoverage | requirement_id | Pattern: `###-FR-###[a-z]?` |
| PostgresConfig | port | Default 5432 |
| MinIOConfig | endpoint | Valid URL format |
| PolarisConfig | uri | Valid URL format |

---

## Relationships

```
┌─────────────────────┐
│ IntegrationTestBase │
└──────────┬──────────┘
           │ extends
     ┌─────┴─────┐
     │           │
┌────▼────┐ ┌────▼────────┐
│PluginTest│ │AdapterTest │
│  Base   │ │   Base     │
└─────────┘ └─────────────┘

┌─────────────────────┐
│  ServiceFixture     │◄──────implements─────┐
│    (Protocol)       │                       │
└─────────────────────┘                       │
                                              │
    ┌────────────────────────────────────────┬┴┬──────────────────────┐
    │                │                │       │                        │
┌───▼───┐      ┌─────▼─────┐    ┌─────▼─────┐ │  ┌─────────┐    ┌─────▼─────┐
│Postgres│     │   MinIO   │    │  Polaris  │ │  │ DuckDB  │    │  Dagster  │
│Fixture │     │  Fixture  │    │  Fixture  │ │  │ Fixture │    │  Fixture  │
└────────┘     └───────────┘    └───────────┘ │  └─────────┘    └───────────┘
                                              │
┌─────────────────────┐                       │
│   PollingConfig     │◄──────used by────────┘
└─────────────────────┘
```
