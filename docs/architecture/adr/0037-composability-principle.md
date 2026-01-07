# ADR-0037: Composability as Core Principle

## Status

Accepted

## Context

floe must scale gracefully across vastly different organizational structures:

1. **Single-team startup** - 5 data engineers, one DuckDB instance
2. **Enterprise with multiple teams** - Shared platform, standardized tooling
3. **Data Mesh organization** - Federated domains, autonomous product teams

Traditional approaches fail at these extremes:

- **Monolithic configuration**: Works for single-team, but Data Mesh requires hundreds of config variants
- **Per-team customization**: Creates drift, breaks governance, prevents cross-team data sharing
- **Rewrite between models**: Scaling from 2-tier to 3-tier (Data Mesh) becomes a migration project

**The tension:** We need ONE architecture that supports both extremes without rewriting.

## Decision

**Composability is the CORE architectural principle** guiding all design decisions.

### Definition

**Composability** = Small, interchangeable components with clean interfaces that combine to form complex systems without modification.

### Four Key Principles

#### 1. Plugin Architecture > Configuration Switches

**Rule:** If multiple implementations exist OR may exist in the future, use a plugin interface (NOT an if/else configuration switch).

**Rationale:** Plugin interfaces enable new implementations without changing the core. Configuration switches create coupling and require core changes for every variant.

**Example:**

```python
# ❌ BAD: Configuration switch (coupling)
def get_observability_backend(config: dict) -> Backend:
    if config["type"] == "jaeger":
        return JaegerBackend(config)
    elif config["type"] == "datadog":
        return DatadogBackend(config)
    # Future: Add elif for every new backend = core changes

# ✅ GOOD: Plugin interface (composable)
class ObservabilityPlugin(ABC):
    @abstractmethod
    def get_otlp_exporter_config(self) -> dict:
        pass

# Future: New backends register via entry points = no core changes
```

**Entry Points (11 plugin types):**
- `floe.computes` - Compute engines (DuckDB, Snowflake, Spark, etc.)
- `floe.orchestrators` - Orchestration platforms (Dagster, Airflow)
- `floe.catalogs` - Catalog backends (Polaris, Glue, Hive)
- `floe.storage` - Storage backends (S3, GCS, Azure, MinIO)
- `floe.telemetry_backends` - Telemetry backends (Jaeger, Datadog, Grafana Cloud)
- `floe.lineage_backends` - Lineage backends (Marquez, Atlan, OpenMetadata)
- `floe.dbt` - DBT compilation environments (local, fusion, cloud)
- `floe.semantic_layers` - Semantic layers (Cube, dbt Semantic Layer)
- `floe.ingestion` - Ingestion tools (dlt, Airbyte)
- `floe.secrets` - Secrets management (K8s Secrets, ESO, Vault)
- `floe.identity` - Identity providers (OIDC, Keycloak)

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins.

#### 2. Interface > Implementation

**Rule:** Define abstract base classes (ABCs) representing behavior contracts, NOT concrete implementations.

**Rationale:** Interfaces enable multiple implementations to coexist without core knowing about them. Concrete classes create tight coupling.

**Example:**

```python
# ✅ GOOD: ABC defines contract
class ComputePlugin(ABC):
    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def generate_profiles(self, artifacts: CompiledArtifacts) -> dict[str, Any]:
        """Generate dbt profiles.yml section for this compute target."""
        pass

# Multiple implementations register via entry points
class DuckDBPlugin(ComputePlugin): ...
class SnowflakePlugin(ComputePlugin): ...
class SparkPlugin(ComputePlugin): ...

# Core discovers plugins WITHOUT importing them
registry = PluginRegistry()
plugins = registry.discover("floe.computes")
```

**Benefit:** Adding `BigQueryPlugin` requires ZERO changes to core code.

#### 3. Progressive Disclosure

**Rule:** Point to detailed documentation instead of duplicating content. Reveal complexity only when needed.

**Rationale:** Prevents documentation bloat, ensures single source of truth, reduces cognitive load for beginners.

**Example:**

```markdown
# ❌ BAD: Duplicate plugin architecture in CLAUDE.md (800 lines)
## Plugin Architecture
[Full plugin interface definitions, entry points, examples...]

# ✅ GOOD: Pointer to detailed docs
## Plugin Architecture
floe uses plugin interfaces for extensibility. 11 plugin types exist.
**See:** docs/architecture/plugin-architecture.md
```

