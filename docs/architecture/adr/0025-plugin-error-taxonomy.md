# ADR-0025: Plugin Error Taxonomy

## Status

Accepted

## Context

The floe plugin system currently has inconsistent error handling patterns across plugins:

| Plugin | Pattern | Example |
|--------|---------|---------|
| ComputePlugin | Result object with `success: bool` | `validate_connection() → ConnectionResult` |
| PolicyEnforcer | List of errors (empty = success) | `validate_data_product() → list[ValidationError]` |
| IdentityPlugin | `None` for invalid cases | `validate_token() → UserInfo | None` |
| OrchestratorPlugin | Implicit exceptions | `create_definitions()` raises on error |
| CatalogPlugin | Implicit exceptions | `connect()` raises on error |

This inconsistency creates several problems:

1. **Caller confusion**: Different error handling code paths per plugin type
2. **No retry semantics**: Callers cannot distinguish transient from permanent errors
3. **Poor observability**: Errors lack structured context for debugging
4. **Orchestration challenges**: No standard way to propagate plugin errors to lineage events

## Decision

Define a **unified PluginError hierarchy** with explicit error categories, retry semantics, and structured context. All plugins will use this hierarchy for error reporting.

### Error Categories

Errors are classified into categories that determine retry behavior:

| Category | Retryable | Max Retries | Examples |
|----------|-----------|-------------|----------|
| `TRANSIENT` | Yes | 3 | Network timeout, rate limited, temporary unavailable |
| `RESOURCE` | Yes | 5 | OOM, disk full, quota exceeded (may recover) |
| `CONFIGURATION` | No | 0 | Invalid config, missing required field |
| `VALIDATION` | No | 0 | Invalid input, schema violation |
| `PERMANENT` | No | 0 | Permission denied, resource not found |

### Error Severity

Severity indicates the impact level:

| Severity | Description |
|----------|-------------|
| `WARNING` | Degraded operation but functional |
| `ERROR` | Operation failed but plugin is usable |
| `CRITICAL` | Plugin is unusable, requires intervention |

### Error Hierarchy

