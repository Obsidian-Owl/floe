# Research: Tech Debt Resolution (Epic 12B)

**Date**: 2026-01-22
**Feature**: Tech Debt Resolution
**Status**: Complete

## Prior Decisions (from Agent-Memory)

Agent-memory search revealed prior context on circular dependency resolution:

1. **Separation of Concerns**: Each component (dbt, Dagster, Iceberg) owns its specific domain
2. **Circular Dependency Pattern**: Occurs when two or more modules depend on each other, creating a loop
3. **Resolution Strategy**: Layer separation - ensure lower layers don't depend on higher layers

## Research Topics

### 1. Circular Dependency Resolution Patterns

**Question**: What is the best approach to break the schemas → telemetry → plugins cycle?

**Research Findings**:

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| Move TelemetryConfig to schemas/ | Simple, maintains coupling | Telemetry config in wrong conceptual location | **SELECTED** - pragmatic |
| Use TYPE_CHECKING imports | No module moves | Runtime type info unavailable | Not suitable for Pydantic |
| Create shared/common module | Clean separation | Additional module to maintain | Overkill for single type |
| Interface extraction | Decouples via abstraction | Complexity for simple config | Not needed |

**Decision**: Move `TelemetryConfig` from `telemetry/config.py` to `schemas/telemetry.py`
**Rationale**:
- TelemetryConfig is a Pydantic model (data schema), so schemas/ is appropriate
- Minimal code changes required
- Maintains runtime type information for Pydantic validation
- Re-export from `telemetry/config.py` for backward compatibility

**Implementation**:
```python
# schemas/telemetry.py (NEW)
class TelemetryConfig(BaseModel):
    """Telemetry configuration schema."""
    ...

# telemetry/config.py (MODIFIED - re-export for compatibility)
from floe_core.schemas.telemetry import TelemetryConfig  # Re-export
__all__ = ["TelemetryConfig"]

# compiled_artifacts.py (MODIFIED)
from floe_core.schemas.telemetry import TelemetryConfig  # Direct import
```

---

### 2. Strategy Pattern for Error Mapping

**Question**: How to refactor `map_pyiceberg_error()` from CC 26 to CC ≤10?

**Research Findings**:

| Pattern | Applicability | Complexity Reduction |
|---------|---------------|---------------------|
| Dispatch Dictionary | Exception type → handler | CC 26 → ~5 |
| Chain of Responsibility | Complex conditions | CC 26 → ~8 |
| Match Statement (3.10+) | Type matching | CC 26 → ~20 (still high) |

**Decision**: Use dispatch dictionary with type → handler mapping
**Rationale**:
- Most significant CC reduction (26 → ~5)
- Each handler is independently testable
- Easy to extend with new error types
- Aligns with composability principle (ADR-0037)

**Implementation**:
```python
# BEFORE: 16 if-statements
def map_pyiceberg_error(error, catalog_uri=None, operation=None):
    if isinstance(error, ServiceUnavailableError):
        return CatalogUnavailableError(...)
    if isinstance(error, UnauthorizedError):
        return CatalogAuthError(...)
    # ... 14 more if statements

# AFTER: Dispatch dictionary
ERROR_HANDLERS: dict[type[Exception], Callable] = {
    ServiceUnavailableError: _handle_unavailable,
    UnauthorizedError: _handle_unauthorized,
    # ... all error types
}

def map_pyiceberg_error(error, catalog_uri=None, operation=None):
    handler = ERROR_HANDLERS.get(type(error), _handle_unknown)
    return handler(error, catalog_uri, operation)

def _handle_unavailable(error, catalog_uri, operation):
    return CatalogUnavailableError(
        message=f"Catalog unavailable: {error}",
        catalog_uri=catalog_uri,
        operation=operation,
    )
```

---

### 3. God Module Decomposition Strategy

**Question**: How to split plugin_registry.py (1230 lines, 20 methods) into focused modules?

**Research Findings**:

**Current Responsibilities Analysis**:
1. Entry point discovery (~200 lines)
2. Plugin loading/instantiation (~200 lines)
3. Lifecycle management (activate, shutdown, health) (~250 lines)
4. Dependency resolution (~200 lines)
5. Registry operations (get, list, filter) (~300 lines)
6. Validation and error handling (~80 lines)

**Decision**: Apply Single Responsibility Principle with Facade pattern
**Rationale**:
- Each responsibility becomes a focused module
- PluginRegistry becomes thin facade delegating to helpers
- Maintains backward compatibility via facade
- Each module independently testable

**Target Structure**:
```text
plugins/
├── __init__.py           # Public API (PluginRegistry facade)
├── discovery.py          # Entry point discovery (~200 lines)
├── loader.py             # Plugin instantiation (~200 lines)
├── lifecycle.py          # Activation, shutdown, health (~250 lines)
├── dependencies.py       # Dependency resolution (~200 lines)
└── registry.py           # Core registry operations (~300 lines)
```

**Facade Pattern**:
```python
# plugins/__init__.py
from floe_core.plugins.registry import PluginRegistry

# Backward compatibility
__all__ = ["PluginRegistry", "get_registry"]

# plugins/registry.py (facade)
class PluginRegistry:
    """Facade for plugin operations."""

    def __init__(self):
        self._discovery = PluginDiscovery()
        self._loader = PluginLoader()
        self._lifecycle = PluginLifecycle()
        self._deps = DependencyResolver()

    def discover(self) -> list[PluginMetadata]:
        return self._discovery.discover_all()

    def load(self, name: str) -> Plugin:
        metadata = self._discovery.get(name)
        deps = self._deps.resolve(metadata)
        return self._loader.load(metadata, deps)
```

