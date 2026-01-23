# Research: January 2026 Tech Debt Reduction

**Date**: 2026-01-22
**Epic**: 12A (Tech Debt Q1 2026)

## Prior Decisions (from Agent-Memory)

- **Composability as core principle**: Plugin architectures preferred over configuration switches for flexibility (source: agent-memory)
- **Facade pattern for simplification**: When refactoring god classes, facade pattern maintains backward compatibility while enabling SRP (source: agent-memory)
- **Strategy pattern for complexity reduction**: Replacing complex conditionals with strategy pattern improves testability (source: agent-memory)

## Research Topics

### 1. Circular Dependency Resolution

**Question**: Best approach for breaking floe_core ↔ floe_rbac_k8s cycle?

**Decision**: Dependency injection via plugin registry lookup

**Rationale**:
- floe already has a plugin registry with entry point discovery
- RBACPlugin ABC already exists - just need to use it consistently
- Registry lookup at runtime (lazy loading) breaks the import cycle
- No additional frameworks or patterns needed

**Alternatives Considered**:
1. **Package extraction** - Move shared code to new package → Rejected: Too invasive, deferred to future epic
2. **Import at use-site** - Move import inside function → Rejected: Code smell, doesn't fix design issue
3. **Interface segregation** - Split ABC further → Rejected: RBACPlugin ABC is already appropriately scoped

**Implementation Pattern**:
```python
# Before (circular)
from floe_rbac_k8s import K8sRBACPlugin  # Direct concrete import

# After (registry lookup)
from floe_core.plugin_registry import registry
plugin = registry.get("rbac", "k8s")  # Runtime lookup
```

### 2. N+1 Performance Fix Approach

**Question**: ThreadPoolExecutor vs asyncio for parallel HTTP calls?

**Decision**: ThreadPoolExecutor with configurable max_workers (default 10)

**Rationale**:
- Existing OCI client is synchronous
- Converting to async would require broader refactoring
- ThreadPoolExecutor is sufficient for I/O-bound HTTP calls
- Standard library, no additional dependencies

**Alternatives Considered**:
1. **asyncio + httpx.AsyncClient** → Rejected: Requires async conversion throughout
2. **multiprocessing.Pool** → Rejected: Overkill for I/O-bound work, GIL not a bottleneck
3. **aiohttp** → Rejected: Same issue as asyncio, plus new dependency

**Implementation Pattern**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def list_tags_parallel(self, tags: list[str], max_workers: int = 10) -> dict[str, Manifest]:
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(self._fetch_tag, tag): tag for tag in tags}
        results = {}
        for future in as_completed(futures):
            tag = futures[future]
            results[tag] = future.result()
    return results
```

### 3. Complexity Refactoring Patterns

**Question**: How to safely reduce CC from 30 to 10?

**Decision**: Extract Method + Strategy pattern, validated with golden tests

**Rationale**:
- Extract Method reduces CC by moving branches to separate functions
- Strategy pattern converts switch/if-else chains to polymorphic dispatch
- Golden tests capture exact behavior before refactoring
- Behavior-preserving transformation is verifiable

**Refactoring Recipe for diff_command() (CC 30→10)**:
1. Create golden tests with known inputs/outputs
2. Extract each condition branch to helper function
3. Extract common setup/teardown to separate functions
4. Replace conditional chains with strategy dispatch where applicable
5. Verify golden tests still pass
6. Measure CC with radon

**Strategy Pattern Application (_generate_impl)**:
```python
# Before (CC 15+)
def _generate_impl(variant: str, config: dict) -> Result:
    if variant == "type_a":
        # 20 lines of type_a logic
    elif variant == "type_b":
        # 20 lines of type_b logic
    elif variant == "type_c":
        # 20 lines of type_c logic

# After (CC 3)
class GeneratorStrategy(Protocol):
    def generate(self, config: dict) -> Result: ...

_STRATEGIES: dict[str, GeneratorStrategy] = {
    "type_a": TypeAGenerator(),
    "type_b": TypeBGenerator(),
    "type_c": TypeCGenerator(),
}

def _generate_impl(variant: str, config: dict) -> Result:
    strategy = _STRATEGIES[variant]
    return strategy.generate(config)