```python
# floe_core/errors.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TypeVar, Generic
import traceback

class ErrorCategory(Enum):
    """Error category determines retry behavior."""
    TRANSIENT = "transient"          # Retry with backoff
    RESOURCE = "resource"            # Wait for resources, retry
    CONFIGURATION = "configuration"  # Fix config, no retry
    VALIDATION = "validation"        # Input error, no retry
    PERMANENT = "permanent"          # Cannot recover, no retry

class ErrorSeverity(Enum):
    """Error severity indicates impact level."""
    WARNING = "warning"    # Degraded but functional
    ERROR = "error"        # Operation failed
    CRITICAL = "critical"  # Plugin unusable

@dataclass
class PluginError(Exception):
    """Base class for all plugin errors.

    All plugin-related exceptions inherit from this class, providing
    consistent error handling across the plugin ecosystem.

    Attributes:
        code: Machine-readable error code (e.g., "COMPUTE_CONNECTION_TIMEOUT")
        message: Human-readable error description
        category: Error category for retry semantics
        severity: Impact level
        plugin_name: Name of the plugin that raised the error
        cause: Original exception if wrapping another error
        details: Additional structured context for debugging
    """
    code: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.ERROR
    plugin_name: str = ""
    cause: Optional[Exception] = None
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        # Set exception message
        super().__init__(self.message)

    @property
    def is_retryable(self) -> bool:
        """Check if this error can be retried."""
        return self.category in (ErrorCategory.TRANSIENT, ErrorCategory.RESOURCE)

    @property
    def retry_config(self) -> dict:
        """Get retry configuration for this error category."""
        configs = {
            ErrorCategory.TRANSIENT: {
                "max_retries": 3,
                "initial_delay_seconds": 1,
                "max_delay_seconds": 30,
                "backoff_multiplier": 2,
            },
            ErrorCategory.RESOURCE: {
                "max_retries": 5,
                "initial_delay_seconds": 5,
                "max_delay_seconds": 60,
                "backoff_multiplier": 2,
            },
        }
        return configs.get(self.category, {"max_retries": 0})

    def to_dict(self) -> dict:
        """Serialize error for logging and telemetry."""
        return {
            "code": self.code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "plugin_name": self.plugin_name,
            "is_retryable": self.is_retryable,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
            "traceback": traceback.format_exc() if self.cause else None,
        }

    def to_otel_attributes(self) -> dict:
        """Convert to OpenTelemetry span attributes."""
        return {
            "error.code": self.code,
            "error.message": self.message,
            "error.category": self.category.value,
            "error.severity": self.severity.value,
            "error.plugin": self.plugin_name,
            "error.retryable": self.is_retryable,
        }


# Specialized Error Classes

@dataclass
class PluginConnectionError(PluginError):
    """Failed to connect to external service.

    Use for: Database connections, API endpoints, network issues.
    Default category: TRANSIENT (networks are flaky)
    """
    host: str = ""
    port: int = 0

    def __post_init__(self):
        if not self.category:
            self.category = ErrorCategory.TRANSIENT
        if self.host:
            self.details["host"] = self.host
        if self.port:
            self.details["port"] = self.port
        super().__post_init__()


@dataclass
class PluginAuthenticationError(PluginError):
    """Authentication or authorization failure.

    Use for: Invalid credentials, expired tokens, permission denied.
    Default category: CONFIGURATION (usually needs credential fix)
    """
    principal: str = ""

    def __post_init__(self):
        if not self.category:
            self.category = ErrorCategory.CONFIGURATION
        if self.principal:
            self.details["principal"] = self.principal
        super().__post_init__()


@dataclass
class PluginConfigurationError(PluginError):
    """Plugin misconfiguration.

    Use for: Missing required config, invalid values, incompatible settings.
    Default category: CONFIGURATION (always)
    """
    config_key: str = ""
    expected: str = ""
    actual: str = ""

    def __post_init__(self):
        self.category = ErrorCategory.CONFIGURATION
        if self.config_key:
            self.details["config_key"] = self.config_key
        if self.expected:
            self.details["expected"] = self.expected
        if self.actual:
            self.details["actual"] = self.actual
        super().__post_init__()


@dataclass
class PluginValidationError(PluginError):
    """Input validation failure.

    Use for: Schema violations, constraint violations, invalid data.
    Default category: VALIDATION (always)
    """
    field: str = ""
    constraint: str = ""
    value: str = ""

    def __post_init__(self):
        self.category = ErrorCategory.VALIDATION
        if self.field:
            self.details["field"] = self.field
        if self.constraint:
            self.details["constraint"] = self.constraint
        if self.value:
            self.details["value"] = self.value
        super().__post_init__()


@dataclass
class PluginResourceError(PluginError):
    """Resource exhaustion or unavailable.

    Use for: OOM, disk full, quota exceeded, rate limited.
    Default category: RESOURCE (may recover)
    """
    resource_type: str = ""
    limit: str = ""
    current: str = ""

    def __post_init__(self):
        if not self.category:
            self.category = ErrorCategory.RESOURCE
        if self.resource_type:
            self.details["resource_type"] = self.resource_type
        if self.limit:
            self.details["limit"] = self.limit
        if self.current:
            self.details["current"] = self.current
        super().__post_init__()


@dataclass
class PluginExecutionError(PluginError):
    """Execution failure during plugin operation.

    Use for: SQL errors, transformation failures, unexpected results.
    Default category: Depends on cause
    """
    operation: str = ""
    sql: str = ""

    def __post_init__(self):
        if not self.category:
            self.category = ErrorCategory.PERMANENT
        if self.operation:
            self.details["operation"] = self.operation
        if self.sql:
            self.details["sql"] = self.sql[:500]  # Truncate long SQL
        super().__post_init__()


@dataclass
class PluginNotFoundError(PluginError):
    """Requested plugin is not available.

    Use for: Unknown plugin type, plugin not installed.
    Default category: CONFIGURATION (always)
    """
    requested_plugin: str = ""
    available_plugins: list = field(default_factory=list)

    def __post_init__(self):
        self.category = ErrorCategory.CONFIGURATION
        if self.requested_plugin:
            self.details["requested_plugin"] = self.requested_plugin
        if self.available_plugins:
            self.details["available_plugins"] = self.available_plugins
        super().__post_init__()


@dataclass
class PluginIncompatibleError(PluginError):
    """Plugin version is incompatible.

    Use for: API version mismatch, unsupported features.
    Default category: CONFIGURATION (always)
    """
    plugin_version: str = ""
    required_version: str = ""

    def __post_init__(self):
        self.category = ErrorCategory.CONFIGURATION
        if self.plugin_version:
            self.details["plugin_version"] = self.plugin_version
        if self.required_version:
            self.details["required_version"] = self.required_version
        super().__post_init__()
```

### PluginResult Wrapper

For operations that can succeed or fail, use a `PluginResult` wrapper:

```python
# floe_core/result.py
from dataclasses import dataclass, field
from typing import TypeVar, Generic, Optional, Callable

T = TypeVar('T')

@dataclass
class PluginResult(Generic[T]):
    """Result wrapper for plugin operations.

    Provides a consistent pattern for returning success/failure
    without using exceptions for control flow.

    Usage:
        result = plugin.validate_connection(config)
        if result.is_success:
            connection = result.unwrap()
        else:
            error = result.error
            if error.is_retryable:
                # retry logic
    """
    value: Optional[T] = None
    error: Optional[PluginError] = None
    warnings: list[PluginError] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Check if operation succeeded."""
        return self.error is None

    @property
    def is_failure(self) -> bool:
        """Check if operation failed."""
        return self.error is not None

    @property
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0

    def unwrap(self) -> T:
        """Get the value, raising error if failed.

        Raises:
            PluginError: If the result is a failure
        """
        if self.error:
            raise self.error
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get the value or a default if failed."""
        return self.value if self.is_success else default

    def unwrap_or_else(self, fn: Callable[[], T]) -> T:
        """Get the value or compute a default if failed."""
        return self.value if self.is_success else fn()

    def map(self, fn: Callable[[T], 'U']) -> 'PluginResult[U]':
        """Transform the success value."""
        if self.is_success:
            return PluginResult(value=fn(self.value), warnings=self.warnings)
        return PluginResult(error=self.error, warnings=self.warnings)

    @staticmethod
    def ok(value: T, warnings: list[PluginError] = None) -> 'PluginResult[T]':
        """Create a success result."""
        return PluginResult(value=value, warnings=warnings or [])

    @staticmethod
    def fail(error: PluginError, warnings: list[PluginError] = None) -> 'PluginResult[T]':
        """Create a failure result."""
        return PluginResult(error=error, warnings=warnings or [])
```

### Updated Plugin Interfaces

Plugin interfaces are updated to use the error taxonomy:

```python
# floe_core/interfaces/compute.py
from abc import ABC, abstractmethod
from floe_core.errors import PluginError, PluginConnectionError
from floe_core.result import PluginResult

class ComputePlugin(ABC):
    """Interface for compute engines where dbt transforms execute.

    Error Handling:
        Methods return PluginResult for operations that can fail.
        Use specific error types from floe_core.errors:
        - PluginConnectionError for connection issues
        - PluginConfigurationError for config problems
        - PluginExecutionError for runtime failures
    """

    name: str
    version: str
    is_self_hosted: bool

    @abstractmethod
    def validate_connection(self, config: ComputeConfig) -> PluginResult[ConnectionInfo]:
        """Test connection to compute engine.

        Returns:
            PluginResult containing ConnectionInfo on success.

        Error Codes:
            COMPUTE_CONNECTION_TIMEOUT (TRANSIENT) - Connection timed out
            COMPUTE_CONNECTION_REFUSED (TRANSIENT) - Connection refused
            COMPUTE_AUTH_FAILED (CONFIGURATION) - Invalid credentials
            COMPUTE_HOST_UNREACHABLE (CONFIGURATION) - Host not found
        """
        pass

    @abstractmethod
    def generate_dbt_profile(self, config: ComputeConfig) -> PluginResult[dict]:
        """Generate dbt profile.yml configuration.

        Error Codes:
            COMPUTE_CONFIG_INVALID (CONFIGURATION) - Invalid configuration
            COMPUTE_CONFIG_MISSING (CONFIGURATION) - Required config missing
        """
        pass


# Example implementation
class DuckDBComputePlugin(ComputePlugin):
    name = "duckdb"
    version = "1.0.0"
    is_self_hosted = True

    def validate_connection(self, config: ComputeConfig) -> PluginResult[ConnectionInfo]:
        try:
            # Attempt connection
            conn = duckdb.connect(config.path)
            conn.execute("SELECT 1")
            return PluginResult.ok(ConnectionInfo(
                connected=True,
                latency_ms=5.0,
                version=conn.execute("SELECT version()").fetchone()[0],
            ))
        except duckdb.IOException as e:
            return PluginResult.fail(PluginConnectionError(
                code="COMPUTE_CONNECTION_FAILED",
                message=f"Failed to connect to DuckDB: {e}",
                plugin_name=self.name,
                host=config.path,
                cause=e,
            ))
        except Exception as e:
            return PluginResult.fail(PluginExecutionError(
                code="COMPUTE_UNEXPECTED_ERROR",
                message=f"Unexpected error: {e}",
                plugin_name=self.name,
                cause=e,
            ))
```

### Retry Implementation

The orchestration layer uses error categories for retry decisions:

```python
# floe_core/retry.py
import asyncio
from typing import TypeVar, Callable, Awaitable
from floe_core.errors import PluginError, ErrorCategory

T = TypeVar('T')

async def with_retry(
    operation: Callable[[], Awaitable[T]],
    error_handler: Callable[[PluginError], None] = None,
) -> T:
    """Execute operation with retry based on error category.

    Args:
        operation: Async function to execute
        error_handler: Optional callback for logging/metrics

    Raises:
        PluginError: If all retries exhausted or error is not retryable
    """
    last_error: PluginError = None

    while True:
        try:
            return await operation()
        except PluginError as e:
            last_error = e

            if error_handler:
                error_handler(e)

            if not e.is_retryable:
                raise

            retry_config = e.retry_config
            current_retries = e.details.get("_retry_count", 0)

            if current_retries >= retry_config["max_retries"]:
                raise

            # Calculate delay with exponential backoff
            delay = min(
                retry_config["initial_delay_seconds"] * (retry_config["backoff_multiplier"] ** current_retries),
                retry_config["max_delay_seconds"],
            )

            await asyncio.sleep(delay)

            # Track retry count
            e.details["_retry_count"] = current_retries + 1
```

### OpenLineage Integration

Plugin errors integrate with OpenLineage events:

```python
# floe_core/lineage.py
from openlineage.client.facet import ErrorMessageRunFacet
from floe_core.errors import PluginError

def plugin_error_to_facet(error: PluginError) -> ErrorMessageRunFacet:
    """Convert PluginError to OpenLineage error facet."""
    return ErrorMessageRunFacet(
        message=error.message,
        programmingLanguage="python",
        stackTrace=error.to_dict().get("traceback"),
    )

def emit_error_lineage(
    emitter: LineageEmitter,
    job: str,
    run_id: str,
    error: PluginError,
):
    """Emit OpenLineage FAIL event with error details."""
    emitter.emit(
        RunEvent(
            eventType=RunState.FAIL,
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=Run(
                runId=run_id,
                facets={
                    "errorMessage": plugin_error_to_facet(error),
                    "floe": FloeFacet(
                        error_code=error.code,
                        error_category=error.category.value,
                        error_retryable=error.is_retryable,
                        plugin_name=error.plugin_name,
                    ),
                },
            ),
            job=Job(namespace="floe", name=job),
        )
    )
```

## Consequences

### Positive

- **Consistent error handling**: All plugins use the same patterns
- **Clear retry semantics**: Callers know when to retry
- **Better observability**: Structured errors enable debugging
- **OpenLineage integration**: Errors captured in lineage
- **Type safety**: Generic PluginResult provides compile-time checks

### Negative

- **Migration effort**: Existing plugins need updates
- **Learning curve**: Plugin authors need to understand taxonomy
- **More verbose code**: Explicit error handling adds lines

### Neutral

- **Documentation requirement**: Each plugin must document error codes
- **Testing requirement**: Error paths need explicit tests

## Migration Guide

### Step 1: Add Error Dependency

```python
# In plugin's pyproject.toml
dependencies = [
    "floe-core>=0.2.0",  # Includes error taxonomy
]
```

### Step 2: Update Method Signatures

Before:
```python
def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
    ...
```

After:
```python
def validate_connection(self, config: ComputeConfig) -> PluginResult[ConnectionInfo]:
    ...
```

### Step 3: Replace Exceptions with Results

Before:
```python
def connect(self, config: dict) -> Catalog:
    try:
        return PyIcebergCatalog(config)
    except Exception as e:
        raise RuntimeError(f"Failed to connect: {e}")
```

After:
```python
def connect(self, config: dict) -> PluginResult[Catalog]:
    try:
        catalog = PyIcebergCatalog(config)
        return PluginResult.ok(catalog)
    except ConnectionError as e:
        return PluginResult.fail(PluginConnectionError(
            code="CATALOG_CONNECTION_FAILED",
            message=f"Failed to connect to catalog: {e}",
            plugin_name=self.name,
            cause=e,
        ))
```

## Error Code Registry

Each plugin registers its error codes:

| Plugin | Code | Category | Description |
|--------|------|----------|-------------|
| compute-duckdb | COMPUTE_CONNECTION_FAILED | TRANSIENT | DuckDB file unavailable |
| compute-snowflake | COMPUTE_AUTH_FAILED | CONFIGURATION | Invalid Snowflake credentials |
| catalog-polaris | CATALOG_NAMESPACE_NOT_FOUND | PERMANENT | Namespace doesn't exist |
| catalog-polaris | CATALOG_CONNECTION_TIMEOUT | TRANSIENT | Polaris server timeout |
| ingestion-dlt | INGESTION_SOURCE_ERROR | TRANSIENT | Source API error |
| ingestion-dlt | INGESTION_SCHEMA_MISMATCH | VALIDATION | Schema doesn't match |

## References

- [Plugin Interfaces](../interfaces/index.md)
- [Plugin Architecture](../plugin-architecture.md)
- [ADR-0010: Target-Agnostic Compute](./0010-target-agnostic-compute.md)
- [OpenLineage Run Events](https://openlineage.io/docs/spec/run-events)
- [Rust Result Pattern](https://doc.rust-lang.org/std/result/) (inspiration)
