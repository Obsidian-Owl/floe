# Research: Catalog Plugin

**Feature**: 001-catalog-plugin
**Date**: 2026-01-09
**Status**: Complete

## Executive Summary

This research resolves all technical decisions for implementing the CatalogPlugin ABC and PolarisCatalogPlugin reference implementation. Key findings inform the data model, API contracts, and implementation approach.

---

## Decision 1: PyIceberg Integration Pattern

### Decision
Use PyIceberg's `load_catalog()` function with REST catalog configuration for Polaris integration. The CatalogPlugin ABC wraps PyIceberg's Catalog protocol.

### Rationale
- PyIceberg is the de-facto Python client for Iceberg catalogs
- REST catalog type supports Polaris, AWS Glue, Unity Catalog, and BigLake
- Built-in OAuth2 authentication with automatic token refresh
- Connection pooling via httpx client

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Direct Polaris REST API calls | Duplicates PyIceberg functionality; misses Iceberg protocol nuances |
| Custom Iceberg client | Massive undertaking; PyIceberg is well-maintained |
| Synchronous-only approach | PyIceberg supports sync natively; async can be added later |

### Key Classes and Methods

```python
from pyiceberg.catalog import load_catalog

# Entry point for all catalog operations
config = {
    'type': 'rest',
    'uri': 'https://polaris.example.com/api/catalog',
    'warehouse': 'default_warehouse',
    'credential': '${CLIENT_ID}:${CLIENT_SECRET}',
    'header.X-Iceberg-Access-Delegation': 'vended-credentials'
}
catalog = load_catalog('polaris', **config)

# Namespace operations
catalog.create_namespace("bronze", {"location": "s3://bucket/bronze"})
catalog.list_namespaces()
catalog.drop_namespace("bronze")

# Table operations
catalog.create_table("bronze.events", schema, location=location)
catalog.list_tables("bronze")
catalog.load_table("bronze.events")
catalog.drop_table("bronze.events")
```

---

## Decision 2: OAuth2 Authentication Strategy

### Decision
Use PyIceberg's built-in OAuth2 AuthManager with client credentials flow. Configure automatic token refresh with 60-second margin before expiration.

### Rationale
- Client credentials flow is standard for service-to-service communication
- PyIceberg handles token refresh automatically when `token-refresh-enabled: true`
- Refresh margin prevents race conditions during token expiration
- No refresh tokens needed (re-authenticate with client credentials)

### Configuration Pattern

```yaml
auth:
  type: oauth2
  oauth2:
    client_id: ${POLARIS_CLIENT_ID}
    client_secret: ${POLARIS_CLIENT_SECRET}
    token_url: https://polaris.example.com/oauth/token
    token-refresh-enabled: true
    refresh_margin: 60  # Seconds before expiration to refresh
```

### Security Considerations
- Client credentials stored as `SecretStr` in Pydantic config
- Credentials passed via environment variables, never hardcoded
- OAuth2 tokens managed internally by PyIceberg (not exposed to calling code)

---

## Decision 3: Credential Vending Implementation

### Decision
Implement `vend_credentials()` using the Iceberg REST Catalog `X-Iceberg-Access-Delegation: vended-credentials` header pattern. PyIceberg handles this when configured.

### Rationale
- Standard Iceberg REST pattern supported by Polaris, AWS Glue, Unity Catalog, BigLake
- Returns temporary, scoped credentials (S3 STS tokens, GCS signed URLs, etc.)
- Enforces least-privilege access (scope to specific tables and operations)
- 1-24 hour TTL prevents credential sprawl

### Implementation Pattern

```python
def vend_credentials(
    self,
    table_path: str,
    operations: list[str],  # ["READ"], ["READ", "WRITE"]
) -> dict[str, Any]:
    """Vend temporary credentials via Iceberg REST protocol."""
    # PyIceberg with X-Iceberg-Access-Delegation header returns:
    table = self._catalog.load_table(table_path)
    # Credentials embedded in table.io configuration
    return {
        'access_key': table.io.properties.get('s3.access-key-id'),
        'secret_key': table.io.properties.get('s3.secret-access-key'),
        'token': table.io.properties.get('s3.session-token'),
        'expiration': table.io.properties.get('s3.session-token-expires-at'),
    }
```

### Unsupported Catalogs (Hive Metastore)
Raise `NotSupportedError` with actionable message:
```python
raise NotSupportedError(
    "Credential vending not supported by Hive Metastore. "
    "Configure storage credentials directly in compute plugin."
)
```

---

## Decision 4: Error Handling Strategy

### Decision
Map PyIceberg exceptions to floe plugin error types with actionable messages. Use retry with exponential backoff for transient failures.

### Exception Mapping

| PyIceberg Exception | Floe Error | Action |
|---------------------|------------|--------|
| `ServiceUnavailableError` | `CatalogUnavailableError` | Retry with backoff (up to 5 attempts) |
| `UnauthorizedError` | `AuthenticationError` | Refresh OAuth2 token, then retry |
| `ForbiddenError` | `PermissionError` | Log and raise (no retry) |
| `NamespaceAlreadyExistsError` | Log info, continue | Idempotent operation |
| `TableAlreadyExistsError` | `ConflictError` | Depends on config (error or update) |
| `NoSuchNamespaceError` | `NotFoundError` | Create namespace first |
| `NoSuchTableError` | `NotFoundError` | Table doesn't exist |

### Retry Configuration

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True
)
def connect_with_retry(config: dict) -> Catalog:
    return load_catalog('polaris', **config)