**Application:**
- CLAUDE.md: High-level overview + links to details
- Architecture docs: Complete specifications
- Skills: Domain expertise loaded on-demand

#### 4. Opt-in Complexity

**Rule:** Default configuration should be simple (2-tier). Advanced features (3-tier Data Mesh) are opt-in extensions, NOT separate systems.

**Rationale:** Teams start simple, add complexity only when needed, without rewriting existing configuration.

**Example:**

```yaml
# ✅ Simple: 2-tier configuration (single-team)
# platform-manifest.yaml
plugins:
  compute: duckdb
  catalog: polaris

# data-product.yaml
transforms:
  - type: dbt
    path: models/

# ✅ Advanced: 3-tier configuration (Data Mesh)
# enterprise-manifest.yaml
scope: enterprise  # NEW FIELD - enables Data Mesh
plugins:
  compute: snowflake
  catalog: polaris

# domain-manifest.yaml
scope: domain  # NEW FIELD - inherits enterprise defaults
approved_products: [sales, marketing]

# data-product.yaml
# Unchanged - same schema as 2-tier
transforms:
  - type: dbt
    path: models/
```

**Key:** Same `Manifest` schema, different `scope` field. No breaking changes when scaling.

## Consequences

### Positive

- **Scales without rewriting** - 2-tier to 3-tier is configuration change, not code migration
- **Extensibility without core changes** - New plugins via entry points, no core modifications
- **Clear interfaces** - ABCs document contracts explicitly
- **Ecosystem growth** - Community can build plugins without forking
- **Progressive disclosure** - Beginners see simple docs, experts find details
- **Testing efficiency** - Mock plugins via fixtures, test interfaces not implementations

### Negative

- **Upfront design cost** - Requires thinking about interfaces before implementations
- **Learning curve** - Teams must understand plugin architecture
- **Abstraction overhead** - More files/classes than hardcoded if/else
- **Discovery complexity** - Entry points less obvious than import statements

### Neutral

- **Trade-off:** Flexibility for upfront design cost
- **Mitigated by:** Clear documentation, reference plugins, testing utilities
- **Industry precedent:** Python ecosystem (pytest plugins, Sphinx extensions), Jenkins, Kubernetes

## Decision Matrix

### When to Create Plugin Interface

| Criteria | Example | Decision |
|----------|---------|----------|
| Multiple implementations exist today | DuckDB, Snowflake, Spark, Databricks | Plugin ✅ |
| Organization may swap implementation | Jaeger → Datadog observability backend | Plugin ✅ |
| User needs to extend behavior | Add custom policy enforcement rules | Plugin ✅ |
| Industry has competing standards | ODCS v3, Protobuf data contracts | Plugin ✅ |

### When to Use Configuration (Not Plugin)

| Criteria | Example | Decision |
|----------|---------|----------|
| Single implementation, no alternatives | OpenTelemetry SDK (emission standard) | Configuration ✅ |
| Simple parameter tuning | Log level (DEBUG, INFO, WARN) | Configuration ✅ |
| Boolean feature flag | Enable/disable lineage collection | Configuration ✅ |
| Fixed set of options (enum) | Environment (dev, staging, prod) | Configuration ✅ |

## Implementation Patterns

### Plugin Discovery Pattern

```python
from abc import ABC, abstractmethod
from importlib.metadata import entry_points

class PluginRegistry:
    """Singleton registry for all plugin types."""

    def discover(self, group: str) -> dict[str, Any]:
        """Discover plugins by entry point group.

        Args:
            group: Entry point group (e.g., "floe.computes")

        Returns:
            Dictionary mapping plugin names to plugin classes
        """
        plugins = {}
        for ep in entry_points(group=group):
            plugin_class = ep.load()
            plugins[ep.name] = plugin_class()
        return plugins
```

### Plugin Interface Pattern

