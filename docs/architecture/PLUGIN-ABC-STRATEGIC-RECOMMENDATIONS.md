# Plugin ABC Strategic Design Recommendations

**Date**: 2025-01-06
**Context**: Architectural validation revealed method signature mismatches between requirements and architecture docs for three plugin ABCs
**Decision Maker**: CTO
**Status**: Strategic Recommendations (Pending Approval)

---

## Executive Summary

Architectural validation identified **3 plugin ABCs with conflicting method signatures** between requirements (Domain 01) and architecture documentation (`docs/architecture/plugin-architecture.md`):

1. **OrchestratorPlugin** - Contract boundary conflict (CompiledArtifacts vs TransformConfig)
2. **SemanticLayerPlugin** - Generic vs Cube-specific interface
3. **IngestionPlugin** - Generic vs dlt-specific interface

This document provides **strategic design analysis** and **recommended interface designs** aligned with ADR-0037 (Composability Principle) and architectural vision.

---

## Conflict #1: OrchestratorPlugin Method Signature

### Current Conflict

**Requirements (REQ-022)**:
```python
@abstractmethod
def create_assets_from_artifacts(
    self,
    artifacts: CompiledArtifacts
) -> list[Asset]:
    """Generate orchestrator-specific assets from CompiledArtifacts."""
    pass
```

**Architecture (`plugin-architecture.md`)**:
```python
@abstractmethod
def create_assets_from_transforms(
    self,
    transforms: list[TransformConfig]
) -> list[Asset]:
    """Generate assets from transform configurations."""
    pass
```

### Root Cause Analysis

This represents a **fundamental architectural decision** about **contract boundaries**:

| Approach | Input Type | Coupling | Versioning Stability | Contract Adherence |
|----------|-----------|----------|---------------------|-------------------|
| Requirements | `CompiledArtifacts` | Loose | High (semver contract) | ✅ Correct (ADR principle) |
| Architecture | `list[TransformConfig]` | Tight | Low (internal type) | ❌ Violates contract-driven design |

**Key Architectural Principle** (from CLAUDE.md):
> "CompiledArtifacts is the SOLE integration point between components. FORBIDDEN: Direct FloeSpec passing."

**Implication**: Architecture docs currently **violate this principle** by exposing internal `TransformConfig` type to plugins.

### Strategic Recommendation: **Use Requirements Approach (CompiledArtifacts)**

**Rationale**:

1. **Contract-Driven Integration** (ADR Design): CompiledArtifacts is the versioned contract
   - MAJOR/MINOR/PATCH semantic versioning
   - Backward compatibility guarantees
   - Plugins insulated from core schema changes

2. **Loose Coupling**: Plugins depend on **stable contract**, not internal types
   - `TransformConfig` is internal to floe-core (can change freely)
   - `CompiledArtifacts` is public contract (requires semver discipline)

3. **Future-Proofing**: CompiledArtifacts can evolve to include:
   - Data Mesh metadata (domain, product, contracts)
   - Governance policies (classification, quality gates)
   - Observability configuration (OTel, OpenLineage)

**Anti-Pattern Example** (What We Avoid):
```python
# ❌ BAD - Plugin depends on internal type
def create_assets_from_transforms(
    self,
    transforms: list[TransformConfig]  # Internal type - breaking change if we add fields
) -> list[Asset]:
    pass
```

**Correct Pattern**:
```python
# ✅ GOOD - Plugin depends on contract
def create_assets_from_artifacts(
    self,
    artifacts: CompiledArtifacts  # Public contract - semver guarantees stability
) -> list[Asset]:
    """Generate orchestrator-specific assets from compiled artifacts.

    The plugin extracts transforms, consumption configs, and governance
    policies from CompiledArtifacts and translates them to orchestrator-
    specific asset definitions (Dagster SoftwareDefinedAssets, Airflow DAGs, etc.).

    Args:
        artifacts: Compiled artifacts containing all pipeline configuration

    Returns:
        List of orchestrator-specific asset definitions
    """
    # Plugin extracts what it needs from contract
    transforms = artifacts.transforms
    governance = artifacts.governance
    observability = artifacts.observability

    # Generate orchestrator assets
    return self._generate_assets(transforms, governance, observability)
```