```

---

## Decision 5: OpenTelemetry Instrumentation Pattern

### Decision
Use OpenTelemetry Python SDK with semantic conventions for database spans. Every catalog operation emits a span with catalog context attributes.

### Span Naming Convention
- `catalog.connect` - Connection establishment
- `catalog.create_namespace` - Namespace creation
- `catalog.list_namespaces` - Namespace listing
- `catalog.create_table` - Table creation
- `catalog.load_table` - Table metadata retrieval
- `catalog.vend_credentials` - Credential vending

### Required Attributes (per spec FR-031)

```python
with tracer.start_as_current_span(
    "catalog.create_namespace",
    kind=SpanKind.CLIENT,
    attributes={
        # Semantic conventions
        "db.system": "iceberg",
        "db.operation": "CREATE_NAMESPACE",

        # Floe standard (per ADR-0006)
        "floe.catalog.system": "polaris",
        "floe.catalog.warehouse": warehouse_name,

        # Operation context
        "catalog.namespace": namespace_name,
        "catalog.location": location,  # No credentials!
    }
) as span:
    # Operation
    span.set_status(Status(StatusCode.OK))
```

### Forbidden Attributes (per spec FR-032)
- NO `credential`, `secret`, `token`, `password`, `api_key`
- NO PII (email, user IDs in non-anonymized form)
- NO large payloads (request/response bodies)

### Log Correlation

```python
import structlog
from opentelemetry import trace

def add_otel_context(logger, method_name, event_dict):
    """Add trace_id and span_id to structlog events."""
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict
```

---

## Decision 6: Configuration Model Design

### Decision
Use Pydantic v2 `BaseModel` with `ConfigDict(frozen=True, extra="forbid")` for all configuration. Secrets use `SecretStr` type.

### Configuration Hierarchy

```python
from pydantic import BaseModel, ConfigDict, SecretStr, Field

class OAuth2Config(BaseModel):
    """OAuth2 client credentials configuration."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: str
    client_secret: SecretStr
    token_url: str
    scope: str | None = None
    refresh_margin_seconds: int = Field(default=60, ge=10, le=300)

class PolarisCatalogConfig(BaseModel):
    """Polaris catalog plugin configuration."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    uri: str = Field(..., description="Polaris REST endpoint")
    warehouse: str = Field(..., description="Warehouse identifier")
    oauth2: OAuth2Config
    connect_timeout_seconds: int = Field(default=10, ge=1, le=60)
    read_timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=5, ge=0, le=10)
    credential_vending_enabled: bool = Field(default=True)
```

---

## Decision 7: Health Check Implementation

### Decision
Use lightweight `list_namespaces()` call for health checks with 1-second timeout. Track failure count for circuit breaker pattern.

### Implementation

```python
def health_check(self, timeout: float = 1.0) -> HealthStatus:
    """Check catalog availability."""
    start = time.time()
    try:
        self._catalog.list_namespaces()
        duration_ms = (time.time() - start) * 1000
        return HealthStatus(
            healthy=True,
            response_time_ms=duration_ms,
            message="Catalog responding normally"
        )
    except Exception as e:
        return HealthStatus(
            healthy=False,
            response_time_ms=timeout * 1000,
            message=f"Catalog unavailable: {str(e)}"
        )
```

---

## Decision 8: Test Strategy

### Decision
Three-tier testing: unit tests with mocks, contract tests for ABC compliance, integration tests with real Polaris in Kind cluster.

### Test Organization

| Test Type | Location | Dependencies | Markers |
|-----------|----------|--------------|---------|
| Unit | `plugins/floe-catalog-polaris/tests/unit/` | Mocks only | None |
| Contract | `tests/contract/test_catalog_plugin_abc.py` | Mock catalog | `@pytest.mark.requirement()` |
| Integration | `plugins/floe-catalog-polaris/tests/integration/` | Real Polaris | `@pytest.mark.requirement()`, `@pytest.mark.integration` |

### Base Test Class (REQ-040)

```python
# testing/base_classes/base_catalog_plugin_tests.py
class BaseCatalogPluginTests:
    """Compliance tests all CatalogPlugin implementations must pass."""

    @pytest.fixture
    def plugin(self) -> CatalogPlugin:
        """Subclass must provide plugin instance."""
        raise NotImplementedError

    @pytest.mark.requirement("REQ-031")
    def test_has_connect_method(self, plugin):
        assert hasattr(plugin, 'connect')
        assert callable(plugin.connect)

    @pytest.mark.requirement("REQ-034")
    def test_has_namespace_methods(self, plugin):
        assert hasattr(plugin, 'create_namespace')
        assert hasattr(plugin, 'list_namespaces')
        assert hasattr(plugin, 'delete_namespace')

    @pytest.mark.requirement("REQ-035")
    def test_has_vend_credentials_method(self, plugin):
        assert hasattr(plugin, 'vend_credentials')
```

---

## Summary of Technical Decisions

| Area | Decision | Confidence |
|------|----------|------------|
| Catalog Client | PyIceberg `load_catalog()` with REST type | High |
| Authentication | OAuth2 client credentials with auto-refresh | High |
| Credential Vending | X-Iceberg-Access-Delegation header | High |
| Error Handling | Map to floe errors + exponential backoff | High |
| Observability | OTel spans + structlog correlation | High |
| Configuration | Pydantic v2 with SecretStr | High |
| Health Checks | list_namespaces() with 1s timeout | High |
| Testing | Unit + Contract + Integration (Kind) | High |

---

## References

- [PyIceberg Documentation](https://py.iceberg.apache.org/)
- [PyIceberg Configuration](https://py.iceberg.apache.org/configuration/)
- [Iceberg REST Catalog Spec](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml)
- [Apache Polaris Documentation](https://polaris.apache.org/releases/1.0.0/)
- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/database/database-spans/)
- [Dremio Credential Vending Guide](https://www.dremio.com/blog/iceberg-credential-vending/)