```

### 4. God Class Splitting (IcebergTableManager)

**Question**: How to split 30-method class while maintaining backward compatibility?

**Decision**: Facade pattern with internal (underscore-prefixed) specialized classes

**Rationale**:
- Facade preserves existing public API
- Internal classes (underscore prefix) prevent direct imports
- Each specialized class has single responsibility
- Testing can target internal classes directly or through facade

**Class Decomposition**:
| New Class | Responsibility | Methods from Manager |
|-----------|---------------|---------------------|
| `_IcebergTableLifecycle` | Table CRUD | create, drop, exists, rename |
| `_IcebergSchemaManager` | Schema ops | evolve, get_schema, update_schema |
| `_IcebergSnapshotManager` | Snapshot ops | snapshot, rollback, expire_snapshots |
| `_IcebergCompactionManager` | File ops | compact, rewrite_manifests, optimize |

**Facade Implementation**:
```python
class IcebergTableManager:
    """Facade for Iceberg table operations. Public API."""

    def __init__(self, catalog: Catalog) -> None:
        self._lifecycle = _IcebergTableLifecycle(catalog)
        self._schema = _IcebergSchemaManager(catalog)
        self._snapshot = _IcebergSnapshotManager(catalog)
        self._compaction = _IcebergCompactionManager(catalog)

    # Delegate to appropriate internal class
    def create(self, name: str, schema: Schema) -> Table:
        return self._lifecycle.create(name, schema)
```

### 5. Test Policy Compliance (pytest.skip removal)

**Question**: How to handle tests requiring infrastructure without skipping?

**Decision**: IntegrationTestBase.check_infrastructure() pattern with clear failure messages

**Rationale**:
- Tests should FAIL, not skip (per constitution)
- Failure message must clearly indicate what infrastructure is needed
- IntegrationTestBase already provides this pattern
- CI visibility improves when tests fail vs skip

**Implementation Pattern**:
```python
# Before (violates policy)
def test_iceberg_write():
    if not polaris_available():
        pytest.skip("Polaris not available")
    # test code

# After (compliant)
class TestIcebergIOManager(IntegrationTestBase):
    required_services = [("polaris", 8181)]

    def test_iceberg_write(self):
        self.check_infrastructure("polaris", 8181)  # Fails with clear message
        # test code
```

### 6. Base Test Classes for Plugins

**Question**: What common test patterns should be extracted?

**Decision**: Three base classes covering metadata, lifecycle, and discovery

**Rationale**:
- All plugins share: metadata validation, lifecycle hooks, entry point discovery
- ~35% test duplication identified in audit
- Inheritance with abstract fixtures enables plugin-specific customization

**Base Class Design**:

```python
class BasePluginMetadataTests:
    """Tests every plugin must pass for metadata compliance."""

    @pytest.fixture
    def plugin_class(self) -> type:
        """Override to return the plugin class to test."""
        raise NotImplementedError

    def test_has_plugin_metadata(self, plugin_class):
        assert hasattr(plugin_class, "metadata")

    def test_metadata_has_required_fields(self, plugin_class):
        metadata = plugin_class.metadata
        assert metadata.name is not None
        assert metadata.version is not None
        assert metadata.floe_api_version is not None

class BasePluginLifecycleTests:
    """Tests for plugin startup/shutdown lifecycle."""

    @pytest.fixture
    def plugin_instance(self) -> Plugin:
        raise NotImplementedError

    def test_initialize_succeeds(self, plugin_instance):
        plugin_instance.initialize()
        assert plugin_instance.is_initialized

class BasePluginDiscoveryTests:
    """Tests for entry point discovery."""

    @pytest.fixture
    def entry_point_group(self) -> str:
        raise NotImplementedError

    def test_registered_in_entry_points(self, entry_point_group, plugin_class):
        from importlib.metadata import entry_points
        eps = entry_points(group=entry_point_group)
        names = [ep.name for ep in eps]
        assert plugin_class.metadata.name in names
```

## Open Questions (Resolved)

All research questions resolved. No NEEDS CLARIFICATION remaining.

## References

- Martin Fowler, "Refactoring: Improving the Design of Existing Code" (Extract Method, Replace Conditional with Polymorphism)
- Gang of Four, "Design Patterns" (Facade, Strategy)
- floe Constitution (`.specify/memory/constitution.md`)
- Existing IntegrationTestBase (`testing/base_classes/integration_test_base.py`)