### Updated Interface Design

**Recommended OrchestratorPlugin ABC**:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from floe_core.schemas import CompiledArtifacts


class OrchestratorPlugin(ABC):
    """Abstract base class for orchestrator plugins.

    Orchestrators (Dagster, Airflow 3.x, Prefect, Argo Workflows) convert
    compiled artifacts into orchestrator-specific asset/task definitions.
    """

    @abstractmethod
    def create_assets_from_artifacts(
        self,
        artifacts: CompiledArtifacts
    ) -> Any:
        """Generate orchestrator-specific assets from compiled artifacts.

        Args:
            artifacts: Compiled artifacts (contract between floe-core and plugins)

        Returns:
            Orchestrator-specific asset definitions:
            - Dagster: list[AssetDefinition]
            - Airflow: DAG
            - Prefect: list[Flow]
            - Argo: WorkflowTemplate
        """
        pass

    @abstractmethod
    def get_helm_values(
        self,
        artifacts: CompiledArtifacts,
        environment: str
    ) -> dict[str, Any]:
        """Generate Helm values for orchestrator deployment.

        Args:
            artifacts: Compiled artifacts
            environment: Target environment (dev, staging, prod)

        Returns:
            Helm values dictionary for orchestrator chart
        """
        pass

    @abstractmethod
    def validate_connection(
        self,
        config: dict[str, Any]
    ) -> bool:
        """Validate orchestrator connection configuration.

        Args:
            config: Connection configuration dictionary

        Returns:
            True if connection successful, False otherwise

        Raises:
            OrchestratorConnectionError: If connection validation fails
        """
        pass

    @abstractmethod
    def get_resource_requirements(
        self,
        workload_size: str
    ) -> dict[str, str]:
        """Get orchestrator resource requirements.

        Args:
            workload_size: Workload size (small, medium, large)

        Returns:
            Resource requirements (CPU, memory, storage)
        """
        pass

    @abstractmethod
    def emit_lineage_event(
        self,
        run_id: str,
        artifacts: CompiledArtifacts,
        status: str
    ) -> None:
        """Emit OpenLineage event for orchestrator run.

        Args:
            run_id: Orchestrator run identifier
            artifacts: Compiled artifacts
            status: Run status (START, COMPLETE, FAIL)
        """
        pass
```

**Migration Impact**: LOW
- DagsterOrchestratorPlugin currently hardcoded, not yet plugin
- Epic 3 extraction creates plugin from scratch (no existing plugins to migrate)

---

## Conflict #2: SemanticLayerPlugin Method Signature

### Current Conflict

**Requirements (REQ-061)**:
```python
@abstractmethod
def generate_cube_config(
    self,
    dbt_manifest: dict[str, Any],
    cube_config_dir: Path
) -> list[Path]:
    """Generate Cube configuration files from dbt manifest."""
    pass

@abstractmethod
def get_helm_values(
    self,
    artifacts: CompiledArtifacts,
    environment: str
) -> dict[str, Any]:
    """Generate Helm values for semantic layer deployment."""
    pass

@abstractmethod
def validate_connection(
    self,
    config: dict[str, Any]
) -> bool:
    """Validate semantic layer connection."""
    pass
```

**Architecture (`plugin-architecture.md`)**:
```python
@abstractmethod
def sync_from_dbt_manifest(
    self,
    manifest_path: Path,
    output_dir: Path
) -> list[Path]:
    """Sync dbt models to semantic layer."""
    pass

@abstractmethod
def get_security_context(
    self,
    namespace: str,
    roles: list[str]
) -> dict:
    """Get security context for namespace."""
    pass