---

### 4. OCI Client Decomposition

**Question**: How to split oci/client.py (1389 lines, 27 methods)?

**Research Findings**:

**Current Responsibilities**:
1. Manifest operations (fetch, parse, validate) (~400 lines)
2. Layer operations (download, extract, cache) (~400 lines)
3. Authentication (OAuth, basic) (~200 lines) - already in auth.py
4. Caching (~100 lines) - already in cache.py
5. Client orchestration (~300 lines)

**Decision**: Extract manifest and layer operations, keep client as orchestrator
**Rationale**:
- auth.py and cache.py already exist
- Manifest and layer operations are distinct concerns
- Client becomes thin orchestrator

**Target Structure**:
```text
oci/
├── __init__.py           # Public API
├── client.py             # Orchestrator facade (~400 lines)
├── manifest.py           # Manifest operations (~400 lines)
├── layers.py             # Layer operations (~400 lines)
├── auth.py               # Authentication (existing)
└── cache.py              # Caching (existing)
```

---

### 5. Implementing drop_table() for Iceberg

**Question**: How to implement `drop_table()` to enable the 3 skipped tests?

**Research Findings**:

**PyIceberg API**:
```python
# PyIceberg catalog API
catalog.drop_table("namespace.table_name")  # Removes metadata
catalog.drop_table("namespace.table_name", purge=True)  # Also removes data files
```

**Existing Pattern in IcebergTableManager**:
```python
def create_table(self, name: str, schema: Schema) -> Table:
    return self._catalog.create_table(name, schema)

def load_table(self, name: str) -> Table:
    return self._catalog.load_table(name)
```

**Decision**: Follow existing pattern, wrap PyIceberg catalog.drop_table()
**Rationale**:
- Consistent with existing table operations
- PyIceberg handles catalog and storage cleanup
- purge parameter controls data file deletion

**Implementation**:
```python
def drop_table(
    self,
    name: str,
    purge: bool = False,
) -> None:
    """Drop a table from the catalog.

    Args:
        name: Fully qualified table name (namespace.table)
        purge: If True, also delete data files. If False, only metadata.

    Raises:
        TableNotFoundError: If table does not exist
        TableInUseError: If table has active operations (future)
    """
    try:
        self._catalog.drop_table(name, purge=purge)
        logger.info("table_dropped", table=name, purge=purge)
    except NoSuchTableError as e:
        raise TableNotFoundError(f"Table not found: {name}") from e
```

---

### 6. Dependency Pinning Strategy

**Question**: What upper bounds should be used for critical dependencies?

**Research Findings**:

| Package | Current | Latest | Breaking Changes Risk | Recommended Bound |
|---------|---------|--------|----------------------|-------------------|
| pydantic | >=2.0 | 2.12.5 | HIGH (v3 planned) | >=2.12.5,<3.0 |
| kubernetes | >=28.0.0 | 35.0.0 | MEDIUM (API changes) | >=35.0.0,<36.0 |
| pyiceberg | >=0.9.0 | 0.10.0 | HIGH (active dev) | >=0.10.0,<0.11.0 |
| opentelemetry-api | >=1.20.0 | 1.39.1 | LOW (stable) | >=1.39.0,<2.0 |
| pyarrow | >=14.0 | 22.0.0 | MEDIUM | >=22.0.0,<23.0 |

**Decision**: Pin with `<MAJOR+1.0` for all critical dependencies
**Rationale**:
- Protects against major version breaking changes
- Allows minor/patch updates within major version
- Balances stability with security updates

---

### 7. Test Duplication Reduction Patterns

**Question**: How to reduce 31.6% test duplication to ≤15%?

**Research Findings**:

**Major Duplication Areas**:
1. Audit event tests (3 files, ~350 lines overlap)
2. Dry-run mode tests (2 files, ~300 lines overlap)
3. Plugin discovery tests (Keycloak/Infisical not using base class)
4. Health check tests (2 files, ~500 lines similar)

**Patterns to Apply**:

| Pattern | Applicability | Reduction |
|---------|---------------|-----------|
| Extract to conftest.py | Shared fixtures | ~200 lines |
| Parametrize tests | Same test, different inputs | ~150 lines |
| Base*Tests classes | Common test patterns | ~400 lines |
| Fixture factories | Complex object creation | ~100 lines |

**Decision**: Apply all four patterns systematically
**Rationale**:
- Combined reduction targets ~850 lines
- Current duplication is ~1000+ lines (31.6% of ~3200 test lines)
- Target 15% = ~480 lines duplication allowed

**Implementation Priority**:
1. Create BasePluginDiscoveryTests (Keycloak/Infisical inherit)
2. Create BaseHealthCheckTests
3. Extract audit event fixtures to conftest.py
4. Parametrize dry-run tests

---

## Summary

All research topics resolved. No NEEDS CLARIFICATION markers remaining.

| Topic | Decision | Confidence |
|-------|----------|------------|
| Circular dependency | Move TelemetryConfig to schemas/ | HIGH |
| Error mapping | Strategy pattern dispatch | HIGH |
| plugin_registry.py split | SRP with Facade | HIGH |
| oci/client.py split | Extract manifest/layers | HIGH |
| drop_table() | Wrap PyIceberg API | HIGH |
| Dependency pinning | <MAJOR+1.0 bounds | HIGH |
| Test duplication | Base classes + parametrize | HIGH |