```python
class ObservabilityPlugin(ABC):
    """Plugin interface for observability backends.

    Responsibilities:
    - Generate OTLP Collector exporter configuration
    - Generate OpenLineage transport configuration
    - Provide Helm values for deploying backend services
    """

    name: str  # e.g., "jaeger", "datadog"
    version: str  # Plugin version
    floe_api_version: str  # Supported floe-core API version

    @abstractmethod
    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector exporter configuration.

        Returns:
            Dictionary matching OTLP Collector config schema
        """
        pass

    @abstractmethod
    def get_lineage_config(self) -> dict[str, Any]:
        """Generate OpenLineage transport configuration.

        Returns:
            Dictionary with 'type' and backend-specific config
        """
        pass

    @abstractmethod
    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate Helm values for deploying backend services.

        Returns:
            Helm values dictionary for backend chart
        """
        pass
```

### Plugin Registration Pattern

```python
# pyproject.toml
[project.entry-points."floe.observability"]
jaeger = "floe_observability_jaeger:JaegerPlugin"
datadog = "floe_observability_datadog:DatadogPlugin"
```

## Real-World Example: ObservabilityPlugin

**Before (Configuration Switch - Coupled):**

```yaml
# platform-manifest.yaml
observability:
  backend: jaeger  # Hardcoded if/else in core
  jaeger:
    endpoint: "http://jaeger:14250"
  # Future: Add datadog section, modify core parsing logic
```

**After (Plugin Interface - Composable):**

```yaml
# platform-manifest.yaml
plugins:
  observability: jaeger  # Plugin name

# floe-observability-jaeger plugin provides:
# - get_otlp_exporter_config() → OTLP Collector config
# - get_lineage_config() → OpenLineage transport
# - get_helm_values_override() → Jaeger Helm chart values

# Future: Install floe-observability-datadog plugin
# plugins:
#   observability: datadog  # Zero core changes
```

**Benefits:**
- Adding Datadog: Install plugin, change config value (NO core changes)
- Testing: Mock ObservabilityPlugin interface (NO real Jaeger needed)
- Custom backends: Implement interface, register via entry point

## Migration Strategy

**Existing Code → Composable Architecture:**

1. **Identify hardcoded implementations** - Search for if/else on config["type"]
2. **Extract ABC** - Define interface representing contract
3. **Create entry point group** - e.g., `floe.observability`
4. **Refactor implementations** - Convert to plugin classes
5. **Update PluginRegistry** - Discover via entry points
6. **Update docs** - Document plugin interface in interfaces/

**Timeline:** Gradual (no big bang) - plugins can coexist with legacy code during migration.

## Anti-Patterns

### DON'T: Use if/else for extensible behavior

```python
# ❌ ANTI-PATTERN: Coupled to core
def get_backend(config: dict):
    if config["type"] == "jaeger":
        return JaegerBackend()
    elif config["type"] == "datadog":
        return DatadogBackend()
    # Every new backend requires core changes
```

### DON'T: Hardcode implementation in configuration schema

```python
# ❌ ANTI-PATTERN: Schema knows about implementations
class PlatformManifest(BaseModel):
    jaeger_config: Optional[JaegerConfig] = None
    datadog_config: Optional[DatadogConfig] = None
    # Every new backend adds field
```

### DO: Use plugin interface with dynamic discovery

```python
# ✅ PATTERN: Composable, extensible
class PlatformManifest(BaseModel):
    plugins: dict[str, str]  # {"observability": "jaeger"}

registry = PluginRegistry()
backend_plugin = registry.discover("floe.observability")["jaeger"]
config = backend_plugin.get_otlp_exporter_config()
```

## References

- [ADR-0018: Opinionation Boundaries](0018-opinionation-boundaries.md) - When to enforce vs allow plugins
- [ADR-0035: Observability Plugin Interface](0035-observability-plugin-interface.md) - Reference implementation
- [ADR-0036: Storage Plugin Interface](0036-storage-plugin-interface.md) - Reference implementation
- [plugin-architecture.md](../plugin-architecture.md) - Complete plugin patterns
- [interfaces/](../interfaces/index.md) - All plugin ABCs
- [03-solution-strategy.md](../../guides/03-solution-strategy.md) - Solution strategy
- **Industry References:**
  - [pytest plugin system](https://docs.pytest.org/en/stable/how-to/writing_plugins.html)
  - [Sphinx extensions](https://www.sphinx-doc.org/en/master/development/tutorials/extending_build.html)
  - [Python entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