@abstractmethod
def get_datasource_config(
    self,
    compute_plugin: ComputePlugin
) -> dict:
    """Get data source configuration."""
    pass
```

### Root Cause Analysis

The architecture interface shows **Cube-specific implementation details** leaked into the ABC:

- `sync_from_dbt_manifest()` - Specific to Cube's `cube_dbt` package workflow
- `get_security_context()` - Specific to Cube's row-level security model
- `get_datasource_config()` - Specific to Cube's data source configuration

**Problem**: This makes the interface **non-composable** for alternative semantic layers:
- dbt Semantic Layer (MetricFlow) - Different sync mechanism
- Apache Superset - Different security model
- Looker (LookML) - Proprietary configuration format

### Strategic Recommendation: **Use Requirements Approach (Generic Interface)**

**Rationale**:

1. **Technology Neutrality**: Generic methods support multiple semantic layer technologies
2. **Composability** (ADR-0037): New semantic layer → new plugin (no ABC changes)
3. **Consistency**: Matches pattern in other plugins (`get_helm_values`, `validate_connection`)

**Design Principle**: ABC defines **WHAT** plugins must do, not **HOW** they do it.

**Good Example** (Semantic Layer Neutral):
```python
# ✅ CORRECT - Generic method, Cube-specific implementation
@abstractmethod
def generate_config(
    self,
    dbt_manifest: dict[str, Any],
    output_dir: Path
) -> list[Path]:
    """Generate semantic layer configuration from dbt manifest.

    Implementation-specific behavior:
    - CubePlugin: Generates .js files via cube_dbt package
    - MetricFlowPlugin: Generates metric YAMLs
    - SupersetPlugin: Generates Superset dataset configs
    """
    pass
```

**Bad Example** (Cube-Specific Leaked into ABC):
```python
# ❌ BAD - Cube-specific method in ABC
@abstractmethod
def sync_from_dbt_manifest(  # "sync" is Cube terminology
    self,
    manifest_path: Path,
    output_dir: Path
) -> list[Path]:
    """Sync dbt models to Cube cubes."""  # "Cube cubes" in ABC docstring
    pass
```

### Updated Interface Design

**Recommended SemanticLayerPlugin ABC**:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from floe_core.schemas import CompiledArtifacts


class SemanticLayerPlugin(ABC):
    """Abstract base class for semantic layer plugins.

    Semantic layers (Cube, dbt Semantic Layer, Superset, Looker) provide
    consumption APIs (REST, GraphQL, SQL) for querying transformed data.
    """

    @abstractmethod
    def generate_config(
        self,
        dbt_manifest: dict[str, Any],
        output_dir: Path
    ) -> list[Path]:
        """Generate semantic layer configuration from dbt manifest.

        Implementations:
        - CubePlugin: Generates .js files via cube_dbt Python package
        - MetricFlowPlugin: Generates metric YAML definitions
        - SupersetPlugin: Generates Superset dataset configurations
        - LookMLPlugin: Generates LookML view files

        Args:
            dbt_manifest: Parsed dbt manifest.json dictionary
            output_dir: Directory to write configuration files

        Returns:
            List of generated configuration file paths
        """
        pass

    @abstractmethod
    def get_helm_values(
        self,
        artifacts: CompiledArtifacts,
        environment: str
    ) -> dict[str, Any]:
        """Generate Helm values for semantic layer deployment.

        Args:
            artifacts: Compiled artifacts
            environment: Target environment (dev, staging, prod)

        Returns:
            Helm values dictionary for semantic layer chart
        """
        pass

    @abstractmethod
    def validate_connection(
        self,
        config: dict[str, Any]
    ) -> bool:
        """Validate semantic layer connection configuration.

        Args:
            config: Connection configuration dictionary

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def get_security_config(
        self,
        namespace: str,
        roles: list[str]
    ) -> dict[str, Any]:
        """Get security configuration for namespace-based access control.

        Implementations:
        - CubePlugin: Returns Cube securityContext for row-level filtering
        - MetricFlowPlugin: Returns role-based dimension filtering rules
        - SupersetPlugin: Returns RLS (Row-Level Security) filters

        Args:
            namespace: floe namespace (for multi-tenancy)
            roles: User roles for RBAC

        Returns:
            Security configuration dictionary (format varies by plugin)
        """
        pass

    @abstractmethod
    def get_datasource_config(
        self,
        compute_plugin: ComputePlugin
    ) -> dict[str, Any]:
        """Get data source configuration for semantic layer.

        Semantic layer must connect to data warehouse (via ComputePlugin).
        This method generates the connection configuration.

        Args:
            compute_plugin: ComputePlugin instance (provides connection details)

        Returns:
            Data source configuration dictionary

        Example:
            >>> cube_plugin.get_datasource_config(duckdb_plugin)
            {
                "type": "duckdb",
                "connection_string": "duckdb:///warehouse.db"
            }
        """
        pass
```

