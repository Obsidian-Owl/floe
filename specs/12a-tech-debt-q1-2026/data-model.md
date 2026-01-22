# Data Model: January 2026 Tech Debt Reduction

**Date**: 2026-01-22
**Epic**: 12A (Tech Debt Q1 2026)

## Overview

This epic involves refactoring existing code, not creating new data models. The entities below are **existing** classes that will be modified or decomposed.

## Entities (Modified)

### 1. IcebergTableManager (Decomposed)

**Current State**: God class with 30 methods, 1,269 lines
**Target State**: Facade with 5 public methods, delegating to 4 internal classes

```text
┌─────────────────────────────────────┐
│     IcebergTableManager (Facade)    │
│                                     │
│  + create(name, schema) → Table     │
│  + drop(name) → None                │
│  + get(name) → Table                │
│  + evolve_schema(name, schema) → T  │
│  + compact(name) → None             │
└─────────────┬───────────────────────┘
              │ delegates to
    ┌─────────┼─────────┬─────────────┐
    ▼         ▼         ▼             ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│Lifecycle│ │ Schema │ │Snapshot│ │Compaction│
│ _class  │ │_Manager│ │_Manager│ │ _Manager │
└────────┘ └────────┘ └────────┘ └──────────┘
```

**Internal Classes**:

| Class | Responsibility | Key Methods |
|-------|---------------|-------------|
| `_IcebergTableLifecycle` | Table CRUD | create, drop, exists, rename, list_tables |
| `_IcebergSchemaManager` | Schema evolution | evolve, get_schema, add_column, drop_column |
| `_IcebergSnapshotManager` | Snapshot management | snapshot, rollback, expire, cherry_pick |
| `_IcebergCompactionManager` | File optimization | compact, rewrite_manifests, rewrite_data_files |

### 2. OCIClient (Refactored)

**Current State**: 800+ LOC, CC 27 in pull(), N+1 in list()
**Target State**: <500 LOC, CC ≤12 in pull(), parallel list()

**New Internal Class**:

| Class | Responsibility | Key Methods |
|-------|---------------|-------------|
| `_BatchFetcher` | Parallel HTTP operations | fetch_all(urls, max_workers) |

**Modified Methods**:

| Method | Current CC | Target CC | Change |
|--------|-----------|-----------|--------|
| `pull()` | 27 | ≤12 | Extract helper methods |
| `list()` | 15 | ≤10 | Use `_BatchFetcher` |

### 3. PluginRegistry (Extended)

**Added Parameter**:
```python
def list(
    self,
    plugin_type: str,
    limit: int | None = None  # NEW: bounds result set
) -> list[PluginMetadata]:
    ...
```

### 4. PolicyEnforcer (Extended)

**Added Parameter**:
```python
def enforce(
    self,
    artifact: CompiledArtifacts,
    max_violations: int | None = None  # NEW: early exit after N violations
) -> EnforcementResult:
    ...
```

### 5. RBACPermissionAggregator (Extended)

**Added Caching**:
```python
@lru_cache(maxsize=256)
def aggregate_permissions(
    self,
    principal: str,
    resource: str
) -> set[Permission]:
    ...
```

## Entities (New)

### 1. BasePluginMetadataTests

**Location**: `testing/base_classes/plugin_metadata_tests.py`
**Purpose**: Reusable test class for plugin metadata validation

**Attributes**:
- `plugin_class`: Abstract fixture (subclass provides)

**Test Methods**:
- `test_has_plugin_metadata()`
- `test_metadata_has_required_fields()`
- `test_metadata_version_format()`
- `test_floe_api_version_compatible()`

### 2. BasePluginLifecycleTests

**Location**: `testing/base_classes/plugin_lifecycle_tests.py`
**Purpose**: Reusable test class for plugin lifecycle hooks

**Attributes**:
- `plugin_instance`: Abstract fixture (subclass provides)

**Test Methods**:
- `test_initialize_succeeds()`
- `test_shutdown_succeeds()`
- `test_double_initialize_safe()`
- `test_shutdown_before_initialize_safe()`

### 3. BasePluginDiscoveryTests

**Location**: `testing/base_classes/plugin_discovery_tests.py`
**Purpose**: Reusable test class for entry point discovery

**Attributes**:
- `entry_point_group`: Abstract fixture (subclass provides)
- `plugin_class`: Abstract fixture (subclass provides)

**Test Methods**:
- `test_registered_in_entry_points()`
- `test_loadable_from_entry_point()`
- `test_entry_point_name_matches_metadata()`

## Relationships

```text
┌──────────────────────────────────────────────────────────┐
│                    Plugin System                          │
│                                                           │
│  PluginRegistry ─────────────────► RBACPlugin (ABC)      │
│       │                                   ▲               │
│       │ discovers                         │ implements    │
│       ▼                                   │               │
│  [entry points] ◄──────────────── K8sRBACPlugin          │
│                                                           │
│  ⚠️ floe_core MUST NOT import K8sRBACPlugin directly      │
│                                                           │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                   Test Hierarchy                          │
│                                                           │
│  BasePluginMetadataTests ◄─── TestComputePluginMeta      │
│  BasePluginLifecycleTests ◄── TestComputePluginLifecycle │
│  BasePluginDiscoveryTests ◄── TestComputePluginDiscovery │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

## Validation Rules

### IcebergTableManager Facade

- Public methods ≤ 5
- Each internal class has single responsibility
- Public API unchanged (backward compatible)

### OCIClient

- Total LOC < 500
- No method with CC > 12
- list() uses parallel fetching
- pull() uses O(1) tag lookup

### Test Base Classes

- All abstract fixtures raise NotImplementedError
- All test methods have @pytest.mark.requirement() markers
- No test method uses pytest.skip()

## State Transitions

### Plugin Lifecycle

```text
                    ┌─────────────┐
                    │ UNLOADED    │
                    └──────┬──────┘
                           │ registry.load()
                           ▼
                    ┌─────────────┐
                    │ LOADED      │
                    └──────┬──────┘
                           │ plugin.initialize()
                           ▼
                    ┌─────────────┐
        ◄───────────│ INITIALIZED │───────────►
shutdown()          └─────────────┘        use normally
        │                                      │
        ▼                                      │
┌─────────────┐                                │
│ SHUTDOWN    │ ◄──────────────────────────────┘
└─────────────┘
```

## Migration Notes

### Breaking Changes

**None** - All changes are backward compatible:
- IcebergTableManager facade preserves public API
- OCIClient public methods unchanged
- New parameters are optional with defaults

### Deprecations

**None** - No deprecations in this epic

### Test Migration

Plugins migrating to base test classes:
1. Inherit from base class
2. Implement abstract fixtures
3. Delete redundant test methods
4. Verify all tests pass