**Key Design Decisions**:

1. **`generate_config` (not `sync_from_dbt_manifest`)**: Generic verb, technology-neutral
2. **`get_security_config` (not `get_security_context`)**: "Config" is neutral, "context" is Cube terminology
3. **`get_datasource_config` retained**: Delegation to ComputePlugin is cross-cutting pattern
4. **Cube-specific implementation**: `CubePlugin.generate_config()` calls `cube_dbt` package internally

**Migration Impact**: MEDIUM
- CubePlugin (MVP) exists, needs method rename
- But MVP is hardcoded, not yet plugin (Epic 3 creates plugin from scratch)
- Recommend: Build CubePlugin from requirements spec (clean slate)

---

## Conflict #3: IngestionPlugin Method Signature

### Current Conflict

**Requirements (REQ-065)**:
```python
@abstractmethod
def generate_connector_config(
    self,
    source_config: dict[str, Any],
    destination_config: dict[str, Any]
) -> dict[str, Any]:
    """Generate ingestion connector configuration."""
    pass

@abstractmethod
def get_helm_values(
    self,
    artifacts: CompiledArtifacts,
    environment: str
) -> dict[str, Any]:
    """Generate Helm values for ingestion deployment."""
    pass

@abstractmethod
def validate_connection(
    self,
    config: dict[str, Any]
) -> bool:
    """Validate ingestion source connection."""
    pass
```

**Architecture (`plugin-architecture.md`)**:
```python
@abstractmethod
def create_pipeline(
    self,
    config: IngestionConfig
) -> any:
    """Create ingestion pipeline."""
    pass

@abstractmethod
def run(
    self,
    pipeline: any,
    **kwargs
) -> IngestionResult:
    """Run ingestion pipeline."""
    pass

@abstractmethod
def get_destination_config(
    self,
    catalog_config: dict
) -> dict:
    """Get destination configuration."""
    pass
```

### Root Cause Analysis

Similar to SemanticLayerPlugin, the architecture shows **dlt-specific workflow** leaked into ABC:

- `create_pipeline()` + `run()` - Two-step execution model specific to dlt
- `IngestionConfig`, `IngestionResult` - dlt-specific types
- Missing methods: `get_helm_values()`, `validate_connection()` (standard pattern)

**Problem**: Alternative ingestion tools have different paradigms:
- **Airbyte**: Declarative connector configs (no "pipeline" object)
- **Fivetran**: SaaS API (no local execution)
- **Meltano**: Singer taps/targets (different execution model)

### Strategic Recommendation: **Use Requirements Approach (Generic Interface)**

**Rationale**:

1. **Tool Neutrality**: Support dlt (open-source), Airbyte (declarative), Fivetran (SaaS)
2. **Consistency**: Match OrchestratorPlugin, SemanticLayerPlugin patterns
3. **Kubernetes-Native**: Helm deployment pattern (standard across plugins)

**Design Principle**: ABC defines **configuration generation** (declarative), not execution (imperative).

### Updated Interface Design

**Recommended IngestionPlugin ABC**:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from floe_core.schemas import CompiledArtifacts


class IngestionPlugin(ABC):
    """Abstract base class for ingestion plugins.

    Ingestion tools (dlt, Airbyte, Fivetran, Meltano) load data from
    external sources into Iceberg tables via catalog.
    """

    @abstractmethod
    def generate_connector_config(
        self,
        source_config: dict[str, Any],
        destination_config: dict[str, Any],
        output_dir: Path
    ) -> list[Path]:
        """Generate ingestion connector configuration files.

        Implementations:
        - DLTPlugin: Generates dlt pipeline.py + sources.py
        - AirbytePlugin: Generates Airbyte connection.yaml
        - FivetranPlugin: Generates Fivetran connector config JSON
        - MeltanoPlugin: Generates meltano.yml tap/target configs

        Args:
            source_config: Source system configuration (API keys, endpoints)
            destination_config: Destination configuration (catalog, warehouse)
            output_dir: Directory to write configuration files

        Returns:
            List of generated configuration file paths
        """
        pass

    @abstractmethod
    def get_helm_values(
        self,
        artifacts: CompiledArtifacts,
        environment: str
    ) -> dict[str, Any]:
        """Generate Helm values for ingestion deployment.

        Args:
            artifacts: Compiled artifacts
            environment: Target environment (dev, staging, prod)

        Returns:
            Helm values dictionary for ingestion chart

        Example:
            {
                "image": "dlt:1.0.0",
                "schedule": "0 * * * *",
                "resources": {"cpu": "500m", "memory": "1Gi"}
            }
        """
        pass

    @abstractmethod
    def validate_connection(
        self,
        source_config: dict[str, Any]
    ) -> bool:
        """Validate source system connection.

        Args:
            source_config: Source system configuration

        Returns:
            True if connection successful, False otherwise

        Raises:
            IngestionConnectionError: If connection validation fails
        """
        pass

    @abstractmethod
    def get_destination_config(
        self,
        catalog_plugin: CatalogPlugin
    ) -> dict[str, Any]:
        """Get destination configuration for ingestion target.

        Ingestion writes to Iceberg tables (via CatalogPlugin).
        This method generates the destination configuration.

        Args:
            catalog_plugin: CatalogPlugin instance (provides catalog URI, credentials)

        Returns:
            Destination configuration dictionary

        Example:
            >>> dlt_plugin.get_destination_config(polaris_plugin)
            {
                "type": "iceberg",
                "catalog_uri": "https://polaris.example.com/api/catalog",
                "warehouse": "s3://bucket/warehouse/"
            }
        """
        pass
```

**Key Design Decisions**:

1. **`generate_connector_config` (not `create_pipeline`)**: Declarative, not imperative
2. **No `run()` method**: Execution handled by OrchestratorPlugin (Dagster schedules ingestion jobs)
3. **`get_destination_config` retained**: Delegation to CatalogPlugin is cross-cutting pattern
4. **dlt-specific execution**: `DLTPlugin` internals handle `dlt.pipeline()` creation, but ABC doesn't expose it

**Execution Flow**:
```
1. Compile: IngestionPlugin.generate_connector_config() → Write configs to filesystem
2. Deploy: Helm chart uses configs to create K8s CronJob
3. Execute: CronJob runs dlt CLI (or Airbyte connector) → Writes to Iceberg
4. Orchestrate: DagsterOrchestratorPlugin monitors ingestion jobs → Downstream transforms
```

**Migration Impact**: LOW
- No existing plugins (MVP has no ingestion yet)
- Epic 8 creates DLTPlugin from scratch (clean implementation)

---

## Cross-Cutting Pattern: Standard Plugin Methods

All three plugins share **common methods** - this should be formalized:

### Standard Plugin Interface (Recommended)

```python
class PluginBase(ABC):
    """Base class for all plugins with standard methods."""

    @abstractmethod
    def get_helm_values(
        self,
        artifacts: CompiledArtifacts,
        environment: str
    ) -> dict[str, Any]:
        """REQUIRED: All deployable plugins MUST support Helm."""
        pass

    @abstractmethod
    def validate_connection(
        self,
        config: dict[str, Any]
    ) -> bool:
        """REQUIRED: All plugins MUST validate connectivity."""
        pass

    @abstractmethod
    def get_resource_requirements(
        self,
        workload_size: str
    ) -> dict[str, str]:
        """REQUIRED: All plugins MUST define K8s resource requests/limits."""
        pass
```

**Benefit**: Consistency across plugin types, enforced via ABC inheritance.

---

## Recommendations Summary

### Immediate Actions (Epic 3)

1. **Update plugin-architecture.md** to match requirements specifications:
   - `OrchestratorPlugin`: Use `create_assets_from_artifacts(CompiledArtifacts)`
   - `SemanticLayerPlugin`: Use generic methods (`generate_config`, not `sync_from_dbt_manifest`)
   - `IngestionPlugin`: Use declarative methods (`generate_connector_config`, not `create_pipeline`)

2. **Update floe-core/src/floe_core/plugin_interfaces.py**:
   - Implement recommended ABCs (above)
   - Add `PluginBase` for cross-cutting methods
   - Ensure all methods have type hints, docstrings, examples

3. **Create contract tests** (`tests/contract/test_plugin_interfaces.py`):
   - Verify all plugins inherit from correct ABC
   - Verify method signatures match
   - Verify type hints present

### Documentation Updates

4. **Create migration guide** (`MIGRATION.md`):
   - Document method renames (for future plugin developers)
   - Explain rationale (contract-driven design, composability)

5. **Update ADR-0037** (Composability Principle):
   - Add "Interface Design Patterns" section
   - Reference these three plugins as examples

### Epic 8 (Production Hardening)

6. **Implement alternative plugins** to validate composability:
   - AirflowOrchestratorPlugin (validates generic OrchestratorPlugin ABC)
   - MetricFlowSemanticPlugin (validates generic SemanticLayerPlugin ABC)
   - AirbyteIngestionPlugin (validates generic IngestionPlugin ABC)

---

## Decision Matrix

| Plugin | Architecture Approach | Requirements Approach | Recommendation | Rationale |
|--------|----------------------|----------------------|----------------|-----------|
| **OrchestratorPlugin** | `create_assets_from_transforms(list[TransformConfig])` | `create_assets_from_artifacts(CompiledArtifacts)` | **Requirements** | Contract-driven integration (ADR principle) |
| **SemanticLayerPlugin** | Cube-specific methods (`sync_from_dbt_manifest`) | Generic methods (`generate_config`) | **Requirements** | Composability (supports Cube, MetricFlow, Superset) |
| **IngestionPlugin** | dlt-specific methods (`create_pipeline`, `run`) | Declarative methods (`generate_connector_config`) | **Requirements** | Composability (supports dlt, Airbyte, Fivetran) |

**Consistent Pattern**: Requirements favor **generic, technology-neutral interfaces** that support multiple implementations without ABC changes (composability principle).

---

## Next Steps

1. **CTO Approval**: Review and approve recommendations
2. **Update Architecture Docs**: Apply recommended ABCs to `plugin-architecture.md`
3. **Update Requirements**: Mark REQ-022, REQ-061, REQ-065 as **authoritative**
4. **Epic Planning**: Include ABC updates in Epic 3 scope
5. **Communication**: Notify team of interface design decisions

---

**Prepared By**: Claude Code Architectural Validation
**Review Required**: CTO Approval
**Impact**: Medium (affects plugin interface design, no impact on MVP since plugins not yet extracted)
